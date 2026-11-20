from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from saaf.farms.models import MAX_PALM_COUNT, RESIDUE_KG_PER_PALM_PER_YEAR

PalmCount = Annotated[int, Field(strict=True, ge=0, le=MAX_PALM_COUNT)]


class Detection(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    confidence: float = Field(ge=0, le=1)
    xyxy: tuple[float, float, float, float]

    @model_validator(mode="after")
    def verify_box(self) -> "Detection":
        x1, y1, x2, y2 = self.xyxy
        if not (0 <= x1 < x2 and 0 <= y1 < y2):
            raise ValueError("invalid box")
        return self


class CountReview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str
    farm_id: str
    predicted_count: PalmCount
    previous_count: PalmCount
    previous_observation_id: str | None
    model_id: str
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PalmObservation(BaseModel):
    observation_id: str
    farm_id: str
    farm_simulated: Literal[True] = True
    count_origin: Literal["model_prediction"] = "model_prediction"
    image_sha256: str
    model_id: str
    annotated_image: str
    image_size: tuple[int, int]
    confidence_threshold: float
    detections: tuple[Detection, ...]
    detected_count: PalmCount
    estimated_annual_waste_kg: int
    waste_factor_kg_per_palm_per_year: Literal[35] = RESIDUE_KG_PER_PALM_PER_YEAR
    waste_factor_record_id: Literal["ctx-02"] = "ctx-02"
    whole_farm_attested: bool


class MonitoringResult(BaseModel):
    status: Literal["ok", "needs_input", "unavailable", "awaiting_confirmation"]
    answer_ar: str
    observation: PalmObservation | None = None
    pending_review: CountReview | None = None
    updated_farm_id: str | None = None
    error_code: Literal["missing_image", "invalid_image", "missing_model", "inference_failed", "stale_review"] | None = None
