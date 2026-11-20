"""Typed, read-only inputs for Arabic recommendations."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

from saaf.farms import FarmProfile, FarmRepository, get_farm_profile as lookup_farm
from saaf.knowledge.retrieval import DEFAULT_TOP_K, KnowledgeIndex, SearchResult


FarmId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
_FARM_ID = TypeAdapter(FarmId)
_SEARCH_RESULT = TypeAdapter(SearchResult)


class EvidenceSearchArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    top_k: int = Field(ge=1)


def get_farm_profile(repository: FarmRepository, farm_id: str | None) -> FarmProfile | None:
    """Read a validated farm profile and verify that it belongs to the requested ID."""
    if farm_id is None or (isinstance(farm_id, str) and not farm_id.strip()):
        return None
    checked_id = _FARM_ID.validate_python(farm_id.strip() if isinstance(farm_id, str) else farm_id, strict=True)
    raw = lookup_farm(repository, checked_id)
    if raw is None:
        return None
    profile = FarmProfile.model_validate(raw.model_dump() if isinstance(raw, FarmProfile) else raw)
    if profile.farm_id != checked_id:
        raise ValueError("farm tool returned a different ID")
    return profile


def search_scientific_evidence(
    knowledge: KnowledgeIndex, query: str, *, top_k: int = DEFAULT_TOP_K,
) -> SearchResult:
    """Search the approved scientific corpus."""
    args = EvidenceSearchArgs(query=query, top_k=top_k)
    raw = knowledge.search(args.query, top_k=args.top_k)
    result = _SEARCH_RESULT.validate_python({
        "status": raw.status, "hits": raw.hits, "reason": raw.reason,
    } if isinstance(raw, SearchResult) else raw)
    records = {record.id: record for record in knowledge.corpus.records}
    ids = set()
    for hit in result.hits:
        if not -1 <= hit.score <= 1 or hit.record.id in ids:
            raise ValueError("invalid evidence score or duplicate evidence ID")
        if (records.get(hit.record.id) != hit.record
                or knowledge.corpus.sources.get(hit.record.source_id) != hit.source):
            raise ValueError("evidence does not match the corpus")
        ids.add(hit.record.id)
    if len(ids) > args.top_k or (result.status == "ok") != bool(ids):
        raise ValueError("inconsistent evidence result")
    return result


@dataclass(frozen=True)
class SoilAssessment:
    warnings: tuple[str, ...]
    missing_information: tuple[str, ...]


def assess_soil_suitability(profile: FarmProfile) -> SoilAssessment:
    """Identify cautions and missing values without inferring soil texture or a dose."""
    warnings = []
    missing = []
    if profile.soil_sand_pct is None:
        missing.append("نسبة الرمل أو وصف قوام التربة")
    if profile.soil_ph is None:
        missing.append("الرقم الهيدروجيني للتربة (pH)")
    elif profile.soil_ph >= 8:
        warnings.append(
            "الرقم الهيدروجيني مرتفع في الملف المحاكى. قد يزيد الفحم الحيوي قلوية التربة. "
            "استشر مختصاً بشأن الملاءمة وخيارات مثل الخلط بالسماد العضوي أو استخدام فحم معالج."
        )
    if profile.irrigation_water_saline is None:
        missing.append("ملوحة مياه الري")
    elif profile.irrigation_water_saline:
        warnings.append("مياه الري مصنفة مالحة في الملف المحاكى. قد يزيد الفحم الحيوي ملوحة التربة.")
    if profile.irrigation_system is None:
        missing.append("نظام الري")
    return SoilAssessment(tuple(warnings), tuple(missing))
