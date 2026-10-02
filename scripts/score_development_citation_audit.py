"""Score the locked development predictions and their human citation audit offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.evaluate import evaluate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=REPO_ROOT / "data" / "development_cases.csv")
    parser.add_argument("--predictions", type=Path, default=REPO_ROOT / "results" / "development_rag_predictions_v2.csv")
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "data" / "source_registry.csv")
    parser.add_argument("--index", type=Path, default=REPO_ROOT / "data" / "derived" / "source_pages.jsonl")
    parser.add_argument("--audit", type=Path, default=REPO_ROOT / "data" / "development_citation_audit_v2.json")
    args = parser.parse_args()
    if args.cases.name != "development_cases.csv":
        raise ValueError("This scorer is restricted to the development set.")
    summary = evaluate(args.cases, args.predictions, args.registry, args.audit, args.index)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
