"""A single-dispatch LangGraph for Arabic SAAF requests."""

from langgraph.graph import END, START, StateGraph
from pydantic import TypeAdapter

from saaf.agents.recommendation import RecommendationResponse
from saaf.agents.tools import FarmId
from saaf.providers import RATE_LIMIT_AR, is_rate_limited

from .contracts import AgentState, ConversationContext, OrchestrationResponse, RecommendationPort
from .routing import INLINE_FARM, classify, is_followup, mentions_other_farm

_FARM_ID = TypeAdapter(FarmId)
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
    if active_id != context.farm_id:
        context = ConversationContext(farm_id=active_id)
    intent, candidates = classify(query, context.previous_intent)
    agent_query = query
    if intent == "recommendation" and is_followup(query) and context.previous_query:
        agent_query = f"السؤال السابق: {context.previous_query}\nالسؤال الحالي: {query}"
    if candidates and intent != "clarification" and not is_followup(query):
        context = ConversationContext(
            farm_id=active_id, previous_query=query, previous_intent=candidates[0],
        )
    elif intent in {"clarification", "unsupported"}:
        # Avoid resolving a later vague follow-up using an abandoned request.
        context = ConversationContext(farm_id=active_id)
    return {
        "intent": intent, "candidate_intents": candidates, "context": context,
        "agent_query": agent_query,
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

    def __init__(self, recommendation: RecommendationPort) -> None:
        self.recommendation = recommendation
        graph = StateGraph(AgentState)
        graph.add_node("route", _route)
        graph.add_node("recommend", self._recommend)
        graph.add_node("respond", _respond_without_agent)
        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route", lambda state: state["intent"] == "recommendation",
            {True: "recommend", False: "respond"},
        )
        graph.add_edge("recommend", END)
        graph.add_edge("respond", END)
        self._graph = graph.compile()

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
    ) -> OrchestrationResponse:
        context = context if context is not None else ConversationContext()
        try:
            if farm_id is not None:
                farm_id = _FARM_ID.validate_python(farm_id, strict=True)
            if context.farm_id is not None:
                _FARM_ID.validate_python(context.farm_id, strict=True)
            if not isinstance(query, str) or len(query) > 4000:
                raise ValueError("invalid query")
        except ValueError:
            return OrchestrationResponse(
                intent="clarification", status="needs_input", context=context,
                answer_ar="أرسل سؤالاً مختصراً ومعرّف مزرعة صالحاً إن لزم.",
            )
        state = self._graph.invoke(
            {"query": query, "context": context, "requested_farm_id": farm_id},
            config={"recursion_limit": 4},
        )
        return state["response"]
