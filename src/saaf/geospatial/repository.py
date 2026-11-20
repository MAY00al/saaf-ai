"""Store user boundaries separately from simulation profiles."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from saaf.farms import FarmRepository
from .geometry import FarmBoundaryInput, GeoPolygon, Position


class FarmMissing(LookupError):
    pass


class RegisteredBoundary(BaseModel):
    geometry: GeoPolygon
    location: Position
    location_origin: Literal["user_provided", "derived_from_user_boundary"]
    area_ha: float
    area_method: Literal["WGS84_ellipsoidal"] = "WGS84_ellipsoidal"
    origin: Literal["user_provided"] = "user_provided"
    location_verified: Literal[False] = False
    updated_at: datetime


class FarmGeography(BaseModel):
    farm_id: str
    simulated_profile: bool
    stored_location: Position
    stored_location_origin: Literal["simulated"] = "simulated"
    stored_area_ha: float
    registered_boundary: RegisteredBoundary | None = None


class GeographyRepository:
    def __init__(self, farms: FarmRepository) -> None:
        self.farms = farms
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS farm_boundaries (
                    farm_id TEXT NOT NULL PRIMARY KEY REFERENCES farms(farm_id) ON DELETE CASCADE,
                    input_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.farms.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def register(self, farm_id: str, data: FarmBoundaryInput) -> FarmGeography:
        data = FarmBoundaryInput.model_validate(data.model_dump())
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM farms WHERE farm_id = ?", (farm_id,)).fetchone() is None:
                raise FarmMissing
            connection.execute("""
                INSERT INTO farm_boundaries VALUES (?, ?, ?)
                ON CONFLICT(farm_id) DO UPDATE SET input_json = excluded.input_json,
                    updated_at = excluded.updated_at
            """, (farm_id, data.model_dump_json(), datetime.now(timezone.utc).isoformat()))
            return self._read(connection, farm_id)

    def get(self, farm_id: str) -> FarmGeography:
        with closing(self._connect()) as connection:
            return self._read(connection, farm_id)

    def _read(self, connection: sqlite3.Connection, farm_id: str) -> FarmGeography:
        row = connection.execute("""
            SELECT f.lon, f.lat, f.area_ha, f.simulated, g.input_json, g.updated_at
            FROM farms f LEFT JOIN farm_boundaries g ON f.farm_id = g.farm_id
            WHERE f.farm_id = ?
        """, (farm_id,)).fetchone()
        if row is None:
            raise FarmMissing
        boundary = None
        if row["input_json"] is not None:
            data = FarmBoundaryInput.model_validate_json(row["input_json"])
            point = data.boundary.polygon().representative_point()
            location = (point.x, point.y) if data.longitude is None else (data.longitude, data.latitude)
            boundary = RegisteredBoundary(
                geometry=data.boundary, location=location,
                location_origin="derived_from_user_boundary" if data.longitude is None else "user_provided",
                area_ha=data.boundary.area_ha(), updated_at=row["updated_at"],
            )
        return FarmGeography(
            farm_id=farm_id, simulated_profile=bool(row["simulated"]),
            stored_location=(row["lon"], row["lat"]), stored_area_ha=row["area_ha"],
            registered_boundary=boundary,
        )
