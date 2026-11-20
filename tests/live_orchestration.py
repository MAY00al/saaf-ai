"""Opt-in provider integration for the Phase 4 graph."""

from pathlib import Path

import pytest

from saaf.agents.recommendation import build_agent
from saaf.farms import FarmRepository
from saaf.orchestration.graph import Orchestrator
from saaf.providers import chat_config, embedding_config, load_environment

DATA = Path(__file__).resolve().parents[1] / "data"


def test_live_graph(tmp_path):
    load_environment()
    try:
        chat_config().require_key()
        embedding_config().require_key()
    except ValueError:
        pytest.skip("configure keys for both selected providers")
    farms = FarmRepository(tmp_path / "farms.sqlite3")
    farms.seed(DATA / "saaf_simulated_farms.json")

    class LiveAgent:
        def recommend(self, query, farm_id=None):
            agent = build_agent(
                DATA / "saaf_knowledge_base.json", farms, index_path=tmp_path / "chroma",
            )
            return agent.recommend(query, farm_id)

    response = Orchestrator(LiveAgent()).run(
        "وش قالت تجربة الطماطم بالصوبة عن رطوبة التربة مع فحم السعف؟", farm_id="SIM-002",
    )
    assert response.intent == "recommendation"
    assert response.status == "ok"
    assert response.recommendation.simulated_data is True
    assert any(source.record_id == "bc-06" for source in response.recommendation.sources)
