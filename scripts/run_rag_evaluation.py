"""Evaluate the clause-level live RAG system on synthetic development cases only."""

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
from src.live_review import ModelReviewRequired, review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402
from src.index_paths import CURRENT_SECTION_INDEX  # noqa: E402


FIELDS = [
    "case_id", "predicted_label", "clause_category", "source_id", "source_section",
    "evidence_json", "reason", "follow_up_question", "abstained", "api_called", "api_calls",
    "prompt_tokens", "completion_tokens", "total_tokens",
]
GROUNDED_FIELDS = [*FIELDS, "comparisons_json"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=REPO_ROOT / "data" / "development_cases.csv")
    parser.add_argument("--index", type=Path, default=CURRENT_SECTION_INDEX)
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "data" / "source_registry.csv")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "results" / "development_rag_predictions_v10.csv")
    parser.add_argument("--limit", type=int, default=4, help="Maximum clause excerpts sent to the model.")
    parser.add_argument("--max-model-calls", type=int, default=60)
    parser.add_argument("--max-total-tokens", type=int, default=100000)
    args = parser.parse_args()

    if args.cases.name != "development_cases.csv":
        raise ValueError("This script is intentionally restricted to development_cases.csv.")
    if not 1 <= args.limit <= 6 or args.max_model_calls < 1 or args.max_total_tokens < 1000:
        raise ValueError("Invalid retrieval or budget limit.")
    if args.output.exists():
        raise FileExistsError(f"Output already exists; choose a new --output path: {args.output}")

    with args.cases.open(encoding="utf-8", newline="") as file:
        cases = list(csv.DictReader(file))
    if not cases:
        raise ValueError("The development CSV contains no cases.")

    retriever = LocalBM25Retriever.from_jsonl(args.index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prompt_tokens = completion_tokens = model_calls = 0
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=GROUNDED_FIELDS)
        writer.writeheader()
        file.flush()
        for position, case in enumerate(cases, start=1):
            try:
                result = review_clause(case["housing_type"], case["clause_text"], retriever,
                                       limit=args.limit, allow_api=False)
            except ModelReviewRequired:
                if model_calls + 2 > args.max_model_calls:
                    raise RuntimeError("Budget stop: fewer than two model calls remain; partial predictions preserved.")
                if prompt_tokens + completion_tokens >= args.max_total_tokens:
                    raise RuntimeError(f"Token budget stop after {position - 1} cases; partial predictions saved at {args.output}.")
                result = review_clause(case["housing_type"], case["clause_text"], retriever, limit=args.limit)
            result_data = asdict(result)
            usage = result_data["usage"] or {}
            if result.api_called:
                model_calls += int(usage.get("api_calls", 1))
            row = {
                "case_id": case["case_id"],
                "predicted_label": result.label,
                "clause_category": result.clause_category,
                "source_id": result.source_id,
                "source_section": result.source_section,
                "evidence_json": json.dumps(result_data["evidence"], ensure_ascii=False),
                "reason": result.reason,
                "follow_up_question": result.follow_up_question,
                "abstained": result.abstained,
                "api_called": result.api_called,
                "api_calls": int(usage.get("api_calls", 1)) if result.api_called else 0,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "comparisons_json": json.dumps(result_data["comparisons"], ensure_ascii=False),
            }
            writer.writerow(row)
            file.flush()
            prompt_tokens += int(usage.get("prompt_tokens", 0))
            completion_tokens += int(usage.get("completion_tokens", 0))
            print(f"[{position}/{len(cases)}] {case['case_id']} -> {result.label}", flush=True)
            if result.api_called and not usage.get("total_tokens"):
                raise RuntimeError("Provider usage was missing; stopped to avoid unmetered API spending.")
            if prompt_tokens + completion_tokens > args.max_total_tokens:
                raise RuntimeError(f"Budget stop after {position} cases; partial predictions saved at {args.output}.")

    summary = evaluate(args.cases, args.output, args.registry)
    summary.update(
        {
            "model_calls": model_calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
