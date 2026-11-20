import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from saaf.agents.monitoring import MonitoringAgent
from saaf.farms import FarmRepository
from saaf.monitoring.inference import InvalidImage, MonitoringSettings, YoloDetector, load_image
from saaf.monitoring.models import Detection
from saaf.orchestration.graph import Orchestrator

DATA = Path(__file__).resolve().parents[1] / "data"


class Detector:
    model_id = "fixture-detector"

    def predict(self, image, settings):
        assert image.mode == "RGB"
        return (
            Detection(confidence=0.8, xyxy=(4, 4, 18, 30)),
            Detection(confidence=0.6, xyxy=(20, 20, 44, 40)),
            Detection(confidence=0.1, xyxy=(40, 40, 49, 49)),
        )


@pytest.fixture
def services(tmp_path):
    farms = FarmRepository(tmp_path / "farms.sqlite3")
    farms.seed(DATA / "saaf_simulated_farms.json")
    settings = MonitoringSettings(output_dir=tmp_path / "results", confidence=0.5)
    image_path = tmp_path / "fixture.png"
    Image.new("RGB", (64, 64), "white").save(image_path)
    return farms, settings, image_path


def test_image_validation(tmp_path, services):
    _, _, valid = services
    image, digest = load_image(valid)
    assert image.size == (64, 64) and len(digest) == 64
    invalid = tmp_path / "corrupt.jpg"
    invalid.write_bytes(b"bad image")
    small = tmp_path / "small.png"
    Image.new("RGB", (16, 16)).save(small)
    webp = tmp_path / "unsupported.bmp"
    Image.new("RGB", (64, 64)).save(webp)
    for path in (invalid, small, webp, tmp_path):
        with pytest.raises(InvalidImage):
            load_image(path)


def test_prediction_processing_estimate_and_annotation(services):
    farms, settings, image = services
    result = MonitoringAgent(farms, settings, Detector()).inspect_palms("SIM-001", image)
    assert result.status == "ok" and result.pending_review is None
    observation = result.observation
    assert observation.detected_count == 2
    assert observation.estimated_annual_waste_kg == 70 and observation.waste_factor_record_id == "ctx-02"
    assert observation.farm_simulated and observation.count_origin == "model_prediction"
    assert [box.confidence for box in observation.detections] == [0.8, 0.6]
    assert observation.detections[0].xyxy == (4, 4, 18, 30)
    with Image.open(observation.annotated_image) as marked:
        assert marked.size == observation.image_size and marked.getpixel((4, 4)) != (255, 255, 255)
    assert farms.get_farm("SIM-001").palm_count == 303


def test_missing_image_model_and_unknown_farm(services):
    farms, settings, image = services
    graph = Orchestrator(None, monitoring=MonitoringAgent(farms, settings))
    assert graph.run("رصد النخيل", farm_id="SIM-001").monitoring.error_code == "missing_image"
    assert graph.run("رصد النخيل", farm_id="SIM-001", image_path=image).monitoring.error_code == "missing_model"
    assert graph.run("رصد النخيل", farm_id="SIM-999", image_path=image).status == "needs_input"
    assert graph.run("رصد النخيل", farm_id="SIM-001", image_path=image.with_suffix(".jpg")).monitoring.error_code == "invalid_image"


def test_graph_requires_whole_coverage_explicit_confirmation_and_matching_farm(services):
    farms, settings, image = services
    graph = Orchestrator(None, monitoring=MonitoringAgent(farms, settings, Detector()))
    partial = graph.run("عد النخيل", farm_id="SIM-001", image_path=image)
    assert graph.run("أؤكد تحديث العدد", context=partial.context).status == "needs_input"
    pending = graph.run("تعدون النخل؟", farm_id="SIM-001", image_path=image, whole_farm=True)
    assert pending.status == "awaiting_confirmation"
    assert graph.run("أؤكد تحديث العدد", context=pending.context, farm_id="SIM-002").status == "needs_input"
    assert graph.run("أؤكد تحديث العدد", context=pending.context, image_path=image).status == "needs_input"
    assert farms.get_farm("SIM-001").palm_count == 303
    saved = graph.run("أؤكد تحديث العدد", context=pending.context)
    assert saved.status == "ok" and saved.context.count_review is None
    assert graph.run("أؤكد تحديث العدد", context=pending.context).status == "ok"
    profile = FarmRepository(farms.path).get_farm("SIM-001")
    assert profile.simulated and profile.palm_count == 2 and profile.est_residue_kg_per_year == 70
    assert profile.provenance.palm_count_origin == "model_prediction"
    assert profile.provenance.palm_count_observation_id == pending.monitoring.observation.observation_id
    assert farms.update_farm("SIM-001", soil_ph=8).provenance.palm_count_origin == "model_prediction"
    assert farms.update_farm("SIM-001", palm_count=4).provenance.palm_count_origin == "simulation"
    assert graph.run("أؤكد تحديث العدد", context=pending.context).monitoring.error_code == "stale_review"


def test_pending_review_rejects_stale_baseline(services):
    farms, settings, image = services
    agent = MonitoringAgent(farms, settings, Detector())
    pending = agent.inspect_palms("SIM-001", image, whole_farm=True)
    farms.update_farm("SIM-001", palm_count=9)
    assert agent.confirm_count("SIM-001", pending.pending_review).error_code == "stale_review"
    assert farms.get_farm("SIM-001").palm_count == 9


@pytest.mark.parametrize("label", ["Date-Palm-Crown", "palm_tree"])
def test_yolo_adapter_uses_cpu_and_palm_class_only(tmp_path, monkeypatch, label):
    weights = tmp_path / "checkpoint.pt"
    weights.write_bytes(b"fixture")
    calls = []

    class Tensor(list):
        def cpu(self):
            return self

        def tolist(self):
            return list(self)

    class FakeYolo:
        task = "detect"
        names = {0: "other", 1: label}

        def __init__(self, filename, task):
            assert Path(filename) == weights and task == "detect"

        def predict(self, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=SimpleNamespace(
                xyxy=Tensor([[1, 1, 6, 6]]), conf=Tensor([0.7]),
            ))]

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYolo))
    detector = YoloDetector(weights)
    settings = MonitoringSettings(weights=weights, confidence=0.4, image_size=320)
    assert detector.predict(object(), settings)[0].confidence == 0.7
    assert calls[0]["device"] == "cpu" and calls[0]["classes"] == [1]
    assert calls[0]["conf"] == 0.4 and calls[0]["imgsz"] == 320
    assert "sha256:" in detector.model_id


def test_capped_detection_output_cannot_update_farm(services):
    farms, settings, image = services
    capped = settings.model_copy(update={"max_detections": 3})
    result = MonitoringAgent(farms, capped, Detector()).inspect_palms("SIM-001", image, whole_farm=True)
    assert result.status == "ok" and result.pending_review is None
    assert farms.get_farm("SIM-001").palm_count == 303
