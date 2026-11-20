"""Small Arabic retrieval benchmark with human-assigned target IDs."""

from .retrieval import KnowledgeIndex

# A case passes when any accepted record appears in the results, or when a
# negative yields no hits. The IDs describe evidence targets, not gold answers.
CASES = (
    ("كيف يؤثر الفحم الحيوي في السعة الحقلية للتربة الرملية اللومية؟", ("bc-02",)),
    ("ما أثر فحم السعف على رطوبة التربة في تجربة الطماطم داخل الصوبة؟", ("bc-06",)),
    ("هل يخفض فحم مخلفات النخيل التبخر التراكمي من التربة؟", ("bc-03",)),
    ("ما الجرعة المرجعية وزناً من الفحم الحيوي للتربة الرملية؟", ("bc-05",)),
    ("كيف تغير التوصيل الهيدروليكي المشبع عند إضافة الفحم؟", ("bc-04",)),
    ("هل زادت ملوحة التربة عند إضافة الفحم الحيوي في الصوبة؟", ("bc-08",)),
    ("كيف تغير الرقم الهيدروجيني للتربة الكلسية مع فحم الكونوكاربس؟", ("bc-09",)),
    ("كم يُقدّر وزن مخلفات النخلة الواحدة سنوياً؟", ("ctx-02",)),
    ("ما عدد النخيل في السعودية بحسب إحصاءات 2023؟", ("ctx-01",)),
    ("ما أثر الفحم المعالج حمضياً على توفر الفسفور في التربة الكلسية؟", ("bc-10",)),
    ("ما نتيجة مباراة كرة القدم أمس؟", ()),
    ("كيف أستعيد كلمة مرور هاتفي؟", ()),
    ("كم بلغ توفير مياه الري المقاس في مزرعة نخيل بعد إضافة الفحم الحيوي؟", ()),
)


def evaluate(index: KnowledgeIndex, *, top_k: int, min_score: float) -> dict:
    cases = []
    for query, expected in CASES:
        result = index.search(query, top_k=top_k, min_score=min_score)
        ids = [hit.record.id for hit in result.hits]
        rank = next((rank for rank, record_id in enumerate(ids, 1) if record_id in expected), None)
        cases.append({
            "query": query,
            "expected": expected,
            "retrieved": [{"id": hit.record.id, "score": hit.score} for hit in result.hits],
            "first_relevant_rank": rank,
            "passed": rank is not None if expected else not ids,
        })
    positives = [case for case in cases if case["expected"]]
    negatives = [case for case in cases if not case["expected"]]
    return {
        "top_k": top_k,
        "min_score": min_score,
        "accuracy": sum(case["passed"] for case in cases) / len(cases),
        "positive_hit_rate_at_k": sum(case["passed"] for case in positives) / len(positives),
        "positive_mrr_at_k": sum(
            1 / case["first_relevant_rank"] for case in positives if case["first_relevant_rank"]
        ) / len(positives),
        "negative_rejection_rate": sum(case["passed"] for case in negatives) / len(negatives),
        "cases": cases,
    }
