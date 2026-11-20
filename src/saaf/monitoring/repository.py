"""Apply a reviewed prediction and its provenance in a single transaction."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from saaf.farms import FarmRepository
from saaf.farms.models import RESIDUE_KG_PER_PALM_PER_YEAR

from .models import CountReview


def apply_count_review(farms: FarmRepository, review: CountReview) -> bool:
    review = CountReview.model_validate(review.model_dump())
    with closing(sqlite3.connect(farms.path)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """SELECT farm_id, predicted_count, previous_count, model_id, image_sha256, active
               FROM farm_palm_observations WHERE observation_id = ?""",
            (review.observation_id,),
        ).fetchone()
        if existing is not None:
            return existing == (
                review.farm_id, review.predicted_count, review.previous_count,
                review.model_id, review.image_sha256, 1,
            )
        baseline = connection.execute(
            """SELECT f.palm_count, o.observation_id FROM farms f
               LEFT JOIN farm_palm_observations o ON o.farm_id = f.farm_id AND o.active = 1
               WHERE f.farm_id = ?""", (review.farm_id,),
        ).fetchone()
        if baseline != (review.previous_count, review.previous_observation_id):
            return False
        connection.execute(
            """UPDATE farms SET palm_count = ?, est_residue_kg_per_year = ?,
               origin = CASE WHEN seed_file IS NULL THEN 'local_simulation' ELSE 'edited_seed' END
               WHERE farm_id = ?""",
            (review.predicted_count, review.predicted_count * RESIDUE_KG_PER_PALM_PER_YEAR,
             review.farm_id),
        )
        connection.execute(
            "UPDATE farm_palm_observations SET active = 0 WHERE farm_id = ? AND active = 1",
            (review.farm_id,),
        )
        connection.execute(
            """INSERT INTO farm_palm_observations
               (observation_id, farm_id, predicted_count, previous_count, model_id, image_sha256, confirmed_at, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (review.observation_id, review.farm_id, review.predicted_count, review.previous_count,
             review.model_id, review.image_sha256, datetime.now(timezone.utc).isoformat()),
        )
        return True
