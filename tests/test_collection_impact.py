import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from saaf.agents.collection import CollectionAgent
from saaf.agents.impact import ImpactAgent, ImpactExplanation
from saaf.collection.models import PickupDraft
from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository
from saaf.impact.metrics import calculate_metrics
from saaf.orchestration.contracts import ConversationContext
from saaf.orchestration.graph import Orchestrator

SOURCE = Path(__file__).resolve().parents[1] / "data" / "saaf_simulated_farms.json"
NOW = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)


@pytest.fixture
def services(tmp_path):
    farms = FarmRepository(tmp_path / "farms.sqlite3")
    farms.seed(SOURCE)
    requests = CollectionRepository(farms)
    return farms, requests, CollectionAgent(farms, requests, clock=lambda: NOW)


def test_arabic_confirmation_persistence_and_tracking(services):
    farms, requests, agent = services
    initial = agent.plan_collection("تشلون المخلفات؟", "SIM-001")
    assert initial.status == "needs_input"
    assert initial.estimated_annual_residue_kg == 10605
    proposal = agent.plan_collection("أبي جمع المخلفات، الكمية ٣٠٠ كيلو", "SIM-001")
    assert proposal.status == "awaiting_confirmation"
    assert proposal.draft.requested_quantity_kg == 300 and proposal.draft.pickup_date == date(2026, 11, 21)
    assert requests.list() == []
    assert agent.plan_collection("تمام", "SIM-001", proposal.draft).status == "needs_input"
    assert requests.list() == []
    saved = agent.plan_collection("أؤكد الطلب", "SIM-001", proposal.draft).request
    assert saved.status == "confirmed" and saved.simulated and saved.created_at == NOW
    assert agent.plan_collection("أؤكد", "SIM-001", proposal.draft).request == saved
    assert agent.plan_collection("تتبع الطلب " + saved.request_id, "SIM-001").request == saved
    assert agent.plan_collection("طلباتي", "SIM-001").requests == (saved,)
    assert agent.plan_collection("تتبع الطلب " + saved.request_id, "SIM-002").status == "not_found"
    assert CollectionRepository(FarmRepository(farms.path)).list() == [saved]


@pytest.mark.parametrize("quantity", [
    "0 كجم", "-40 كجم", "- 40 كجم", "2 طن", "1.5 كجم", "١٫٥ كجم",
    "6 كجم أو 7 كجم", "1, 200 كجم", "9223372036854775808 كجم",
])
def test_invalid_quantities_require_input(services, quantity):
    _, requests, agent = services
    assert agent.plan_collection(quantity, "SIM-001", continuing=True).status == "needs_input"
    assert not requests.list()


def test_drafts_cannot_write_for_other_farms_or_expired_dates(services):
    _, requests, agent = services
    draft = agent.plan_collection("60 كجم", "SIM-001").draft
    assert agent.plan_collection("أؤكد", "SIM-002", draft).status == "needs_input"
    expired = draft.model_copy(update={"pickup_date": date(2026, 11, 20)})
    assert agent.plan_collection("أؤكد", "SIM-001", expired).status == "needs_input"
    assert agent.plan_collection("إلغاء المسودة", "SIM-001", draft).draft is None
    assert agent.plan_collection("60 كجم", "SIM-999").status == "needs_input"
    assert not requests.list()


def test_concurrent_duplicate_confirmation_and_cancellation(services):
    _, requests, agent = services
    draft = agent.plan_collection("50 كجم", "SIM-001").draft
    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = set(executor.map(lambda _: requests.confirm(draft, NOW).request_id, range(8)))
    assert len(ids) == 1
    request_id, = ids
    query = "إلغاء الطلب " + request_id
    assert agent.plan_collection(query, "SIM-002").status == "not_found"
    assert agent.plan_collection(query, "SIM-001").request.status == "cancelled"
    assert agent.plan_collection("أؤكد", "SIM-001", draft).request.status == "cancelled"
    assert len(requests.list()) == 1


def test_impact_uses_registered_farms_and_only_confirmed_demo_quantities(services):
    farms, requests, _ = services
    seeded = json.loads(SOURCE.read_text(encoding="utf-8"))["farms"]
    day = date(2026, 11, 21)
    for farm, kg in (("SIM-001", 250), ("SIM-011", 100), ("SIM-012", 900)):
        item = requests.confirm(PickupDraft(farm_id=farm, pickup_date=day, requested_quantity_kg=kg), NOW)
        if farm == "SIM-012":
            requests.cancel(item.request_id, farm_id=farm)
    totals = calculate_metrics(farms, requests)
    assert totals.registered_farms == 20
    assert totals.palm_trees == sum(row["palm_count"] for row in seeded)
    assert totals.estimated_annual_waste_kg == sum(row["est_residue_kg_per_year"] for row in seeded)
    assert totals.confirmed_requested_quantity_kg == 350
    assert totals.requests_by_status.model_dump() == {"confirmed": 2, "cancelled": 1}
    assert totals.requests_by_region_and_status["القصيم"].model_dump() == {"confirmed": 1, "cancelled": 1}
    regional = ImpactAgent(farms, requests).estimate_impact("كم الكمية المؤكدة في القصيم؟")
    assert regional.metrics.confirmed_requested_quantity_kg == 100
    assert regional.metrics.registered_farms == 10


@pytest.mark.parametrize(("question", "indicator"), [
    ("كم ننتج فحم حيوي؟", "biochar"),
    ("كم الكربون المخزن؟", "stored_carbon"),
    ("كم الانبعاثات المتجنبة؟", "avoided_emissions"),
    ("احسب توفير مياه الري", "water_savings"),
])
def test_environmental_data_gaps_via_graph(services, question, indicator):
    farms, requests, _ = services
    graph = Orchestrator(None, impact=ImpactAgent(farms, requests))
    response = graph.run(question)
    assert response.intent == "impact" and response.status == "insufficient_data"
    gap, = response.impact.gaps
    assert gap.indicator == indicator and gap.missing_information
    assert response.impact.metrics.simulated


def test_impact_model_explains_precomputed_metrics_with_safe_fallback(services):
    farms, requests, _ = services

    class Model:
        def invoke(self, messages):
            assert '"registered_farms":20' in messages[1][1]
            return ImpactExplanation(focus="collection")

    class BrokenModel:
        def invoke(self, messages):
            raise RuntimeError("private provider details")

    selected = ImpactAgent(farms, requests, Model()).estimate_impact("إجمالي الطلبات")
    fallback = ImpactAgent(farms, requests, BrokenModel()).estimate_impact("إجمالي الطلبات")
    assert selected.metrics == fallback.metrics
    assert "يستبعد الطلبات الملغاة" in selected.answer_ar
    assert "private provider details" not in fallback.answer_ar


def test_multi_turn_graph_confirmation_context_and_other_routes(services):
    farms, requests, collection = services
    graph = Orchestrator(None, collection=collection, impact=ImpactAgent(farms, requests))
    no_farm = graph.run("أبغى طلب جمع للسعف")
    assert no_farm.status == "needs_input"
    no_amount = graph.run("SIM-001", context=no_farm.context)
    assert no_amount.context.farm_id == "SIM-001" and no_amount.status == "needs_input"
    pending = graph.run("٢١٠", context=no_amount.context)
    assert pending.status == "awaiting_confirmation"
    assert not requests.list()
    copied_context = ConversationContext.model_validate_json(pending.context.model_dump_json())
    assert graph.run("أؤكد", context=copied_context, farm_id="SIM-002").status == "needs_input"
    assert not requests.list()
    confirmed = graph.run("أؤكد", context=copied_context)
    assert confirmed.collection.request.requested_quantity_kg == 210
    assert confirmed.context.pickup_draft is None
    assert graph.run("أؤكد", context=confirmed.context).status == "needs_input"
    assert graph.run("تتبع " + confirmed.collection.request.request_id,
                     context=confirmed.context).collection.request == confirmed.collection.request
    impact = graph.run("وش إجمالي الطلبات حسب المنطقة؟", context=confirmed.context)
    assert impact.impact.metrics.confirmed_requested_quantity_kg == 210
    assert graph.run("كم عدد المزارع؟").impact.metrics.registered_farms == 20
    assert graph.run("أحتاج رصد النخيل", context=impact.context).status == "not_implemented"
