"""Deterministic Arabic and Saudi dialect routing for the supported domains."""

import re
from typing import Literal

from saaf.agents.impact import is_environmental_query, requested_indicators
from saaf.arabic import normalize
from saaf.collection.commands import REQUEST_ID
from saaf.geospatial.satellite import Mode
from .contracts import Capability, Intent

_PATTERNS: dict[Capability, re.Pattern[str]] = {
    "recommendation": re.compile(
        r"الفحم الحيوي|فحم (?:حيوي|السعف|النخيل)|(?:استخدام|اضافه) الفحم|بيوتشار|biochar|"
        r"هل (?:الفحم (?:مناسب|ملايم)|(?:يناسب|يصلح) الفحم)|"
        r"قلويه|رطوبه التربه|ملوحه|التبخر|الجرعه|الرقم الهيدروجيني|الفحم.{0,40}التربه|"
        r"كم (?:وزن|كميه) مخلفات|مخلفات النخله|التوصيه العلميه|"
        r"توفير مياه الري|اوفر (?:من )?(?:مويه|مياه)|الدراسات العلميه"
    ),
    "collection": re.compile(
        r"(?:اجمع|جمع|تجميع|استلام|يشيل|ياخذ|تشلون|شيل|نقل|انقل|التقاط)\w* (?:(?:لي|مني) )?(?:ال)?(?:مخلفات|سعف|جريد)|"
        r"(?:جمع|استلام|نقل|انقل)\w* (?:هالمخلفات|هالسعف)|"
        r"(?:موعد|طلب) (?:للجمع|للاستلام|جمع|استلام)|شاحنه|نقطه (?:ال)?تجميع|"
        r"طلباتي|(?:حاله|متابعه|تتبع) (?:ال)?طلب|طلبات (?:الجمع|الاستلام)"
    ),
    "monitoring": re.compile(
        r"مراقبه النخيل|رصد النخيل|(?:عد|اعد|احسب|عدوا|تعدون) (?:عدد )?(?:ال)?نخ(?:ل|يل)|"
        r"(?:صور|صوره|تصوير|وصوره) (?:جويه|الدرون|بالدرون|قمر صناعي|الاقمار الصناعيه)|"
        r"كشف (?:النخيل|تيجان)|عدد النخيل (?:في|من) الصور"
    ),
    "impact": re.compile(
        r"(?:اثر|الاثر|تاثير|التاثير) (?:ال)?بييي|(?:البصمه|بصمه) الكربونيه|"
        r"انبعاثات|الكربون|co2e?|غازات الدفييه|دوره الحياه|"
        r"المزارع المسجله|عدد المزارع|عدد (?:النخيل|النخل) (?:المسجل|في السجل|عندنا)|"
        r"(?:اجمالي|مجموع) (?:عدد )?(?:النخيل|النخل|المزارع|المخلفات|الطلبات)|"
        r"كم (?:مزرعه|نخله) (?:مسجله|في السجل|عندنا)|المخلفات السنويه المقدره|"
        r"(?:الكميه|الكميات) الموكده|كم جمعنا|"
        r"(?:طلبات|الطلبات|الطلب) (?:(?:الجمع|الاستلام) )?(?:الموكده|الملغاه|حسب الحاله|حسب المنطقه)|تقرير المحاكاه"
    ),
}
_AMBIGUOUS = re.compile(r"^(?:كيف ابدا|ساعدني|وش اسوي|ابغ[اي] مساعده|عندي مخلفات|عندي سعف|مزرعتي)[.!؟ ]*$")
_FOLLOWUP = re.compile(r"^(?:طيب )?(?:وش بعد|وضح اكثر|ممكن توضح|ليه|كيف يعني|وش تقصد|وعن ذا)[.!؟? ]*$")
INLINE_FARM = re.compile(r"(?<![\w-])SIM-[0-9]+(?![\w-])", re.IGNORECASE | re.ASCII)
_OTHER_FARM = re.compile(r"(?:مزرعه|المزرعه) (?:ال)?(?:ثانيه|اخرى|جديده|مختلفه)")
_WASTE_TOTAL = re.compile(
    r"(?:مخلفات|نفايات|بقايا|مخلف) (?:النخيل|النخل)\b.{0,36}(?:سنوي|بالسنه|في السنه|كل سنه)|"
    r"(?:مخلفات|نفايات|بقايا) (?:ال)?(?:سنوي\w*|منتجه سنويا)|"
    r"(?:اجمالي|مجموع|كم|ما|وش) (?:ال)?(?:كميه|وزن) (?:ال)?(?:مخلفات|نفايات) (?:النخيل|النخل)\b|"
    r"annual (?:estimated )?(?:date )?palm (?:waste|residue)|total (?:date )?palm waste"
)
_COLLECTION_TOTAL = re.compile(
    r"(?:كميه|كميات|وزن|اجمالي) (?:ال)?(?:جمع|استلام|طلبات (?:الجمع|الاستلام))\b|"
    r"(?:كميه|وزن) (?:التي|اللي) (?:تم جمع|تم استلام|انجمعت|جمعتو)|"
    r"(?:كميه|كميات|وزن|اجمالي|كم|وش كثر) (?:ال)?(?:مخلفات|سعف|نفايات)\b.{0,36}"
    r"(?:المجمعه|المستلمه|جمعنا|جمعتو|انجمعت|تم جمع|تم استلام|جمعها)|"
    r"كم (?:جمعتو|انجمع|استلمتوا|تم جمع)|(?:total|confirmed) (?:collection|collected) (?:quantity|quantities|weight|waste)|"
    r"how much (?:palm )?waste (?:was |has been )?collected|\bcollection (?:quantity|quantities|totals)\b"
)
_SCIENTIFIC_REQUEST = re.compile(r"فحم|biochar|توصي|جرعه|ملوحه|قلويه|رطوبه|التبخر|دراس")
_PICKUP_ACTION = re.compile(r"\b(?:استلم|اجمع|انقل|موعد|شاحنه|تشلون|ابغى|ابي|احجز|الغ|الغاء)\b")
_GEOGRAPHY = re.compile(r"(?:حدود|مساحه|احداثيات) (?:ال)?مزرع\w*|farm (?:boundary|area|coordinates)")
_VEGETATION = re.compile(r"\bndvi\b|sentinel[ -]?2|سنتينل|(?:صور|صوره) (?:ال)?اقمار صناعيه|الغطاء النباتي|satellite|vegetation")


def geographic_request(query: str) -> Mode | Literal["geography", "satellite_count"] | None:
    text = normalize(query)
    if _VEGETATION.search(text):
        if re.search(r"(?:عد|اعد|احسب|عدد|كم) (?:عدد )?(?:ال)?نخ(?:ل|يل|له)\b|palm count|count (?:individual )?palms", text):
            return "satellite_count"
        if re.search(r"تاريخ|تاريخي|سجل|مع الوقت|تغير|history|trend", text):
            return "history"
        if re.search(r"صور|imagery", text) and not re.search(r"ndvi|الغطاء النباتي|vegetation", text):
            return "imagery"
        return "ndvi"
    return "geography" if _GEOGRAPHY.search(text) else None


def classify(query: str, previous_intent: Capability | None = None) -> tuple[Intent, tuple[Capability, ...]]:
    text = normalize(query)
    if not text or _AMBIGUOUS.fullmatch(text):
        return "clarification", ()
    if _FOLLOWUP.fullmatch(text):
        return (previous_intent, (previous_intent,)) if previous_intent else ("clarification", ())
    candidates_found = {intent for intent, pattern in _PATTERNS.items() if pattern.search(text)}
    if geographic_request(query):
        candidates_found.add("monitoring")
    indicators = requested_indicators(text)
    if REQUEST_ID.search(query):
        candidates_found.add("collection")
    aggregate = bool(_WASTE_TOTAL.search(text) or _COLLECTION_TOTAL.search(text))
    if aggregate:
        candidates_found.add("impact")
        if not _SCIENTIFIC_REQUEST.search(text):
            candidates_found.discard("recommendation")
        if not _PICKUP_ACTION.search(text) and not REQUEST_ID.search(query):
            candidates_found.discard("collection")
    explicit_water_report = "water_savings" in indicators and bool(re.search(r"احسب|قدر|تقرير", text))
    if any(item != "water_savings" for item in indicators) or is_environmental_query(text) or explicit_water_report:
        candidates_found.add("impact")
        # A reference to biochar inside an impact question does not add a separate task.
        if not re.search(r"توصي|جرعه|ملوحه|قلويه|رطوبه|التبخر|وش رايك", text):
            candidates_found.discard("recommendation")
    if "impact" in candidates_found and re.search(r"اجمالي|مجموع|حسب الحاله|حسب المنطقه|الموكده|الملغاه", text):
        if not re.search(r"استلم|اجمع|انقل|موعد|شاحنه|تشلون", text):
            candidates_found.discard("collection")
    candidates = tuple(intent for intent in _PATTERNS if intent in candidates_found)
    if len(candidates) > 1:
        return "clarification", candidates
    if candidates:
        return candidates[0], candidates
    return "unsupported", ()


def is_followup(query: str) -> bool:
    return bool(_FOLLOWUP.fullmatch(normalize(query)))


def mentions_other_farm(query: str) -> bool:
    return bool(_OTHER_FARM.search(normalize(query)))
