"""Deterministic Arabic and Saudi dialect routing for the supported domains."""

import re
import unicodedata

from .contracts import Capability, Intent

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670]")
_LETTERS = str.maketrans("أإآٱىةؤئـ", "اااايهوي ")
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
        r"(?:موعد|طلب) (?:للجمع|للاستلام|جمع|استلام)|شاحنه|نقطه (?:ال)?تجميع"
    ),
    "monitoring": re.compile(
        r"مراقبه النخيل|رصد النخيل|(?:عد|اعد|احسب|عدوا|تعدون) (?:عدد )?(?:ال)?نخ(?:ل|يل)|"
        r"(?:صور|صوره|تصوير|وصوره) (?:جويه|الدرون|بالدرون|قمر صناعي|الاقمار الصناعيه)|"
        r"كشف (?:النخيل|تيجان)|عدد النخيل (?:في|من) الصور"
    ),
    "impact": re.compile(
        r"(?:اثر|الاثر|تاثير|التاثير) (?:ال)?بييي|(?:البصمه|بصمه) الكربونيه|"
        r"انبعاثات|الكربون|co2e?|غازات الدفييه|دوره الحياه"
    ),
}
_AMBIGUOUS = re.compile(r"^(?:كيف ابدا|ساعدني|وش اسوي|ابغ[اي] مساعده|عندي مخلفات|عندي سعف|مزرعتي)[.!؟ ]*$")
_FOLLOWUP = re.compile(r"^(?:طيب )?(?:وش بعد|وضح اكثر|ممكن توضح|ليه|كيف يعني|وش تقصد|وعن ذا)[.!؟? ]*$")
INLINE_FARM = re.compile(r"(?<![\w-])SIM-[0-9]+(?![\w-])", re.IGNORECASE | re.ASCII)
_OTHER_FARM = re.compile(r"(?:مزرعه|المزرعه) (?:ال)?(?:ثانيه|اخرى|جديده|مختلفه)")


def normalize(query: str) -> str:
    text = unicodedata.normalize("NFKC", query).lower()
    return " ".join(_ARABIC_DIACRITICS.sub("", text).translate(_LETTERS).split())


def classify(query: str, previous_intent: Capability | None = None) -> tuple[Intent, tuple[Capability, ...]]:
    text = normalize(query)
    if not text or _AMBIGUOUS.fullmatch(text):
        return "clarification", ()
    if _FOLLOWUP.fullmatch(text):
        return (previous_intent, (previous_intent,)) if previous_intent else ("clarification", ())
    candidates = tuple(intent for intent, pattern in _PATTERNS.items() if pattern.search(text))
    if len(candidates) > 1:
        return "clarification", candidates
    if candidates:
        return candidates[0], candidates
    return "unsupported", ()


def is_followup(query: str) -> bool:
    return bool(_FOLLOWUP.fullmatch(normalize(query)))


def mentions_other_farm(query: str) -> bool:
    return bool(_OTHER_FARM.search(normalize(query)))
