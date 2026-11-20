"""Validate the complete fixture before a repository writes any rows."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .models import Farm

DEFAULT_SEED_PATH = Path("data/saaf_simulated_farms.json")


class FarmDataset(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    about: dict[str, JsonValue] = Field(min_length=1)
    farms: list[Farm] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rows(self) -> "FarmDataset":
        seen = set()
        for farm in self.farms:
            if farm.farm_id in seen:
                raise ValueError(f"duplicate farm ID: {farm.farm_id}")
            missing = [name for name, value in farm.model_dump().items() if value is None]
            if missing:
                raise ValueError(f"{farm.farm_id}: missing fixture values: {', '.join(missing)}")
            seen.add(farm.farm_id)
        return self


def load_farm_dataset(path: Path = DEFAULT_SEED_PATH) -> FarmDataset:
    return FarmDataset.model_validate_json(path.read_text(encoding="utf-8-sig"))
