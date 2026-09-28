"""Inspect the local BM25 retriever without sending content to a model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.retrieval import LocalBM25Retriever  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("housing_type", choices=["HDB", "Private Residential"])
    parser.add_argument("query")
    parser.add_argument("--index", type=Path, default=REPO_ROOT / "data" / "derived" / "source_pages.jsonl")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    retriever = LocalBM25Retriever.from_jsonl(args.index)
    for rank, result in enumerate(retriever.search(args.query, args.housing_type, args.limit), start=1):
        preview = result.text[:300].replace("\n", " ")
        print(f"{rank}. {result.source_id} | {result.section} | page {result.page_number} | score={result.score}")
        print(f"   {preview}\n")


if __name__ == "__main__":
    main()
