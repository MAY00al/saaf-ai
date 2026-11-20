"""Deterministic Arabic and Saudi dialect routing for the supported domains."""

import re

from saaf.agents.impact import is_environmental_query, requested_indicators
from saaf.arabic import normalize
from saaf.collection.commands import REQUEST_ID
from .contracts import Capability, Intent

_PATTERNS: dict[Capability, re.Pattern[str]] = {
    "recommendation": re.compile(
        r"الفحم الحيوي|فحم (?:حيوي|السعف|النخيل)|بيوتشار|biochar|"
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


def classify(query: str, previous_intent: Capability | None = None) -> tuple[Intent, tuple[Capability, ...]]:
    text = normalize(query)
    if not text or _AMBIGUOUS.fullmatch(text):
        return "clarification", ()
    if _FOLLOWUP.fullmatch(text):
        return (previous_intent, (previous_intent,)) if previous_intent else ("clarification", ())
    candidates_found = {intent for intent, pattern in _PATTERNS.items() if pattern.search(text)}
    indicators = requested_indicators(text)
    if REQUEST_ID.search(query):
        candidates_found.add("collection")
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
