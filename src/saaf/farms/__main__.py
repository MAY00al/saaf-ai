"""Seed the local simulated farm database."""

import argparse
from pathlib import Path

from .repository import FarmRepository
from .seed import DEFAULT_SEED_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seed"])
    parser.add_argument("--db", type=Path)
    parser.add_argument("--source", type=Path, default=DEFAULT_SEED_PATH)
    args = parser.parse_args()
    repository = FarmRepository(args.db)
    added = repository.seed(args.source)
    print(f"Inserted {added} simulated farms into {repository.path}")


if __name__ == "__main__":
    main()
