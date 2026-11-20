"""Farm data contracts and residue estimation for the simulated MVP."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

RESIDUE_KG_PER_PALM_PER_YEAR = 35
MAX_PALM_COUNT = (2**63 - 1) // RESIDUE_KG_PER_PALM_PER_YEAR
NonBlank = Annotated[str, StringConstraints(pattern=r"\S")]


class Farm(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False)

    farm_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
    region: NonBlank
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    area_ha: Annotated[float, Field(gt=0)]
    palm_count: Annotated[int, Field(ge=0, le=MAX_PALM_COUNT)]
    est_residue_kg_per_year: Annotated[int, Field(ge=0)]
    soil_sand_pct: Annotated[float, Field(ge=0, le=100)] | None
    soil_ph: Annotated[float, Field(ge=0, le=14)] | None
    irrigation_system: NonBlank | None
    irrigation_water_saline: bool | None
    current_disposal: NonBlank | None
    simulated: bool

    @model_validator(mode="after")
    def validate_estimate_and_origin(self) -> "Farm":
        if not self.simulated:
            raise ValueError("Phase 2 supports simulated farms only")
        if self.est_residue_kg_per_year != self.palm_count * RESIDUE_KG_PER_PALM_PER_YEAR:
            raise ValueError("est_residue_kg_per_year must equal palm_count × 35")
        return self


class FarmProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin: Literal["seed_dataset", "edited_seed", "local_simulation"]
    seed_file: str | None
    data_kind: Literal["simulated"] = "simulated"
    residue_kind: Literal["estimated"] = "estimated"
    residue_kg_per_palm_per_year: int = RESIDUE_KG_PER_PALM_PER_YEAR
    residue_source_id: Literal["NASSER2016"] = "NASSER2016"
    residue_record_id: Literal["ctx-02"] = "ctx-02"
    palm_count_origin: Literal["simulation", "model_prediction"] = "simulation"
    palm_count_observation_id: str | None = None


class FarmProfile(Farm):
    provenance: FarmProvenance


class FarmStatistics(BaseModel):
    model_config = ConfigDict(frozen=True)

    region: str | None
    farm_count: int
    total_area_ha: float
    total_palm_count: int
    total_est_residue_kg_per_year: int
    simulated: Literal[True] = True
