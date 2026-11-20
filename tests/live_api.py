"""Opt-in HTTP smoke test using the configured chat and embedding providers."""

from fastapi.testclient import TestClient
import pytest

from saaf.api.app import create_app
from saaf.farms import FarmRepository
from saaf.providers import chat_config, embedding_config, load_environment


def test_live_recommendation_over_http(tmp_path, monkeypatch):
    load_environment()
    try:
        chat_config().require_key()
        embedding_config().require_key()
    except ValueError:
        pytest.skip("Configure credentials for both selected providers.")
    database = tmp_path / "live.sqlite3"
    monkeypatch.setenv("SAAF_SQLITE_PATH", str(database))
    monkeypatch.setenv("SAAF_CHROMA_DIR", str(tmp_path / "chroma"))
    FarmRepository(database).seed()
    with TestClient(create_app(cors_origins=[])) as client:
        session = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(f"/api/v1/sessions/{session}/chat", json={
            "message": "وش قالت تجربة الطماطم بالصوبة عن رطوبة التربة مع فحم السعف؟",
            "farm_id": "SIM-002",
        })
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        answer = payload["recommendation"]
        assert answer["simulated_data"] is True
        assert any(source["record_id"] == "bc-06" for source in answer["sources"])
