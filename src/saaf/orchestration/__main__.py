"""Run a query or an interactive SAAF session."""

import argparse
from functools import cached_property
from pathlib import Path

from saaf.agents.recommendation import RecommendationResponse, build_agent
from saaf.farms import FarmRepository
from saaf.providers import load_environment

from .contracts import ConversationContext
from .evaluation import evaluate_routing
from .graph import Orchestrator


class LiveRecommendation:
    @cached_property
    def agent(self):
        return build_agent(Path("data/saaf_knowledge_base.json"), FarmRepository())

    def recommend(self, query: str, farm_id: str | None = None) -> RecommendationResponse:
        return self.agent.recommend(query, farm_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--farm-id")
    parser.add_argument("--evaluate-routing", action="store_true")
    args = parser.parse_args()
    if args.evaluate_routing:
        print(evaluate_routing().model_dump_json(indent=2))
        return
    load_environment()
    orchestrator = Orchestrator(LiveRecommendation())
    if args.query is not None:
        print(orchestrator.run(args.query, farm_id=args.farm_id).model_dump_json(indent=2))
        return
    context = ConversationContext()
    farm_id = args.farm_id
    print("سَعَف | /farm ID لتحديد المزرعة | /reset لمسح السياق | /exit للخروج")
    while True:
        try:
            query = input("سَعَف> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if query == "/exit":
            return
        if query == "/reset":
            context, farm_id = ConversationContext(), None
            print("مُسح سياق المحادثة.")
            continue
        if query.startswith("/farm "):
            farm_id = query.split(maxsplit=1)[1]
            print("سيُستخدم هذا المعرّف في الطلب التالي.")
            continue
        response = orchestrator.run(query, context=context, farm_id=farm_id)
        context, farm_id = response.context, None
        print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
