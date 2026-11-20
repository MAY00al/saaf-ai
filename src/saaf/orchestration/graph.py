"""A single-dispatch LangGraph for Arabic SAAF requests."""

from pathlib import Path

from langgraph.graph import END, START, StateGraph
from pydantic import TypeAdapter

from saaf.agents.recommendation import RecommendationResponse
from saaf.agents.tools import FarmId
from saaf.collection.commands import confirmation_action, has_quantity_input
from saaf.monitoring.models import MonitoringResult
from saaf.providers import RATE_LIMIT_AR, is_rate_limited

from .contracts import (
    AgentState, CollectionPort, ConversationContext, ImpactPort, MonitoringPort,
    OrchestrationResponse, RecommendationPort,
)
from .routing import INLINE_FARM, classify, geographic_request, is_followup, mentions_other_farm, normalize

_FARM_ID = TypeAdapter(FarmId)


def _confirm_count(query: str) -> bool:
    return normalize(query).rstrip(".!").strip() in {"اوكد تحديث العدد", "اكد تحديث العدد"}


_LABELS = {
    "recommendation": "التوصية العلمية",
    "collection": "جمع المخلفات",
    "monitoring": "رصد النخيل",
    "impact": "تقييم الأثر البيئي",
}


def _route(state: AgentState) -> AgentState:
    query, context = state["query"], state["context"]
    inline_ids = {match.group().upper() for match in INLINE_FARM.finditer(query)}
    explicit_id = state.get("requested_farm_id")
    if explicit_id and INLINE_FARM.fullmatch(explicit_id):
        explicit_id = explicit_id.upper()
    if explicit_id:
        inline_ids.add(explicit_id)
    if len(inline_ids) > 1:
        return {"intent": "clarification", "clarification_ar": "حدّد مزرعة واحدة لهذا الطلب."}
    if mentions_other_farm(query) and (not inline_ids or context.farm_id in inline_ids):
        return {
            "intent": "clarification", "context": ConversationContext(),
            "clarification_ar": "أرسل معرّف المزرعة الأخرى قبل متابعة الطلب.",
        }

    active_id = next(iter(inline_ids), context.farm_id)
    first_farm_selection = context.farm_id is None and context.previous_intent == "collection"
    if active_id != context.farm_id:
        context = ConversationContext(farm_id=active_id)
    collection_continuing = context.previous_intent == "collection" or first_farm_selection
    intent, candidates = classify(query, context.previous_intent)
    if confirmation_action(query) == "confirm" or (
        confirmation_action(query) == "decline" and (collection_continuing or context.pickup_draft)
    ):
        intent, candidates = "collection", ("collection",)
    elif collection_continuing and intent == "unsupported" and (
        has_quantity_input(query) or INLINE_FARM.fullmatch(query.strip())
    ):
        intent, candidates = "collection", ("collection",)
    if _confirm_count(query):
        if state.get("image_path") is not None:
            return {"intent": "clarification", "context": context,
                    "clarification_ar": "أرسل تأكيد العدد في رسالة مستقلة عن الصورة الجديدة."}
        intent, candidates = "monitoring", ("monitoring",)
    elif state.get("image_path") is not None and intent in {"clarification", "unsupported"} and not candidates:
        intent, candidates = "monitoring", ("monitoring",)
    agent_query = query
    if intent == "recommendation" and is_followup(query) and context.previous_query:
        agent_query = f"السؤال السابق: {context.previous_query}\nالسؤال الحالي: {query}"
    if candidates and intent != "clarification" and not is_followup(query):
        context = ConversationContext(
            farm_id=active_id, previous_query=query, previous_intent=candidates[0],
            pickup_draft=context.pickup_draft,
            count_review=context.count_review,
        )
    elif intent in {"clarification", "unsupported"}:
        # Avoid resolving a later vague follow-up using an abandoned request.
        context = ConversationContext(farm_id=active_id)
    return {
        "intent": intent, "candidate_intents": candidates, "context": context,
        "agent_query": agent_query, "collection_continuing": collection_continuing,
    }


def _respond_without_agent(state: AgentState) -> AgentState:
    intent = state["intent"]
    context = state["context"]
    candidates = state.get("candidate_intents", ())
    if intent == "clarification":
        message = state.get("clarification_ar")
        if not message and candidates:
            message = "طلبك يتضمن أكثر من مهمة. اختر مهمة واحدة: " + "، ".join(
                _LABELS[candidate] for candidate in candidates
            ) + "."
        return {"response": OrchestrationResponse(
            intent=intent, status="needs_input", context=context, candidate_intents=candidates,
            answer_ar=message or "وضّح طلبك: هل تريد توصية علمية، جمع المخلفات، رصد النخيل، أم تقييم الأثر البيئي؟",
        )}
    if intent == "unsupported":
        return {"response": OrchestrationResponse(
            intent=intent, status="unsupported", context=context,
            answer_ar="هذا الطلب خارج نطاق خدمات سَعَف. اسأل عن النخيل أو مخلفاته أو الفحم الحيوي.",
        )}
    return {"response": OrchestrationResponse(
        intent=intent, status="not_implemented", context=context, candidate_intents=candidates,
        answer_ar=f"خدمة {_LABELS[intent]} قيد التطوير. لم يُنفّذ طلبك.",
    )}


class Orchestrator:
    """Route each turn once using context supplied explicitly by the caller."""

    def __init__(
        self, recommendation: RecommendationPort, *, collection: CollectionPort | None = None,
        impact: ImpactPort | None = None, monitoring: MonitoringPort | None = None,
    ) -> None:
        self.recommendation = recommendation
        self.collection = collection
        self.impact = impact
        self.monitoring = monitoring
        graph = StateGraph(AgentState)
        graph.add_node("route", _route)
        graph.add_node("recommend", self._recommend)
        graph.add_node("collect", self._collect)
        graph.add_node("impact_report", self._impact)
        graph.add_node("monitor", self._monitor)
        graph.add_node("respond", _respond_without_agent)
        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route", self._dispatch,
            {"recommend": "recommend", "collect": "collect",
             "impact_report": "impact_report", "monitor": "monitor", "respond": "respond"},
        )
        graph.add_edge("recommend", END)
        graph.add_edge("collect", END)
        graph.add_edge("impact_report", END)
        graph.add_edge("monitor", END)
        graph.add_edge("respond", END)
        self._graph = graph.compile()

    def _dispatch(self, state: AgentState) -> str:
        intent = state["intent"]
        if intent == "recommendation":
            return "recommend"
        if intent == "collection" and self.collection is not None:
            return "collect"
        if intent == "impact" and self.impact is not None:
            return "impact_report"
        if intent == "monitoring" and self.monitoring is not None:
            return "monitor"
        return "respond"

    def _monitor(self, state: AgentState) -> AgentState:
        context = state["context"]
        candidates = state["candidate_intents"]
        try:
            geographic = geographic_request(state["agent_query"]) if state.get("image_path") is None else None
            if _confirm_count(state["query"]):
                result = self.monitoring.confirm_count(context.farm_id, context.count_review)
            elif geographic == "satellite_count":
                result = MonitoringResult(
                    status="needs_input",
                    answer_ar="عدّ النخيل الفردي يحتاج صورة جوية عالية الدقة؛ صور Sentinel‑2 تُستخدم لرصد الغطاء النباتي.",
                )
            elif geographic == "geography":
                result = self.monitoring.inspect_geography(context.farm_id)
            elif geographic is not None:
                result = self.monitoring.inspect_vegetation(context.farm_id, geographic)
            else:
                result = self.monitoring.inspect_palms(
                    context.farm_id, state.get("image_path"), whole_farm=state.get("whole_farm", False),
                )
            if ((result.observation and result.observation.farm_id != context.farm_id)
                    or (result.pending_review and result.pending_review.farm_id != context.farm_id)
                    or (result.updated_farm_id and result.updated_farm_id != context.farm_id)):
                raise ValueError("monitoring result returned a different farm")
        except Exception:
            return {"response": OrchestrationResponse(
                intent="monitoring", status="unavailable", context=context, candidate_intents=candidates,
                answer_ar="تعذّر تشغيل الرصد المحلي حالياً. تحقق من إعدادات الصورة والأوزان.",
            )}
        if geographic is None:
            context = context.model_copy(update={"count_review": result.pending_review})
        return {"response": OrchestrationResponse(
            intent="monitoring", status=result.status, context=context, answer_ar=result.answer_ar,
            candidate_intents=candidates, monitoring=result,
        )}

    def _collect(self, state: AgentState) -> AgentState:
        context = state["context"]
        candidates = state["candidate_intents"]
        try:
            result = self.collection.plan_collection(
                state["query"], context.farm_id, context.pickup_draft,
                continuing=state["collection_continuing"],
            )
            records = (result.draft, result.request, *result.requests)
            if any(record and record.farm_id != context.farm_id for record in records):
                raise ValueError("collection result returned a different farm")
        except Exception:
            return {"response": OrchestrationResponse(
                intent="collection", status="unavailable", context=context, candidate_intents=candidates,
                answer_ar="تعذّر الوصول إلى سجل الجمع المحاكى حالياً. حاول مرة أخرى لاحقاً.",
            )}
        context = context.model_copy(update={"pickup_draft": result.draft})
        return {"response": OrchestrationResponse(
            intent="collection", status=result.status, context=context, answer_ar=result.answer_ar,
            candidate_intents=candidates, collection=result,
        )}

    def _impact(self, state: AgentState) -> AgentState:
        context = state["context"]
        candidates = state["candidate_intents"]
        try:
            result = self.impact.estimate_impact(state["agent_query"])
        except Exception:
            return {"response": OrchestrationResponse(
                intent="impact", status="unavailable", context=context, candidate_intents=candidates,
                answer_ar="تعذّر إعداد تقرير المحاكاة حالياً. حاول مرة أخرى لاحقاً.",
            )}
        return {"response": OrchestrationResponse(
            intent="impact", status=result.status, context=context, answer_ar=result.answer_ar,
            candidate_intents=candidates, impact=result,
        )}

    def _recommend(self, state: AgentState) -> AgentState:
        context = state["context"]
        candidates = state["candidate_intents"]
        try:
            raw = self.recommendation.recommend(state["agent_query"], context.farm_id)
            result = RecommendationResponse.model_validate(
                raw.model_dump() if isinstance(raw, RecommendationResponse) else raw,
            )
            if result.farm_id != context.farm_id:
                raise ValueError("agent returned a different farm")
        except Exception as exc:
            return {"response": OrchestrationResponse(
                intent="recommendation", status="unavailable", context=context,
                candidate_intents=candidates,
                answer_ar=RATE_LIMIT_AR if is_rate_limited(exc) else
                "تعذّر تشغيل خدمة التوصيات حالياً. حاول مرة أخرى لاحقاً.",
            )}
        return {"response": OrchestrationResponse(
            intent="recommendation", status=result.status, answer_ar=result.answer_ar,
            context=context, candidate_intents=candidates, recommendation=result,
        )}

    def run(
        self, query: str, *, context: ConversationContext | None = None, farm_id: str | None = None,
        image_path: Path | None = None, whole_farm: bool = False,
    ) -> OrchestrationResponse:
        context = context if context is not None else ConversationContext()
        try:
            if farm_id is not None:
                farm_id = _FARM_ID.validate_python(farm_id, strict=True)
            if context.farm_id is not None:
                _FARM_ID.validate_python(context.farm_id, strict=True)
            if not isinstance(query, str) or len(query) > 4000:
                raise ValueError("invalid query")
            if type(whole_farm) is not bool or (image_path is not None and not isinstance(image_path, Path)):
                raise ValueError("invalid monitoring input")
        except ValueError:
            return OrchestrationResponse(
                intent="clarification", status="needs_input", context=context,
                answer_ar="أرسل سؤالاً مختصراً ومعرّف مزرعة صالحاً إن لزم.",
            )
        state = self._graph.invoke(
            {"query": query, "context": context, "requested_farm_id": farm_id,
             "image_path": image_path, "whole_farm": whole_farm},
            config={"recursion_limit": 4},
        )
        return state["response"]
