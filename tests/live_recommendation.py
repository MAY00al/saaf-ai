"""Opt-in integration test against Gemini's free-tier model offerings."""

import os
from pathlib import Path

import pytest

from saaf.agents.recommendation import build_agent
from saaf.farms import FarmRepository
from saaf.providers import GEMINI_CHAT_MODEL, GEMINI_EMBEDDING_MODEL, load_environment

DATA = Path(__file__).resolve().parents[1] / "data"


def test_gemini_recommendation(tmp_path, monkeypatch):
    load_environment()
    if not any(os.getenv(name, "").strip() for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY")):
        pytest.skip("set GOOGLE_API_KEY or GEMINI_API_KEY to run the Gemini integration")
    monkeypatch.setenv("SAAF_CHAT_PROVIDER", "gemini")
    monkeypatch.setenv("SAAF_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("SAAF_CHAT_MODEL", GEMINI_CHAT_MODEL)
    monkeypatch.setenv("SAAF_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL)
    farms = FarmRepository(tmp_path / "farms.sqlite3")
    farms.seed(DATA / "saaf_simulated_farms.json")
    agent = build_agent(
        DATA / "saaf_knowledge_base.json", farms, index_path=tmp_path / "chroma",
    )
    response = agent.recommend("وش قالت تجربة الطماطم بالصوبة عن رطوبة التربة مع فحم السعف؟", "SIM-002")
    assert response.status == "ok"
    assert response.simulated_data is True
    assert any(source.record_id == "bc-06" for source in response.sources)
    assert any("مالحة" in warning for warning in response.warnings)
    unsupported = agent.recommend("كم بالمية بأوفر من موية الري في مزرعتي؟", "SIM-002")
    assert unsupported.status == "insufficient_evidence"
    assert not unsupported.sources
