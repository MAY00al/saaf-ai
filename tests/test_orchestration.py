from pathlib import Path

import pytest

from saaf.agents.recommendation import EvidenceDecision, RecommendationAgent, RecommendationResponse
from saaf.agents.tools import get_farm_profile, search_scientific_evidence
from saaf.farms import FarmRepository
from saaf.knowledge.retrieval import EmbeddingUnavailable, Hit, KnowledgeIndex, SearchResult
from saaf.orchestration.evaluation import CASES, evaluate_routing
from saaf.orchestration.graph import Orchestrator

DATA = Path(__file__).resolve().parents[1] / "data"


class RecordingAgent:
    def __init__(self):
        self.calls = []

    def recommend(self, query, farm_id=None):
        self.calls.append((query, farm_id))
        return RecommendationResponse(
            answer_ar="رد تجريبي", recommendation=None, farm_id=farm_id,
            simulated_data=None, sources=[], evidence_level=[], warnings=[],
            missing_information=[], status="ok",
        )


@pytest.mark.parametrize("query,expected,candidates", CASES)
def test_routing_scenarios(query, expected, candidates):
    agent = RecordingAgent()
    response = Orchestrator(agent).run(query)
    assert (response.intent, response.candidate_intents) == (expected, candidates)
    assert len(agent.calls) == int(expected == "recommendation")
    if expected in {"collection", "monitoring", "impact"}:
        assert response.status == "not_implemented"
        assert response.recommendation is None
    if expected == "clarification":
        assert response.status == "needs_input"
    if expected == "unsupported":
        assert response.status == "unsupported"


def test_routing_accuracy_counts_only_intents():
    report = evaluate_routing()
    assert report.total >= 20
    assert report.correct == report.total
    assert report.routing_accuracy == 1


def test_session_continuity_switch_and_isolation():
    agent = RecordingAgent()
    graph = Orchestrator(agent)
    first = graph.run("وش أثر الفحم الحيوي؟", farm_id="SIM-001")
    followup = graph.run("وضح أكثر", context=first.context)
    assert agent.calls[-1][1] == "SIM-001"
    assert first.context.previous_query in agent.calls[-1][0]
    switched = graph.run("هل الملوحة مهمة في sim-002؟", context=followup.context)
    assert switched.context.farm_id == "SIM-002"
    assert "SIM-001" not in agent.calls[-1][0]
    assert first.context.farm_id == "SIM-001"
    graph.run("هل الفحم الحيوي مفيد؟")
    assert agent.calls[-1][1] is None
    result = graph.run("وضح أكثر", context=switched.context, farm_id="SIM-003")
    assert result.status == "needs_input"
    assert result.context.previous_query is None


def test_conflicting_farm_ids_block_execution():
    agent = RecordingAgent()
    graph = Orchestrator(agent)
    assert graph.run("فحم حيوي في SIM-002؟", farm_id="SIM-001").status == "needs_input"
    assert graph.run("قارن الملوحة في SIM-001 وSIM-002").status == "needs_input"
    assert graph.run("الفحم الحيوي؟", farm_id="غير صالح").status == "needs_input"
    assert not agent.calls


def test_unnamed_farm_switch_does_not_reuse_active_profile():
    agent = RecordingAgent()
    graph = Orchestrator(agent)
    first = graph.run("الفحم الحيوي؟", farm_id="SIM-001")
    second = graph.run("وش أثر الفحم الحيوي في مزرعة ثانية؟", context=first.context)
    assert second.status == "needs_input"
    assert second.context.farm_id is None
    assert len(agent.calls) == 1


class QuotaError(Exception):
    status_code = 429


@pytest.mark.parametrize("error,expected", [
    (QuotaError("test-secret"), "حد الاستخدام"),
    (RuntimeError("test-secret"), "تعذّر تشغيل"),
])
def test_agent_errors_are_localized_and_not_retried(error, expected):
    class BrokenAgent:
        calls = 0

        def recommend(self, query, farm_id=None):
            self.calls += 1
            raise error

    agent = BrokenAgent()
    response = Orchestrator(agent).run("الفحم الحيوي؟")
    assert response.status == "unavailable"
    assert expected in response.answer_ar
    assert "test-secret" not in response.model_dump_json()
    assert agent.calls == 1


def test_rejects_malformed_or_cross_farm_agent_output(monkeypatch):
    agent = RecordingAgent()
    graph = Orchestrator(agent)
    monkeypatch.setattr(agent, "recommend", lambda *_: {"answer_ar": "test-secret"})
    assert graph.run("الفحم الحيوي؟").status == "unavailable"
    monkeypatch.setattr(agent, "recommend", lambda *_: RecordingAgent().recommend("", "SIM-999"))
    assert graph.run("الفحم الحيوي؟", farm_id="SIM-001").status == "unavailable"


@pytest.fixture
def services(tmp_path):
    class Vectors:
        def embed_documents(self, texts):
            return [[1.0, float(i)] for i, _ in enumerate(texts)]

        def embed_query(self, text):
            return [1.0, 0.0]

    farms = FarmRepository(tmp_path / "farm.sqlite")
    farms.seed(DATA / "saaf_simulated_farms.json")
    knowledge = KnowledgeIndex(DATA / "saaf_knowledge_base.json", tmp_path / "chroma", Vectors())
    knowledge.ingest()
    return farms, knowledge


def test_graph_with_real_recommendation_preserves_citations_and_provenance(services):
    class Chat:
        def invoke(self, messages):
            return EvidenceDecision(scope="general", outcome="answered", record_ids=["ctx-01"])

    farms, knowledge = services
    graph = Orchestrator(RecommendationAgent(knowledge, farms, Chat(), top_k=1))
    result = graph.run("وش قالت الدراسات العلمية عن عدد النخيل؟", farm_id="SIM-002")
    assert result.status == "ok"
    assert result.recommendation.simulated_data is True
    assert result.recommendation.sources[0].record_id == "ctx-01"
    assert result.recommendation.sources[0].source_id == "GASTAT2023"
    assert graph.run("الفحم الحيوي؟", farm_id="SIM-999").status == "needs_input"


def test_tool_argument_and_result_validation(services, monkeypatch):
    farms, knowledge = services
    with pytest.raises(ValueError):
        search_scientific_evidence(knowledge, " ", top_k=1)
    with pytest.raises(ValueError):
        search_scientific_evidence(knowledge, "الفحم", top_k=0)
    with pytest.raises(ValueError):
        get_farm_profile(farms, "not a farm id")
    wrong = farms.get_farm("SIM-002")
    monkeypatch.setattr(farms, "get_farm", lambda _: wrong)
    with pytest.raises(ValueError, match="different ID"):
        get_farm_profile(farms, "SIM-001")
    record = knowledge.corpus.records[0].model_copy(update={"text_ar": "ادعاء غير موثق"})
    hit = Hit(record, knowledge.corpus.sources[record.source_id], 0.9)
    monkeypatch.setattr(knowledge, "search", lambda *args, **kwargs: SearchResult("ok", (hit,)))
    with pytest.raises(ValueError, match="does not match"):
        search_scientific_evidence(knowledge, "الفحم")


def test_wrapped_embedding_rate_limit_preserved_by_real_agent(services, monkeypatch):
    farms, knowledge = services

    def fail(*args, **kwargs):
        raise EmbeddingUnavailable("internal details") from QuotaError("test-secret")

    monkeypatch.setattr(knowledge, "search", fail)
    response = Orchestrator(RecommendationAgent(knowledge, farms, None)).run("الفحم الحيوي؟")
    assert response.status == "unavailable"
    assert "حد الاستخدام" in response.answer_ar
    assert "test-secret" not in response.model_dump_json()
