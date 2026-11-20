from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from saaf.agents.collection import CollectionAgent
from saaf.agents.impact import ImpactAgent
from saaf.agents.monitoring import MonitoringAgent
from saaf.agents.recommendation import EvidenceDecision, RecommendationAgent
from saaf.api import app as api
from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository
from saaf.knowledge.retrieval import Hit, KnowledgeIndex, SearchResult
from saaf.monitoring.inference import MonitoringSettings
from saaf.monitoring.models import Detection
from saaf.orchestration.graph import Orchestrator

DATA = Path(__file__).resolve().parents[1] / "data"
BASE = "/api/v1"


class Vectors:
    def embed_documents(self, texts):
        return [[1.0, float(i)] for i, _ in enumerate(texts)]

    def embed_query(self, text):
        return [1.0, 0.0]


class Chat:
    def invoke(self, messages):
        return EvidenceDecision(scope="general", outcome="answered", record_ids=["ctx-01"])


class Detector:
    model_id = "offline-test-model"

    def predict(self, image, settings):
        return (Detection(confidence=0.9, xyxy=(2, 2, 20, 20)),)


@pytest.fixture
def client(tmp_path):
    farms = FarmRepository(tmp_path / "farms.sqlite3")
    farms.seed(DATA / "saaf_simulated_farms.json")
    collections = CollectionRepository(farms)
    impact = ImpactAgent(farms, collections)
    index = KnowledgeIndex(DATA / "saaf_knowledge_base.json", tmp_path / "chroma", Vectors())
    index.ingest()
    graph = Orchestrator(
        RecommendationAgent(index, farms, Chat(), top_k=1),
        collection=CollectionAgent(farms, collections), impact=impact,
        monitoring=MonitoringAgent(farms, MonitoringSettings(output_dir=tmp_path / "images"), Detector()),
    )
    with TestClient(api.create_app(api.Services(farms, collections, impact, graph),
                                   cors_origins=["http://localhost:5173"])) as client:
        yield client


def session(client):
    response = client.post(f"{BASE}/sessions")
    assert response.status_code == 201
    return f"{BASE}/sessions/{response.json()['session_id']}"


def png():
    stream = BytesIO()
    Image.new("RGB", (64, 64)).save(stream, format="PNG")
    return stream.getvalue()


def test_jpeg_upload_reaches_detector(client):
    stream = BytesIO()
    Image.new("RGB", (64, 64)).save(stream, format="JPEG")
    response = client.post(session(client) + "/monitoring/detect", params={"farm_id": "SIM-001"},
                           content=stream.getvalue(), headers={"Content-Type": "image/jpeg"})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    observation = result["monitoring"]["observation"]
    assert observation["detected_count"] == 1
    assert client.get(observation["annotated_image"]).content.startswith(b"\x89PNG")


def test_http_suitability_recovers_from_dosage_intent(client, monkeypatch):
    agent = client.app.state.services.orchestrator.recommendation
    records = [r for r in agent.knowledge.corpus.records if r.id in {"bc-02", "bc-08", "bc-09"}]
    hits = tuple(Hit(record, agent.knowledge.corpus.sources[record.source_id], 0.9) for record in records)
    monkeypatch.setattr(agent, "top_k", 3)
    monkeypatch.setattr(agent.knowledge, "search", lambda *args, **kwargs: SearchResult("ok", hits))
    monkeypatch.setattr(agent.model, "invoke",
                        lambda _: EvidenceDecision(scope="farm", outcome="farm_dose", record_ids=[]))
    response = client.post(session(client) + "/chat", json={
        "message": "هل يصلح الفحم الحيوي لمزرعتي؟", "farm_id": "SIM-002",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["intent"] == "recommendation" and result["status"] == "ok"
    answer = result["recommendation"]
    assert answer["simulated_data"]
    assert {citation["record_id"] for citation in answer["sources"]} == {"bc-02", "bc-08", "bc-09"}
    assert any("مالحة" in warning for warning in answer["warnings"])
    assert any("قلوية" in warning for warning in answer["warnings"])
    assert "جرعة" not in answer["answer_ar"]


@pytest.mark.parametrize("question,field", [
    ("كم كمية مخلفات النخيل السنوية؟", "estimated_annual_waste_kg"),
    ("إيش وزن المخلفات اللي تم جمعها؟", "confirmed_requested_quantity_kg"),
    ("وش الكمية اللي جمعتوها؟", "confirmed_requested_quantity_kg"),
    ("How much palm waste was collected?", "confirmed_requested_quantity_kg"),
])
def test_http_routes_aggregate_waste_and_collection_to_impact(client, question, field):
    response = client.post(session(client) + "/chat", json={"message": question})
    assert response.status_code == 200
    result = response.json()
    assert result["intent"] == "impact" and result["status"] == "ok"
    metrics = result["impact"]["metrics"]
    assert metrics["simulated"] and field in metrics


def test_recommendation_and_session_isolation(client):
    first, second = session(client), session(client)
    response = client.post(first + "/chat", json={
        "message": "وش قالت الدراسات العلمية عن عدد النخيل؟", "farm_id": "SIM-002",
    }).json()
    assert response["intent"] == "recommendation" and response["status"] == "ok"
    assert response["recommendation"]["simulated_data"] is True
    assert response["recommendation"]["sources"][0]["source_id"] == "GASTAT2023"
    assert response["recommendation"]["sources"][0]["url"].startswith("http")
    assert client.get(first).json()["farm_id"] == "SIM-002"
    assert client.get(second).json()["farm_id"] is None
    assert client.delete(first).status_code == 204
    assert client.post(first + "/chat", json={"message": "الفحم الحيوي"}).status_code == 404


def test_farm_management_validates_and_preserves_simulation(client):
    farms = client.get(f"{BASE}/farms", params={"region": "الأحساء"}).json()
    assert len(farms) == 10
    farm = farms[0]
    assert farm.pop("provenance")["data_kind"] == "simulated"
    assert client.post(f"{BASE}/farms", json=farm).status_code == 409
    farm["farm_id"] = "SIM-TEST"
    assert client.post(f"{BASE}/farms", json={**farm, "simulated": False}).status_code == 422
    assert client.post(f"{BASE}/farms", json=farm).status_code == 201
    endpoint = f"{BASE}/farms/SIM-TEST"
    assert client.patch(endpoint, json={"palm_count": 2}).status_code == 422
    assert client.patch(endpoint, json={"area_ha": None}).status_code == 422
    assert client.patch(endpoint, json={"soil_ph": None}).json()["soil_ph"] is None
    assert client.get(f"{BASE}/farms/statistics").json()["farm_count"] == 21
    assert client.delete(endpoint).status_code == 204
    assert client.get(endpoint).status_code == 404


def test_collection_confirmation_tracking_and_impact(client):
    source, stranger = session(client), session(client)
    request = {"farm_id": "SIM-001", "requested_quantity_kg": 120}
    proposal = client.post(source + "/collections/propose", json=request).json()
    assert proposal["status"] == "awaiting_confirmation"
    assert proposal["collection"]["estimated_annual_residue_kg"] == 10605
    pending = {"confirmed": True, "draft": proposal["collection"]["draft"]}
    records = f"{BASE}/farms/SIM-001/collections"
    assert client.get(records).json() == []
    assert client.post(stranger + "/collections/confirm", json=pending).status_code == 409
    assert client.post(source + "/collections/confirm", json={**pending, "confirmed": False}).status_code == 422
    tampered = {**pending, "draft": {**pending["draft"], "requested_quantity_kg": 500}}
    assert client.post(source + "/collections/confirm", json=tampered).status_code == 409
    saved = client.post(source + "/collections/confirm", json=pending).json()["collection"]["request"]
    assert saved["simulated"] and saved["requested_quantity_kg"] == 120
    assert client.get(records).json() == [saved]
    assert client.get(f"{BASE}/farms/SIM-002/collections/{saved['request_id']}").status_code == 404
    assert client.delete(f"{BASE}/farms/SIM-001").status_code == 409
    impact = client.get(f"{BASE}/impact", params={"region": "الأحساء"}).json()
    assert impact["metrics"]["confirmed_requested_quantity_kg"] == 120
    assert impact["simulated"] is True
    gap = client.post(f"{BASE}/impact/assess", json={"message": "كم الانبعاثات المتجنبة؟"}).json()
    assert gap["status"] == "insufficient_data" and gap["gaps"][0]["indicator"] == "avoided_emissions"
    assert client.post(f"{records}/{saved['request_id']}/cancel", json={"confirmed": True}).json()["status"] == "cancelled"
    assert client.get(f"{BASE}/impact").json()["metrics"]["confirmed_requested_quantity_kg"] == 0


def test_monitoring_upload_annotation_and_confirmation(client, monkeypatch):
    source, stranger = session(client), session(client)
    endpoint = source + "/monitoring/detect"
    headers = {"Content-Type": "image/png"}
    assert client.post(endpoint, params={"farm_id": "SIM-001"}, content=b"").status_code == 415
    assert client.post(endpoint, params={"farm_id": "SIM-001"}, content=b"", headers=headers).status_code == 422
    with monkeypatch.context() as patch:
        patch.setattr(api, "MAX_IMAGE_BYTES", 5)
        assert client.post(endpoint, params={"farm_id": "SIM-001"}, content=png(), headers=headers).status_code == 413
    assert client.post(endpoint, params={"farm_id": "SIM-001"}, content=b"invalid",
                       headers=headers).json()["monitoring"]["error_code"] == "invalid_image"
    partial = client.post(endpoint, params={"farm_id": "SIM-001"}, content=png(), headers=headers).json()
    assert partial["status"] == "ok"
    pending = client.post(endpoint, params={"farm_id": "SIM-001", "whole_farm": True},
                          content=png(), headers=headers).json()
    assert pending["status"] == "awaiting_confirmation"
    assert pending["monitoring"]["pending_review"] is None
    obs = pending["monitoring"]["observation"]
    assert obs["farm_simulated"] and obs["estimated_annual_waste_kg"] == 35
    assert client.get(obs["annotated_image"]).content.startswith(b"\x89PNG")
    assert client.get(stranger + "/images/" + obs["observation_id"]).status_code == 404
    confirmation = {"confirmed": True, "observation_id": obs["observation_id"]}
    assert client.post(stranger + "/monitoring/confirm", json=confirmation).status_code == 409
    farm = f"{BASE}/farms/SIM-001"
    assert client.get(farm).json()["palm_count"] == 303
    assert client.post(source + "/monitoring/confirm", json=confirmation).json()["status"] == "ok"
    assert client.get(farm).json()["provenance"]["palm_count_origin"] == "model_prediction"
    assert client.get(farm).json()["palm_count"] == 1
    assert client.post(source + "/monitoring/confirm", json=confirmation).status_code == 409


def test_http_health_schema_cors_and_redaction(client, monkeypatch):
    assert client.get("/health/live").json()["status"] == "ok"
    assert client.get("/health/ready").json()["database"] == "ok"
    assert client.get("/docs").status_code == 200
    assert f"{BASE}/sessions/{{session_id}}/monitoring/detect" in client.get("/openapi.json").json()["paths"]
    origin = "http://localhost:5173"
    allowed = client.options(f"{BASE}/sessions", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type",
    })
    assert allowed.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-origin" not in client.get("/health/live", headers={"Origin": "https://unknown.test"}).headers
    url = session(client) + "/chat"
    invalid = client.post(url, json={"message": " ", "context": {"key": "fake-secret"}})
    assert invalid.status_code == 422 and "fake-secret" not in invalid.text

    def fail(*args, **kwargs):
        raise RuntimeError("fake-secret")

    monkeypatch.setattr(client.app.state.services.farms, "list_farms", fail)
    error = client.get(f"{BASE}/farms")
    assert error.status_code == 500 and "fake-secret" not in error.text
