import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from saaf.farms import Farm, FarmAlreadyExists, FarmRepository, get_farm_profile
from saaf.farms.seed import load_farm_dataset

SOURCE = Path(__file__).resolve().parents[1] / "data" / "saaf_simulated_farms.json"


@pytest.fixture
def repository(tmp_path):
    return FarmRepository(tmp_path / "db" / "farms.sqlite3")


@pytest.fixture
def raw_dataset():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_dataset_preserves_all_fixture_values(raw_dataset):
    dataset = load_farm_dataset(SOURCE)
    assert len(dataset.farms) == 20
    assert dataset.model_dump() == raw_dataset
    assert all(farm.simulated and farm.est_residue_kg_per_year == farm.palm_count * 35
               for farm in dataset.farms)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("farm_id", "SIM-002", "duplicate farm ID"),
        ("farm_id", " ", "pattern"),
        ("lat", 91, "less than or equal to 90"),
        ("lon", -181, "greater than or equal to -180"),
        ("area_ha", 0, "greater than 0"),
        ("soil_ph", 15, "less than or equal to 14"),
        ("soil_sand_pct", -1, "greater than or equal to 0"),
        ("irrigation_water_saline", 1, "valid boolean"),
        ("soil_ph", None, "missing fixture values"),
        ("palm_count", "303", "valid integer"),
        ("est_residue_kg_per_year", 1, "must equal"),
        ("simulated", False, "simulated farms only"),
    ],
)
def test_bad_fixture_never_writes(repository, tmp_path, raw_dataset, field, value, message):
    raw_dataset["farms"][0][field] = value
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(raw_dataset), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        repository.seed(source)
    assert repository.list_farms() == []


def test_missing_required_field(tmp_path, raw_dataset):
    del raw_dataset["farms"][0]["region"]
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(raw_dataset), encoding="utf-8")
    with pytest.raises(ValueError, match="Field required"):
        load_farm_dataset(source)


def test_auto_initialization_uses_environment(tmp_path, monkeypatch):
    path = tmp_path / "configured" / "farms.sqlite3"
    monkeypatch.setenv("SAAF_SQLITE_PATH", str(path))
    repository = FarmRepository()
    assert path.is_file()
    assert repository.list_farms() == []
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA index_list(farms)").fetchall()


def test_seed_is_persistent_and_keeps_local_edits(repository, raw_dataset):
    assert repository.seed(SOURCE) == 20
    expected = raw_dataset["farms"]
    assert [farm.model_dump(exclude={"provenance"}) for farm in repository.list_farms()] == expected
    imported = get_farm_profile(repository, "SIM-001")
    assert imported.simulated is True
    assert imported.provenance.origin == "seed_dataset"
    assert imported.provenance.seed_file == SOURCE.name
    assert imported.provenance.residue_record_id == "ctx-02"
    edited = repository.update_farm("SIM-001", soil_ph=None)
    assert edited.provenance.origin == "edited_seed"
    assert edited.provenance.seed_file == SOURCE.name
    reopened = FarmRepository(repository.path)
    assert reopened.seed(SOURCE) == 0
    assert reopened.get_farm("SIM-001") == edited


def test_seed_rolls_back_if_a_later_row_fails(repository):
    with closing(sqlite3.connect(repository.path)) as connection:
        connection.executescript("""
            CREATE TRIGGER reject_seed BEFORE INSERT ON farms
            WHEN NEW.farm_id = 'SIM-002'
            BEGIN SELECT RAISE(ABORT, 'test write failure'); END;
        """)
    with pytest.raises(sqlite3.IntegrityError, match="test write failure"):
        repository.seed(SOURCE)
    assert repository.list_farms() == []


def test_crud_and_missing_ids(repository, raw_dataset):
    farm = Farm.model_validate({**raw_dataset["farms"][0], "farm_id": "demo-21"})
    created = repository.create_farm(farm)
    assert created.provenance.origin == "local_simulation"
    assert created.provenance.seed_file is None
    assert get_farm_profile(repository, farm.farm_id) == created
    with pytest.raises(FarmAlreadyExists):
        repository.create_farm(farm)
    updated = repository.update_farm(farm.farm_id, palm_count=10, irrigation_water_saline=None)
    assert updated.est_residue_kg_per_year == 350
    assert updated.irrigation_water_saline is None
    with pytest.raises(ValueError, match="immutable"):
        repository.update_farm(farm.farm_id, simulated=False)
    with pytest.raises(ValueError, match="must equal"):
        repository.update_farm(farm.farm_id, palm_count=3, est_residue_kg_per_year=0)
    assert repository.get_farm(farm.farm_id) == updated
    assert repository.delete_farm(farm.farm_id)
    assert not repository.delete_farm(farm.farm_id)
    assert repository.update_farm(farm.farm_id, soil_ph=8.2) is None
    for farm_id in (None, "", " ", farm.farm_id):
        assert get_farm_profile(repository, farm_id) is None


@pytest.mark.parametrize("region", [None, "الأحساء", "القصيم", "unknown", "' OR 1=1 --"])
def test_region_and_statistics(repository, raw_dataset, region):
    repository.seed(SOURCE)
    rows = [row for row in raw_dataset["farms"] if region is None or row["region"] == region]
    farms = repository.list_farms(region=region)
    assert [farm.farm_id for farm in farms] == [row["farm_id"] for row in rows]
    stats = repository.statistics(region=region)
    assert stats.simulated and stats.region == region
    assert stats.farm_count == len(rows)
    assert stats.total_area_ha == pytest.approx(sum(row["area_ha"] for row in rows))
    assert stats.total_palm_count == sum(row["palm_count"] for row in rows)
    assert stats.total_est_residue_kg_per_year == sum(row["est_residue_kg_per_year"] for row in rows)
