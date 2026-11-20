"""Typed, read-only inputs for Arabic recommendations."""

from dataclasses import dataclass

from saaf.farms import FarmProfile, get_farm_profile as get_farm_profile
from saaf.knowledge.retrieval import DEFAULT_TOP_K, KnowledgeIndex, SearchResult


def search_scientific_evidence(
    knowledge: KnowledgeIndex, query: str, *, top_k: int = DEFAULT_TOP_K,
) -> SearchResult:
    """Search the approved scientific corpus."""
    return knowledge.search(query, top_k=top_k)


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
