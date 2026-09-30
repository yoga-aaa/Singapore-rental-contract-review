"""Run a live single-clause RAG review using the ignored local .env key."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.live_review import review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("housing_type", choices=["HDB", "Private Residential"])
    parser.add_argument("clause")
    parser.add_argument("--index", type=Path, default=REPO_ROOT / "data" / "derived" / "source_pages.jsonl")
    args = parser.parse_args()

    retriever = LocalBM25Retriever.from_jsonl(args.index)
    print(json.dumps(asdict(review_clause(args.housing_type, args.clause, retriever)), indent=2))


if __name__ == "__main__":
    main()
