"""Aggregate registered farms and simulated pickup requests."""

from typing import Literal

from pydantic import BaseModel

from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository


class RequestCounts(BaseModel):
    confirmed: int = 0
    cancelled: int = 0


class ImpactMetrics(BaseModel):
    region: str | None
    registered_farms: int
    palm_trees: int
    estimated_annual_waste_kg: int
    confirmed_requested_quantity_kg: int
    requests_by_status: RequestCounts
    requests_by_region_and_status: dict[str, RequestCounts]
    simulated: Literal[True] = True


def calculate_metrics(
    farms: FarmRepository, requests: CollectionRepository, *, region: str | None = None,
) -> ImpactMetrics:
    profiles = {farm.farm_id: farm for farm in farms.list_farms(region=region)}
    by_region = {name: RequestCounts() for name in sorted({farm.region for farm in profiles.values()})}
    total = RequestCounts()
    quantity = 0
    for request in requests.list(region=region):
        profile = profiles.get(request.farm_id)
        if profile is None:
            continue
        counts = by_region[profile.region]
        if request.status == "confirmed":
            counts.confirmed += 1
            total.confirmed += 1
            quantity += request.requested_quantity_kg
        else:
            counts.cancelled += 1
            total.cancelled += 1
    return ImpactMetrics(
        region=region, registered_farms=len(profiles),
        palm_trees=sum(farm.palm_count for farm in profiles.values()),
        estimated_annual_waste_kg=sum(farm.est_residue_kg_per_year for farm in profiles.values()),
        confirmed_requested_quantity_kg=quantity, requests_by_status=total,
        requests_by_region_and_status=by_region,
    )
