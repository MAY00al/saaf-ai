"""Explain calculated operational metrics and identify scientific data gaps."""

import re
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from saaf.arabic import normalize
from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository

from saaf.impact.metrics import ImpactMetrics, calculate_metrics

Indicator = Literal["biochar", "stored_carbon", "avoided_emissions", "water_savings"]
_INDICATORS: dict[Indicator, re.Pattern[str]] = {
    "biochar": re.compile(r"(?:انتاج|انتج|ينتج|ننتج|كم(?:يه)?)\s+(?:من\s+)?(?:ال)?فحم(?: (?:ال)?حيوي)?"),
    "stored_carbon": re.compile(r"(?:(?:تخزين|خزن|احتجاز|يثبت|نخزن) (?:ال)?كربون|(?:ال)?كربون (?:المخزن|المحتجز))"),
    "avoided_emissions": re.compile(r"انبعاثات|البصمه الكربونيه|بصمه الكربون|co2e?|غازات الدفييه"),
    "water_savings": re.compile(r"(?:وفر|توفير|نوفر|اوفر) (?:في |من )?(?:مياه|مويه|المويه|المياه)"),
}
_GAPS: dict[Indicator, tuple[str, tuple[str, ...]]] = {
    "biochar": ("إنتاج الفحم الحيوي", ("كتلة المدخلات الجافة المقاسة", "مردود التحلل الحراري الموثق للعملية")),
    "stored_carbon": ("الكربون المخزّن", ("كتلة الفحم الحيوي الجافة المقاسة", "محتوى الكربون المقاس ومعامل الثبات الموثق")),
    "avoided_emissions": ("الانبعاثات المتجنبة", ("خط أساس وحدود مقارنة محددة", "بيانات النقل والمعالجة المقاسة", "عوامل انبعاث موثقة للسيناريوهين")),
    "water_savings": ("توفير مياه الري", ("حجم مياه الري المقاس قبل التطبيق وبعده", "مقارنة ميدانية مناسبة")),
}
_NARRATIVE = {
    "overview": "توضح الأرقام حجم السجل والطلبات المسجلة فيه.",
    "registry": "تقدير المخلفات السنوي مبني على عدد النخيل في السجل.",
    "collection": "إجمالي الكمية المؤكدة يجمع الكميات المدخلة للطلبات المؤكدة، ويستبعد الطلبات الملغاة.",
}


def requested_indicators(normalized_query: str) -> tuple[Indicator, ...]:
    return tuple(name for name, pattern in _INDICATORS.items() if pattern.search(normalized_query))


def is_environmental_query(normalized_query: str) -> bool:
    return bool(re.search(
        r"(?:اثر|الاثر|تاثير|التاثير) (?:ال)?بييي|دوره الحياه|الكربون", normalized_query,
    ))


class ImpactExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus: Literal["overview", "registry", "collection"]


class ExplanationModel(Protocol):
    def invoke(self, input: list[tuple[str, str]]) -> ImpactExplanation: ...


class DataGap(BaseModel):
    indicator: Indicator
    label_ar: str
    missing_information: tuple[str, ...]


class ImpactResult(BaseModel):
    status: Literal["ok", "insufficient_data", "needs_input"]
    answer_ar: str
    metrics: ImpactMetrics | None = None
    gaps: tuple[DataGap, ...] = ()
    simulated: Literal[True] = True


class ImpactAgent:
    def __init__(
        self, farms: FarmRepository, requests: CollectionRepository, model: ExplanationModel | None = None,
    ) -> None:
        self.farms = farms
        self.requests = requests
        self.model = model

    def estimate_impact(
        self, query: str, *, region: str | None = None,
    ) -> ImpactResult:
        text = normalize(query)
        indicators = requested_indicators(text)
        if not indicators and is_environmental_query(text):
            indicators = tuple(_GAPS)
        if region is None:
            regions = {farm.region for farm in self.farms.list_farms()}
            selected = [name for name in sorted(regions) if re.search(
                rf"(?<!\w){re.escape(normalize(name))}(?!\w)", text,
            )]
            if len(selected) > 1 or (not selected and re.search(r"\bمنطقه\b", text)):
                return ImpactResult(status="needs_input", answer_ar="حدّد منطقة واحدة مسجلة لتقرير المحاكاة.")
            region = selected[0] if selected else None
        metrics = calculate_metrics(self.farms, self.requests, region=region)
        scope = f" في {region}" if region else ""
        explanation = _NARRATIVE["overview"]
        if self.model is not None:
            try:
                choice = ImpactExplanation.model_validate(self.model.invoke([
                    ("system", "اختر محور شرح التقرير حسب السؤال: overview أو registry أو collection. "
                               "الأرقام محسوبة مسبقاً. لا تحسب أرقاماً ولا تستنتج أثراً بيئياً."),
                    ("human", f"السؤال: {query}\nالنتائج: {metrics.model_dump_json()}"),
                ]))
                explanation = _NARRATIVE[choice.focus]
            except Exception:
                # The calculation and its Arabic explanation remain available offline.
                pass
        answer = (
            f"تقرير محاكاة{scope}. {explanation}\n"
            f"المزارع المسجلة: {metrics.registered_farms}، النخيل: {metrics.palm_trees}، "
            f"المخلفات السنوية المقدّرة: {metrics.estimated_annual_waste_kg} كجم.\n"
            f"كمية الطلبات المؤكدة: {metrics.confirmed_requested_quantity_kg} كجم. "
            "هذه كمية طلبات في المحاكاة ولا تثبت استلاماً ميدانياً.\n"
            f"الطلبات المؤكدة: {metrics.requests_by_status.confirmed}، "
            f"الطلبات الملغاة: {metrics.requests_by_status.cancelled}."
        )
        for name, counts in metrics.requests_by_region_and_status.items():
            answer += f"\n{name}: {counts.confirmed} مؤكد، {counts.cancelled} ملغى."
        gaps = tuple(DataGap(indicator=item, label_ar=_GAPS[item][0], missing_information=_GAPS[item][1])
                     for item in indicators)
        if gaps:
            details = "\n".join(f"{gap.label_ar}: يلزم " + "، ".join(gap.missing_information) for gap in gaps)
            answer += f"\nلا تتوفر بيانات كافية لحساب المؤشرات البيئية المطلوبة.\n{details}"
        return ImpactResult(status="insufficient_data" if gaps else "ok", answer_ar=answer,
                            metrics=metrics, gaps=gaps)
