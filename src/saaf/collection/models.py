from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_QUANTITY_KG = 2**63 - 1
PickupQuantity = Annotated[int, Field(strict=True, gt=0, le=MAX_QUANTITY_KG)]
RequestStatus = Literal["confirmed", "cancelled"]


class PickupDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    farm_id: str
    requested_quantity_kg: PickupQuantity
    pickup_date: date


class CollectionRequest(PickupDraft):
    request_id: str
    status: RequestStatus
    created_at: datetime
    simulated: Literal[True] = True


class CollectionResult(BaseModel):
    status: Literal["ok", "needs_input", "awaiting_confirmation", "not_found"]
    answer_ar: str
    draft: PickupDraft | None = None
    request: CollectionRequest | None = None
    requests: tuple[CollectionRequest, ...] = ()
    estimated_annual_residue_kg: int | None = None
    missing_information: tuple[str, ...] = ()
    simulated: Literal[True] = True
