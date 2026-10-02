"""Review one clause with local retrieval and OpenRouter, or inspect the request offline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.live_review import review_clause  # noqa: E402
from src.rag_review import build_request  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("housing_type", choices=["HDB", "Private Residential"])
    parser.add_argument("clause")
    parser.add_argument("--index", type=Path, default=REPO_ROOT / "data" / "derived" / "source_sections.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Print the structured API request without calling OpenRouter.")
    args = parser.parse_args()

    retriever = LocalBM25Retriever.from_jsonl(args.index)
    evidence = retriever.search(args.clause, args.housing_type)
    if args.dry_run:
        print(json.dumps(build_request(args.housing_type, args.clause, evidence), indent=2))
        return

    print(json.dumps(asdict(review_clause(args.housing_type, args.clause, retriever)), indent=2))


if __name__ == "__main__":
    main()
