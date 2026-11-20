from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from fastapi.testclient import TestClient

from saaf.api.app import create_app
from saaf.farms import FarmRepository
from saaf.geospatial.geometry import FarmBoundaryInput, GeoPolygon
from saaf.geospatial.repository import GeographyRepository
from saaf.geospatial.satellite import (
    EarthEngineProvider, NDVIStats, SatelliteBatch, SatelliteFailure, SatelliteQuery, Scene, ndvi_band,
)
from saaf.geospatial.service import GeoMonitoring

DATA = Path(__file__).resolve().parents[1] / "data"
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]]}


@pytest.fixture
def farms(tmp_path):
    repository = FarmRepository(tmp_path / "farms.sqlite3")
    repository.seed(DATA / "saaf_simulated_farms.json")
    return repository


@pytest.mark.parametrize("ring", [
    [[0, 0], [0, 1], [1, 1], [1, 0]],
    [[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]],
    [[0, 0], [181, 1], [0, 1], [0, 0]],
    [[0, 0], [1, 91], [0, 1], [0, 0]],
    [[0, 0], [1, 1], [2, 2], [0, 0]],
    [[179, 0], [-179, 0], [-179, 1], [179, 1], [179, 0]],
])
def test_rejects_invalid_polygon(ring):
    with pytest.raises(ValueError):
        GeoPolygon(type="Polygon", coordinates=[ring])


def test_geodesic_area_and_holes():
    boundary = GeoPolygon.model_validate(SQUARE)
    assert boundary.area_ha() == pytest.approx(1.2309, rel=0.001)
    hole = [[0.0002, 0.0002], [0.0006, 0.0002], [0.0006, 0.0006],
            [0.0002, 0.0006], [0.0002, 0.0002]]
    with_hole = GeoPolygon(type="Polygon", coordinates=[SQUARE["coordinates"][0], hole])
    assert with_hole.area_ha() == pytest.approx(boundary.area_ha() * 0.84, rel=0.001)


def test_registration_uses_user_point_and_preserves_seeded_profile(farms):
    geo = GeographyRepository(farms)
    original = farms.get_farm("SIM-001")
    assert geo.get("SIM-001").registered_boundary is None
    with pytest.raises(ValueError):
        FarmBoundaryInput(boundary=SQUARE, longitude=0.0001)
    with pytest.raises(ValueError):
        FarmBoundaryInput(boundary=SQUARE, longitude=1, latitude=1)
    geo.register("SIM-001", FarmBoundaryInput(boundary=SQUARE, longitude=0.0003, latitude=0.0004))
    persisted = GeographyRepository(FarmRepository(farms.path)).get("SIM-001")
    assert persisted.simulated_profile
    assert persisted.stored_location == (original.lon, original.lat)
    assert persisted.registered_boundary.location == (0.0003, 0.0004)
    assert persisted.registered_boundary.location_origin == "user_provided"
    assert not persisted.registered_boundary.location_verified
    assert farms.get_farm("SIM-001") == original


class Scalar:
    def __init__(self, value):
        self.value = value

    def add(self, other):
        return Scalar(self.value + other.value)

    def subtract(self, other):
        return Scalar(self.value - other.value)

    def gt(self, value):
        return self.value > value

    def updateMask(self, mask):
        return self if mask else Scalar(None)

    def divide(self, other):
        return Scalar(self.value / other.value if other.value is not None else None)

    def rename(self, name):
        assert name == "NDVI"
        return self


@pytest.mark.parametrize("red,nir,expected", [(2000, 6000, 0.5), (6000, 2000, -0.5), (0, 0, None)])
def test_ndvi_uses_b8_b4_and_masks_zero_denominator(red, nir, expected):
    image = SimpleNamespace(select=lambda name: Scalar({"B4": red, "B8": nir}[name]))
    assert ndvi_band(image).value == expected


class MockSatellite:
    def __init__(self, failure=None, empty=False):
        self.calls = []
        self.failure = failure
        self.empty = empty

    def fetch(self, boundary, options, mode):
        self.calls.append((boundary, options, mode))
        if self.failure:
            raise self.failure
        if self.empty:
            return SatelliteBatch(scenes=())
        return SatelliteBatch(scenes=(Scene(
            scene_id="fixture-only", acquired_at=datetime(2026, 1, 12, tzinfo=timezone.utc),
            scene_cloud_pct=20, farm_valid_fraction=0.8, vegetation_fraction_of_valid=0.6,
            ndvi=None if mode == "imagery" else NDVIStats(mean=0.4, minimum=0.2, maximum=0.5),
        ),))


@pytest.mark.parametrize("failure,expected", [
    (SatelliteFailure("authentication_failed"), "authentication_failed"),
    (SatelliteFailure("not_configured"), "not_configured"),
    (RuntimeError("sensitive credential value"), "provider_unavailable"),
    (None, "no_imagery"),
])
def test_satellite_failures_have_no_fabricated_data_or_secrets(farms, failure, expected):
    repo = GeographyRepository(farms)
    provider = MockSatellite(failure=failure, empty=True)
    service = GeoMonitoring(repo, provider)
    assert service.inspect("SIM-001", "ndvi", SatelliteQuery()).status == "boundary_required"
    assert not provider.calls
    repo.register("SIM-001", FarmBoundaryInput(boundary=SQUARE))
    result = service.inspect("SIM-001", "ndvi", SatelliteQuery())
    assert result.status == expected
    assert not result.scenes and result.preview is None
    assert "sensitive" not in result.model_dump_json()


def test_earth_engine_authentication_failure_is_mapped(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("403 Permission denied, private credential")

    monkeypatch.delenv("SAAF_EE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.setitem(sys.modules, "ee", SimpleNamespace(Initialize=fail))
    with pytest.raises(SatelliteFailure, match="authentication_failed"):
        EarthEngineProvider("demo-project").fetch(GeoPolygon.model_validate(SQUARE), SatelliteQuery(), "ndvi")


def test_geospatial_http_and_monitoring_agent(farms, monkeypatch):
    monkeypatch.setenv("SAAF_SQLITE_PATH", str(farms.path))
    satellite = MockSatellite()
    with TestClient(create_app(cors_origins=[], satellite_provider=satellite)) as client:
        root = "/api/v1/farms/SIM-001"
        assert client.get(root + "/satellite/ndvi").json()["status"] == "boundary_required"
        assert not satellite.calls
        assert client.get(root + "/boundary/area").status_code == 404
        assert client.put(root + "/boundary", json={"boundary": SQUARE}).status_code == 200
        area = client.post("/api/v1/geography/area", json=SQUARE).json()
        assert client.get(root + "/boundary/area").json() == area
        assert client.get(root + "/boundary").json()["registered_boundary"]["origin"] == "user_provided"
        assert client.get(root).json()["area_ha"] != area["area_ha"]
        assert client.get(root + "/satellite/history?start_date=2026-02-01&end_date=2026-01-01").status_code == 422
        response = client.get(root + "/satellite/history?start_date=2026-01-01&end_date=2026-01-31&limit=2")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "ok" and result["scenes"][0]["ndvi"]["mean"] == 0.4
        assert result["provenance"]["reflectance_resolution_m"] == 10
        assert result["scenes"][0]["vegetation_fraction_of_valid"] == 0.6
        assert satellite.calls[-1][1].limit == 2
        assert client.get(root + "/satellite/imagery").json()["scenes"][0]["ndvi"] is None
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        chat_url = f"/api/v1/sessions/{session_id}/chat"
        reply = client.post(chat_url, json={"message": "احسب NDVI", "farm_id": "SIM-001"}).json()
        assert reply["intent"] == "monitoring" and reply["monitoring"]["vegetation"]["status"] == "ok"
        assert reply["monitoring"]["observation"] is None
        area_reply = client.post(chat_url, json={"message": "كم مساحة المزرعة؟"}).json()
        assert area_reply["monitoring"]["geography"]["registered_boundary"]["area_ha"] == area["area_ha"]
        call_count = len(satellite.calls)
        refusal = client.post(chat_url, json={"message": "عد النخيل باستخدام Sentinel-2"}).json()
        assert refusal["status"] == "needs_input" and len(satellite.calls) == call_count
        waste = client.get(root + "/waste-estimate").json()
        assert waste["count_origin"] == "simulation_estimate"
        assert waste["estimated_annual_waste_kg"] == 303 * 35
        assert waste["factor_record_id"] == "ctx-02"
