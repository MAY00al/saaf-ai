"""Run ingestion, search, and live Arabic retrieval evaluation."""

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from saaf.providers import build_embeddings, embedding_config, load_environment

from .evaluation import evaluate
from .retrieval import DEFAULT_MIN_SCORE, DEFAULT_TOP_K, KnowledgeIndex


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/saaf_knowledge_base.json"))
    parser.add_argument("--index-dir", type=Path, default=os.getenv("SAAF_CHROMA_DIR") or "var/chroma")
    parser.add_argument("--model", help="Override the configured embedding model")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ingest")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--topic")
    benchmark = commands.add_parser("evaluate")
    for command in (search, benchmark):
        command.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
        command.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    args = parser.parse_args()

    if args.command != "ingest":
        if args.top_k < 1 or not -1 <= args.min_score <= 1:
            parser.error("top-k must be positive and min-score must be between -1 and 1")
    try:
        config = embedding_config()
        if args.model:
            config = replace(config, model=args.model)
        embeddings = build_embeddings(config)
    except ValueError as exc:
        parser.error(str(exc))
    index = KnowledgeIndex(
        args.corpus, args.index_dir, embeddings, model=config.model, provider=config.provider,
    )
    added = index.ingest()
    output: dict[str, Any] = {
        "provider": config.provider, "model": config.model, "collection": index.name,
    }
    if args.command == "ingest":
        output.update(added=added, total=len(index.records))
    elif args.command == "evaluate":
        output.update(evaluate(index, top_k=args.top_k, min_score=args.min_score))
    else:
        result = index.search(
            args.query, top_k=args.top_k, min_score=args.min_score, topic=args.topic,
        )
        output.update(
            status=result.status, reason=result.reason,
            hits=[
                {
                    "score": hit.score,
                    "record": hit.record.model_dump(exclude_unset=True),
                    "source": hit.source.model_dump(exclude_unset=True),
                }
                for hit in result.hits
            ],
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
