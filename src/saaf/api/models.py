from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from saaf.agents.recommendation import RecommendationResponse
from saaf.agents.impact import ImpactResult
from saaf.agents.tools import FarmId
from saaf.collection.models import CollectionResult, PickupDraft, PickupQuantity
from saaf.monitoring.models import MonitoringResult
from saaf.orchestration.contracts import Capability, Intent, Outcome

Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Region = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ObservationId = Annotated[str, StringConstraints(pattern=r"^OBS-[A-F0-9]{32}$")]
CollectionId = Annotated[str, StringConstraints(pattern=r"^COL-[A-F0-9]{32}$")]


class InputModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class ChatInput(InputModel):
    message: Message
    farm_id: FarmId | None = None


class FarmPatch(InputModel):
    region: Region | None = None
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    area_ha: Annotated[float, Field(gt=0)] | None = None
    soil_sand_pct: Annotated[float, Field(ge=0, le=100)] | None = None
    soil_ph: Annotated[float, Field(ge=0, le=14)] | None = None
    irrigation_system: Region | None = None
    irrigation_water_saline: bool | None = None
    current_disposal: Region | None = None

    @field_validator("region", "lat", "lon", "area_ha")
    @classmethod
    def required_value(cls, value):
        if value is None:
            raise ValueError("field cannot be null")
        return value


class PickupInput(InputModel):
    farm_id: FarmId
    requested_quantity_kg: PickupQuantity


class Confirmation(InputModel):
    confirmed: bool

    @field_validator("confirmed")
    @classmethod
    def explicit_confirmation(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("explicit confirmation required")
        return value


class PickupConfirmation(Confirmation):
    draft: PickupDraft


class CountConfirmation(Confirmation):
    observation_id: ObservationId


class ImpactInput(InputModel):
    message: Message
    region: Region | None = None


class SessionInfo(BaseModel):
    session_id: UUID
    farm_id: str | None
    expires_at: datetime


class ChatResponse(BaseModel):
    intent: Intent
    status: Outcome
    answer_ar: str
    session: SessionInfo
    candidate_intents: tuple[Capability, ...] = ()
    recommendation: RecommendationResponse | None = None
    collection: CollectionResult | None = None
    impact: ImpactResult | None = None
    monitoring: MonitoringResult | None = None


class Error(BaseModel):
    code: str
    message_ar: str


class ErrorResponse(BaseModel):
    error: Error


class Health(BaseModel):
    status: str
    database: str | None = None
    vision_weights_configured: bool | None = None
