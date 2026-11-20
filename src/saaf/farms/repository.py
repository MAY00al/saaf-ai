"""SQLite persistence for simulated farm profiles."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .models import RESIDUE_KG_PER_PALM_PER_YEAR, Farm, FarmProfile, FarmProvenance, FarmStatistics
from .seed import DEFAULT_SEED_PATH, load_farm_dataset

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS farms (
    farm_id TEXT NOT NULL PRIMARY KEY,
    region TEXT NOT NULL,
    lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
    area_ha REAL NOT NULL CHECK (area_ha > 0),
    palm_count INTEGER NOT NULL CHECK (palm_count >= 0),
    est_residue_kg_per_year INTEGER NOT NULL
        CHECK (est_residue_kg_per_year = palm_count * {RESIDUE_KG_PER_PALM_PER_YEAR}),
    soil_sand_pct REAL CHECK (soil_sand_pct BETWEEN 0 AND 100),
    soil_ph REAL CHECK (soil_ph BETWEEN 0 AND 14),
    irrigation_system TEXT,
    irrigation_water_saline INTEGER CHECK (irrigation_water_saline IN (0, 1)),
    current_disposal TEXT,
    simulated INTEGER NOT NULL CHECK (simulated = 1),
    origin TEXT NOT NULL CHECK (origin IN ('seed_dataset', 'edited_seed', 'local_simulation')),
    seed_file TEXT,
    CHECK ((origin = 'local_simulation') = (seed_file IS NULL))
);
CREATE INDEX IF NOT EXISTS farms_region_idx ON farms (region);
"""
_FARM_FIELDS = tuple(Farm.model_fields)
_STORED_FIELDS = (*_FARM_FIELDS, "origin", "seed_file")
_INSERT = (
    f"INSERT INTO farms ({', '.join(_STORED_FIELDS)}) "
    f"VALUES ({', '.join(':' + name for name in _STORED_FIELDS)})"
)
_UPDATE = "UPDATE farms SET " + ", ".join(
    f"{name} = :{name}" for name in _STORED_FIELDS if name != "farm_id"
) + " WHERE farm_id = :farm_id"


class FarmAlreadyExists(ValueError):
    """A farm already uses the requested ID."""


def _profile(row: sqlite3.Row) -> FarmProfile:
    data = {name: row[name] for name in _FARM_FIELDS}
    data["simulated"] = bool(data["simulated"])
    if data["irrigation_water_saline"] is not None:
        data["irrigation_water_saline"] = bool(data["irrigation_water_saline"])
    return FarmProfile(
        **data, provenance=FarmProvenance(origin=row["origin"], seed_file=row["seed_file"]),
    )


class FarmRepository:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path if path is not None else os.getenv("SAAF_SQLITE_PATH") or "var/saaf.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def seed(self, path: Path = DEFAULT_SEED_PATH) -> int:
        """Insert missing fixture rows in one transaction and preserve local edits."""
        dataset = load_farm_dataset(path)
        rows = [
            dict(farm.model_dump(), origin="seed_dataset", seed_file=path.name)
            for farm in dataset.farms
        ]
        with closing(self._connect()) as connection, connection:
            cursor = connection.executemany(_INSERT + " ON CONFLICT(farm_id) DO NOTHING", rows)
            return cursor.rowcount

    def create_farm(self, farm: Farm) -> FarmProfile:
        data = farm.model_dump(include=set(_FARM_FIELDS))
        farm = Farm.model_validate(data)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                _INSERT + " ON CONFLICT(farm_id) DO NOTHING",
                dict(data, origin="local_simulation", seed_file=None),
            )
            if cursor.rowcount == 0:
                raise FarmAlreadyExists(f"farm already exists: {farm.farm_id}")
        return FarmProfile(
            **data, provenance=FarmProvenance(origin="local_simulation", seed_file=None),
        )

    def get_farm(self, farm_id: str | None) -> FarmProfile | None:
        if not farm_id or not farm_id.strip():
            return None
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM farms WHERE farm_id = ?", (farm_id,)).fetchone()
        return _profile(row) if row is not None else None

    def update_farm(self, farm_id: str, **changes: object) -> FarmProfile | None:
        """Apply changes atomically and recalculate residue when palm count changes."""
        if {"farm_id", "simulated"} & changes.keys():
            raise ValueError("farm_id and simulated are immutable")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM farms WHERE farm_id = ?", (farm_id,)).fetchone()
            if row is None:
                return None
            current = _profile(row)
            original = current.model_dump(exclude={"provenance"})
            updated = {**original, **changes}
            count = changes.get("palm_count")
            if type(count) is int and "est_residue_kg_per_year" not in changes:
                updated["est_residue_kg_per_year"] = count * RESIDUE_KG_PER_PALM_PER_YEAR
            data = Farm.model_validate(updated).model_dump()
            if data == original:
                return current
            seed_file = current.provenance.seed_file
            origin = "edited_seed" if seed_file is not None else "local_simulation"
            connection.execute(_UPDATE, dict(data, origin=origin, seed_file=seed_file))
        return FarmProfile(**data, provenance=FarmProvenance(origin=origin, seed_file=seed_file))

    def delete_farm(self, farm_id: str) -> bool:
        with closing(self._connect()) as connection, connection:
            return connection.execute("DELETE FROM farms WHERE farm_id = ?", (farm_id,)).rowcount == 1

    def list_farms(self, *, region: str | None = None) -> list[FarmProfile]:
        with closing(self._connect()) as connection:
            if region is None:
                rows = connection.execute("SELECT * FROM farms ORDER BY farm_id").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM farms WHERE region = ? ORDER BY farm_id", (region,),
                ).fetchall()
        return [_profile(row) for row in rows]

    def statistics(self, *, region: str | None = None) -> FarmStatistics:
        farms = self.list_farms(region=region)
        return FarmStatistics(
            region=region,
            farm_count=len(farms),
            total_area_ha=sum((farm.area_ha for farm in farms), 0.0),
            total_palm_count=sum(farm.palm_count for farm in farms),
            total_est_residue_kg_per_year=sum(farm.est_residue_kg_per_year for farm in farms),
        )


def get_farm_profile(repository: FarmRepository, farm_id: str | None) -> FarmProfile | None:
    """Return typed farm context, or None for a missing or unknown ID."""
    return repository.get_farm(farm_id)
