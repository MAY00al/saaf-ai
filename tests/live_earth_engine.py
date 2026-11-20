"""Opt-in HTTP test over a publicly documented agricultural site."""

import base64
import os

import pytest
from fastapi.testclient import TestClient

from saaf.api.app import create_app
from saaf.farms import FarmRepository
from saaf.geospatial.satellite import EarthEngineProvider
from saaf.providers import load_environment

# A bounded sampling window around Rothamsted's published point, not a parcel survey.
# https://www.era.rothamsted.ac.uk/experiment/rbk1
BOUNDARY = {
    "boundary": {"type": "Polygon", "coordinates": [[
        [-0.3736, 51.8091], [-0.3724, 51.8091], [-0.3724, 51.8098],
        [-0.3736, 51.8098], [-0.3736, 51.8091],
    ]]},
    "longitude": -0.37301,
    "latitude": 51.80946,
}
QUERY = {
    "start_date": "2026-05-01", "end_date": "2026-07-31",
    "max_scene_cloud_pct": 80, "min_clear_fraction": 0.5, "limit": 3,
}


def test_live_earth_engine(tmp_path, monkeypatch):
    load_environment()
    if not os.getenv("SAAF_EE_PROJECT"):
        pytest.skip("Set SAAF_EE_PROJECT and authenticate Earth Engine to run this test.")
    database = tmp_path / "farm.sqlite3"
    monkeypatch.setenv("SAAF_SQLITE_PATH", str(database))
    FarmRepository(database).seed()
    provider = EarthEngineProvider()
    with TestClient(create_app(cors_origins=[], satellite_provider=provider)) as client:
        root = "/api/v1/farms/SIM-001"
        assert client.put(root + "/boundary", json=BOUNDARY).status_code == 200
        for mode in ("imagery", "ndvi", "history"):
            response = client.get(f"{root}/satellite/{mode}", params=QUERY)
            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "ok", payload["status"]
            assert payload["provenance"]["collection"] == "COPERNICUS/S2_SR_HARMONIZED"
            scenes = payload["scenes"]
            assert scenes
            assert all(scene["farm_valid_fraction"] >= QUERY["min_clear_fraction"] for scene in scenes)
            if mode == "history":
                assert 1 < len(scenes) <= QUERY["limit"]
                assert [scene["acquired_at"] for scene in scenes] == sorted(scene["acquired_at"] for scene in scenes)
                assert payload["preview"] is None
            else:
                assert base64.b64decode(payload["preview"]["data"]).startswith(b"\x89PNG")
            if mode != "imagery":
                assert all(-1 <= scene["ndvi"]["minimum"] <= scene["ndvi"]["mean"]
                           <= scene["ndvi"]["maximum"] <= 1 for scene in scenes)
            print(mode, [(scene["acquired_at"], scene["scene_cloud_pct"],
                          scene["farm_valid_fraction"], scene["ndvi"]) for scene in scenes])
