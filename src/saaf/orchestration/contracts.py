"""Shared graph state and ports for SAAF capabilities."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

from saaf.agents.recommendation import RecommendationResponse

Capability = Literal["recommendation", "collection", "monitoring", "impact"]
Intent = Literal["recommendation", "collection", "monitoring", "impact", "clarification", "unsupported"]
Outcome = Literal["ok", "needs_input", "insufficient_evidence", "unavailable", "not_implemented", "unsupported"]


class ConversationContext(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    farm_id: str | None = None
    previous_query: str | None = Field(default=None, max_length=4000)
    previous_intent: Capability | None = None


class OrchestrationResponse(BaseModel):
    intent: Intent
    status: Outcome
    answer_ar: str
    context: ConversationContext
    candidate_intents: tuple[Capability, ...] = ()
    recommendation: RecommendationResponse | None = None


class AgentState(TypedDict, total=False):
    query: str
    requested_farm_id: str | None
    context: ConversationContext
    intent: Intent
    candidate_intents: tuple[Capability, ...]
    clarification_ar: str | None
    agent_query: str
    response: OrchestrationResponse


class RecommendationPort(Protocol):
    def recommend(self, query: str, farm_id: str | None = None) -> RecommendationResponse: ...


class FutureAgentRequest(BaseModel):
    """Common envelope for later capability-specific request payloads."""

    query: str
    farm_id: str | None


class CollectionPort(Protocol):
    def plan_collection(self, request: FutureAgentRequest) -> OrchestrationResponse: ...


class MonitoringPort(Protocol):
    def inspect_palms(self, request: FutureAgentRequest) -> OrchestrationResponse: ...


class ImpactPort(Protocol):
    def estimate_impact(self, request: FutureAgentRequest) -> OrchestrationResponse: ...
