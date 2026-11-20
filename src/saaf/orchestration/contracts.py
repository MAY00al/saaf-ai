"""Shared graph state and ports for SAAF capabilities."""

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypedDict

from saaf.agents.impact import ImpactResult
from saaf.agents.recommendation import RecommendationResponse
from saaf.collection.models import CollectionResult, PickupDraft
from saaf.monitoring.models import CountReview, MonitoringResult
from saaf.geospatial.satellite import Mode

Capability = Literal["recommendation", "collection", "monitoring", "impact"]
Intent = Literal["recommendation", "collection", "monitoring", "impact", "clarification", "unsupported"]
Outcome = Literal[
    "ok", "needs_input", "insufficient_evidence", "insufficient_data", "unavailable",
    "not_implemented", "unsupported", "awaiting_confirmation", "not_found",
]


class ConversationContext(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    farm_id: str | None = None
    previous_query: str | None = Field(default=None, max_length=4000)
    previous_intent: Capability | None = None
    pickup_draft: PickupDraft | None = None
    count_review: CountReview | None = None


class OrchestrationResponse(BaseModel):
    intent: Intent
    status: Outcome
    answer_ar: str
    context: ConversationContext
    candidate_intents: tuple[Capability, ...] = ()
    recommendation: RecommendationResponse | None = None
    collection: CollectionResult | None = None
    impact: ImpactResult | None = None
    monitoring: MonitoringResult | None = None


class AgentState(TypedDict, total=False):
    query: str
    requested_farm_id: str | None
    context: ConversationContext
    intent: Intent
    candidate_intents: tuple[Capability, ...]
    clarification_ar: str | None
    agent_query: str
    collection_continuing: bool
    image_path: Path | None
    whole_farm: bool
    response: OrchestrationResponse


class RecommendationPort(Protocol):
    def recommend(self, query: str, farm_id: str | None = None) -> RecommendationResponse: ...


class CollectionPort(Protocol):
    def plan_collection(
        self, query: str, farm_id: str | None, draft: PickupDraft | None = None,
        *, continuing: bool = False,
    ) -> CollectionResult: ...


class MonitoringPort(Protocol):
    def inspect_palms(self, farm_id: str | None, image: Path | None, *,
                      whole_farm: bool = False) -> MonitoringResult: ...

    def confirm_count(self, farm_id: str | None, review: CountReview | None) -> MonitoringResult: ...

    def inspect_geography(self, farm_id: str | None) -> MonitoringResult: ...

    def inspect_vegetation(self, farm_id: str | None, mode: Mode) -> MonitoringResult: ...


class ImpactPort(Protocol):
    def estimate_impact(self, query: str, *, region: str | None = None) -> ImpactResult: ...
