"""Persist confirmed demo requests in the same SQLite database as the farms."""

import sqlite3
from contextlib import closing
from datetime import datetime
from uuid import uuid4

from saaf.farms import FarmRepository

from .models import CollectionRequest, PickupDraft

_SCHEMA = """
CREATE TABLE IF NOT EXISTS collection_requests (
    request_id TEXT NOT NULL PRIMARY KEY,
    farm_id TEXT NOT NULL REFERENCES farms(farm_id),
    requested_quantity_kg INTEGER NOT NULL CHECK (requested_quantity_kg > 0),
    pickup_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled')),
    created_at TEXT NOT NULL,
    simulated INTEGER NOT NULL CHECK (simulated = 1)
);
CREATE UNIQUE INDEX IF NOT EXISTS collection_pickup_idx
ON collection_requests(farm_id, pickup_date, requested_quantity_kg);
CREATE INDEX IF NOT EXISTS collection_farm_idx ON collection_requests(farm_id);
"""


class CollectionRepository:
    def __init__(self, farms: FarmRepository) -> None:
        self.path = farms.path
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def confirm(self, draft: PickupDraft, created_at: datetime) -> CollectionRequest:
        """Atomically insert or return the matching request, even after cancellation."""
        draft = PickupDraft.model_validate(draft.model_dump())
        key = (draft.farm_id, draft.requested_quantity_kg, draft.pickup_date.isoformat())
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO collection_requests VALUES (?, ?, ?, ?, 'confirmed', ?, 1)
                   ON CONFLICT DO NOTHING""",
                (f"COL-{uuid4().hex.upper()}", *key, created_at.isoformat()),
            )
            row = connection.execute(
                """SELECT * FROM collection_requests
                   WHERE farm_id = ? AND requested_quantity_kg = ? AND pickup_date = ?""", key,
            ).fetchone()
            return CollectionRequest.model_validate(dict(row))

    def get(self, request_id: str, *, farm_id: str) -> CollectionRequest | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM collection_requests WHERE request_id = ? AND farm_id = ?",
                (request_id, farm_id),
            ).fetchone()
        return CollectionRequest.model_validate(dict(row)) if row is not None else None

    def list(self, *, farm_id: str | None = None, region: str | None = None) -> list[CollectionRequest]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT r.* FROM collection_requests r JOIN farms f ON r.farm_id = f.farm_id
                   WHERE (? IS NULL OR r.farm_id = ?) AND (? IS NULL OR f.region = ?)
                   ORDER BY r.created_at, r.request_id""", (farm_id, farm_id, region, region),
            ).fetchall()
        return [CollectionRequest.model_validate(dict(row)) for row in rows]

    def cancel(self, request_id: str, *, farm_id: str) -> CollectionRequest | None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE collection_requests SET status = 'cancelled' WHERE request_id = ? AND farm_id = ?",
                (request_id, farm_id),
            )
        return self.get(request_id, farm_id=farm_id)
