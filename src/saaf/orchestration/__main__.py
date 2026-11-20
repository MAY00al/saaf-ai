"""Run a query or an interactive SAAF session."""

import argparse
from functools import cached_property
from pathlib import Path

from saaf.agents.collection import CollectionAgent
from saaf.agents.impact import ImpactAgent, ImpactExplanation
from saaf.agents.monitoring import MonitoringAgent
from saaf.agents.recommendation import RecommendationResponse, build_agent
from saaf.collection.repository import CollectionRepository
from saaf.farms import FarmRepository
from saaf.monitoring.inference import MonitoringSettings
from saaf.providers import build_structured_chat, chat_config, load_environment

from .contracts import ConversationContext
from .evaluation import evaluate_routing
from .graph import Orchestrator


class LiveRecommendation:
    @cached_property
    def agent(self):
        return build_agent(Path("data/saaf_knowledge_base.json"), FarmRepository())

    def recommend(self, query: str, farm_id: str | None = None) -> RecommendationResponse:
        return self.agent.recommend(query, farm_id)


class LiveImpactExplanation:
    @cached_property
    def model(self):
        return build_structured_chat(chat_config(), ImpactExplanation)

    def invoke(self, messages):
        return self.model.invoke(messages)


class LocalMonitoring:
    def __init__(self, farms: FarmRepository) -> None:
        self.farms = farms

    @cached_property
    def agent(self):
        return MonitoringAgent(self.farms, MonitoringSettings.from_environment())

    def inspect_palms(self, farm_id, image, *, whole_farm=False):
        return self.agent.inspect_palms(farm_id, image, whole_farm=whole_farm)

    def confirm_count(self, farm_id, review):
        return self.agent.confirm_count(farm_id, review)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--farm-id")
    parser.add_argument("--image", type=Path, help="Local aerial JPEG or PNG")
    parser.add_argument("--whole-farm", action="store_true", help="Attest that the image covers the entire farm")
    parser.add_argument("--evaluate-routing", action="store_true")
    args = parser.parse_args()
    if args.evaluate_routing:
        print(evaluate_routing().model_dump_json(indent=2))
        return
    load_environment()
    farms = FarmRepository()
    requests = CollectionRepository(farms)
    orchestrator = Orchestrator(
        LiveRecommendation(), collection=CollectionAgent(farms, requests),
        impact=ImpactAgent(farms, requests, LiveImpactExplanation()),
        monitoring=LocalMonitoring(farms),
    )
    if args.query is not None:
        print(orchestrator.run(args.query, farm_id=args.farm_id, image_path=args.image,
                               whole_farm=args.whole_farm).model_dump_json(indent=2))
        return
    context = ConversationContext()
    farm_id = args.farm_id
    image, whole_farm = args.image, args.whole_farm
    print("سَعَف | /farm ID | /image PATH | /whole-farm | /reset | /exit")
    while True:
        try:
            query = input("سَعَف> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if query == "/exit":
            return
        if query == "/reset":
            context, farm_id = ConversationContext(), None
            image, whole_farm = None, False
            print("مُسح سياق المحادثة.")
            continue
        if query.startswith("/farm "):
            farm_id = query.split(maxsplit=1)[1]
            print("سيُستخدم هذا المعرّف في الطلب التالي.")
            continue
        if query.startswith("/image "):
            image = Path(query.split(maxsplit=1)[1].strip().strip('"'))
            whole_farm = False
            print("أُضيفت الصورة للطلب التالي.")
            continue
        if query == "/whole-farm":
            whole_farm = image is not None
            print("أُثبتت تغطية كامل المزرعة للصورة التالية." if whole_farm else "أضف الصورة أولاً.")
            continue
        response = orchestrator.run(query, context=context, farm_id=farm_id, image_path=image,
                                    whole_farm=whole_farm)
        context, farm_id = response.context, None
        image, whole_farm = None, False
        print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
