"""Run a live Arabic recommendation from the repository root."""

import argparse
from pathlib import Path

from saaf.farms import FarmRepository
from saaf.knowledge.retrieval import DEFAULT_TOP_K

from .recommendation import build_agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--farm-id")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--corpus", type=Path, default=Path("data/saaf_knowledge_base.json"))
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("top-k must be positive")
    try:
        agent = build_agent(args.corpus, FarmRepository(), top_k=args.top_k)
    except ValueError as exc:
        parser.error(str(exc))
    print(agent.recommend(args.query, args.farm_id).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
