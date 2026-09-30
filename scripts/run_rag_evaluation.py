"""Evaluate the live single-clause RAG system on development cases only."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.evaluate import evaluate  # noqa: E402
from src.live_review import review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=REPO_ROOT / "data" / "development_cases.csv")
    parser.add_argument("--index", type=Path, default=REPO_ROOT / "data" / "derived" / "source_pages.jsonl")
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "data" / "source_registry.csv")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "results" / "development_rag_predictions.csv")
    parser.add_argument("--limit", type=int, default=3, help="Number of retrieved pages included in each model request.")
    args = parser.parse_args()

    with args.cases.open(encoding="utf-8", newline="") as file:
        cases = list(csv.DictReader(file))
    if args.cases.name != "development_cases.csv":
        raise ValueError("This script is intentionally restricted to development_cases.csv.")

    retriever = LocalBM25Retriever.from_jsonl(args.index)
    predictions = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    for position, case in enumerate(cases, start=1):
        result = review_clause(case["housing_type"], case["clause_text"], retriever, limit=args.limit)
        result_data = asdict(result)
        usage = result_data.pop("usage") or {}
        predictions.append(
            {
                "case_id": case["case_id"],
                "predicted_label": result_data["label"],
                "clause_category": result_data["clause_category"],
                "source_id": result_data["source_id"],
                "source_section": result_data["source_section"],
                "reason": result_data["reason"],
                "follow_up_question": result_data["follow_up_question"],
                "abstained": result_data["abstained"],
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        )
        total_prompt_tokens += int(usage.get("prompt_tokens", 0))
        total_completion_tokens += int(usage.get("completion_tokens", 0))
        print(f"[{position}/{len(cases)}] {case['case_id']} -> {result.label}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(predictions[0])
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(predictions)

    summary = evaluate(args.cases, args.output, args.registry)
    summary["prompt_tokens"] = total_prompt_tokens
    summary["completion_tokens"] = total_completion_tokens
    summary["total_tokens"] = total_prompt_tokens + total_completion_tokens
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
