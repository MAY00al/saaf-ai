"""Validate the source snapshot without rewriting its contents."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

NonBlank = Annotated[str, StringConstraints(pattern=r"\S")]


class Source(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    title: NonBlank
    url: NonBlank
    type: NonBlank

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("source URL must be an absolute HTTP(S) URL")
        return value


class Record(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9]*-[0-9]+$")]
    topic: NonBlank
    text_ar: NonBlank
    source_id: NonBlank
    evidence_level: NonBlank
    values: dict[str, JsonValue] | None = None
    conditions: dict[str, JsonValue] | None = None
    caveat_ar: NonBlank | None = None


class Corpus(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    about: dict[str, JsonValue] = Field(min_length=1)
    sources: dict[NonBlank, Source] = Field(min_length=1)
    agent_rules_ar: list[NonBlank]
    records: list[Record] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "Corpus":
        seen = set()
        for record in self.records:
            if record.id in seen:
                raise ValueError(f"duplicate record ID: {record.id}")
            if record.source_id not in self.sources:
                raise ValueError(f"{record.id}: unknown source {record.source_id}")
            seen.add(record.id)
        return self


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def load_corpus(path: Path) -> tuple[Corpus, str]:
    content = path.read_bytes()
    data = json.loads(
        content.decode("utf-8-sig"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_nonfinite,
    )
    return Corpus.model_validate(data), sha256(content).hexdigest()
