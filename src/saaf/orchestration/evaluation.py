"""A small labeled benchmark for routing, independent of agent response quality."""

from pydantic import BaseModel

from .contracts import Capability, Intent
from .routing import classify

CASES: tuple[tuple[str, Intent, tuple[Capability, ...]], ...] = (
    ("هل الفحم الحيوي مناسب للتربة الرملية؟", "recommendation", ("recommendation",)),
    ("وش رأيك بفحم السعف لأرضي؟", "recommendation", ("recommendation",)),
    ("كم الجرعة المرجعية وزناً؟", "recommendation", ("recommendation",)),
    ("هل ملوحة الموية مشكلة؟", "recommendation", ("recommendation",)),
    ("كم بالمية بأوفر من موية الري؟", "recommendation", ("recommendation",)),
    ("كم وزن مخلفات النخلة في السنة؟", "recommendation", ("recommendation",)),
    ("أبغى طلب جمع للسعف", "collection", ("collection",)),
    ("تقدرون تشلون المخلفات من المزرعة؟", "collection", ("collection",)),
    ("حدد موعد استلام المخلفات", "collection", ("collection",)),
    ("وين نقطة التجميع؟", "collection", ("collection",)),
    ("أبي أنقل هالسعف", "collection", ("collection",)),
    ("حلّل صورة جوية للمزرعة", "monitoring", ("monitoring",)),
    ("تعدون النخل عندي؟", "monitoring", ("monitoring",)),
    ("أحتاج رصد النخيل", "monitoring", ("monitoring",)),
    ("هل يمكن كشف تيجان النخيل؟", "monitoring", ("monitoring",)),
    ("ما الأثر البيئي لمعالجة المخلفات؟", "impact", ("impact",)),
    ("كم انبعاثات المعالجة؟", "impact", ("impact",)),
    ("ودي أعرف بصمة الكربون", "impact", ("impact",)),
    ("احسب دورة الحياة للسيناريو", "impact", ("impact",)),
    ("عندي مخلفات", "clarification", ()),
    ("وش أسوي؟", "clarification", ()),
    ("وضح أكثر", "clarification", ()),
    ("اجمع المخلفات واحسب الانبعاثات", "clarification", ("collection", "impact")),
    ("أبي توصية عن الفحم الحيوي ورصد النخيل", "clarification", ("recommendation", "monitoring")),
    ("أحتاج شاحنة وصورة جوية", "clarification", ("collection", "monitoring")),
    ("من فاز بالمباراة؟", "unsupported", ()),
    ("احجز لي رحلة", "unsupported", ()),
    ("وش طريقة تغيير كلمة المرور؟", "unsupported", ()),
)


class RoutingCase(BaseModel):
    query: str
    expected: Intent
    actual: Intent
    expected_candidates: tuple[Capability, ...]
    actual_candidates: tuple[Capability, ...]
    passed: bool


class RoutingReport(BaseModel):
    routing_accuracy: float
    correct: int
    total: int
    cases: list[RoutingCase]


def evaluate_routing() -> RoutingReport:
    results = []
    for query, expected, expected_candidates in CASES:
        actual, actual_candidates = classify(query)
        results.append(RoutingCase(
            query=query, expected=expected, actual=actual,
            expected_candidates=expected_candidates, actual_candidates=actual_candidates,
            passed=(actual, actual_candidates) == (expected, expected_candidates),
        ))
    correct = sum(case.passed for case in results)
    return RoutingReport(routing_accuracy=correct / len(results), correct=correct,
                         total=len(results), cases=results)
