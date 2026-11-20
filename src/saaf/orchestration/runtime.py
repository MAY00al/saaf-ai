"""Shared lazy wiring for the CLI and API."""

from functools import cached_property
from pathlib import Path
from threading import Lock

from saaf.agents.collection import CollectionAgent
from saaf.agents.impact import ImpactAgent, ImpactExplanation
from saaf.agents.monitoring import MonitoringAgent
from saaf.agents.recommendation import RecommendationResponse, build_agent
from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository
from saaf.geospatial.repository import GeographyRepository
from saaf.geospatial.service import GeoMonitoring
from saaf.monitoring.inference import MonitoringSettings
from saaf.providers import build_structured_chat, chat_config

from .graph import Orchestrator


class LiveRecommendation:
    def __init__(self, farms: FarmRepository) -> None:
        self.farms = farms
        self._lock = Lock()

    @cached_property
    def agent(self):
        return build_agent(Path("data/saaf_knowledge_base.json"), self.farms)

    def recommend(self, query: str, farm_id: str | None = None) -> RecommendationResponse:
        with self._lock:
            agent = self.agent
        return agent.recommend(query, farm_id)


class LiveImpactExplanation:
    @cached_property
    def model(self):
        return build_structured_chat(chat_config(), ImpactExplanation)

    def invoke(self, messages):
        return self.model.invoke(messages)


class LocalMonitoring:
    def __init__(
        self, farms: FarmRepository, output_dir: Path | None = None, *, geospatial: GeoMonitoring | None = None,
    ) -> None:
        self.farms = farms
        self.geospatial = geospatial
        self.output_dir = output_dir
        self._lock = Lock()

    @cached_property
    def agent(self):
        settings = MonitoringSettings.from_environment()
        if self.output_dir is not None:
            settings = settings.model_copy(update={"output_dir": self.output_dir})
        return MonitoringAgent(self.farms, settings, geospatial=self.geospatial)

    def inspect_geography(self, farm_id):
        return self.agent.inspect_geography(farm_id)

    def inspect_vegetation(self, farm_id, mode):
        return self.agent.inspect_vegetation(farm_id, mode)

    def inspect_palms(self, farm_id, image, *, whole_farm=False):
        with self._lock:
            return self.agent.inspect_palms(farm_id, image, whole_farm=whole_farm)

    def confirm_count(self, farm_id, review):
        with self._lock:
            return self.agent.confirm_count(farm_id, review)


def build_orchestrator(
    farms: FarmRepository, requests: CollectionRepository, *, image_output: Path | None = None,
    geospatial: GeoMonitoring | None = None,
) -> tuple[Orchestrator, ImpactAgent]:
    impact = ImpactAgent(farms, requests, LiveImpactExplanation())
    return Orchestrator(
        LiveRecommendation(farms), collection=CollectionAgent(farms, requests),
        impact=impact, monitoring=LocalMonitoring(
            farms, image_output, geospatial=geospatial or GeoMonitoring(GeographyRepository(farms)),
        ),
    ), impact
