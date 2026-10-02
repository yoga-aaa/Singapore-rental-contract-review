"""Score the completed, frozen 20-case external evaluation without API calls."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.evaluate import evaluate  # noqa: E402


TRUTH = REPO_ROOT / "data" / "external_cases_ground_truth.reviewed.csv"
PREDICTIONS = REPO_ROOT / "results" / "external_rag_predictions_v12.csv"
REGISTRY = REPO_ROOT / "data" / "source_registry.csv"
INDEX = REPO_ROOT / "data" / "derived" / "source_sections.jsonl"
AUDIT = REPO_ROOT / "data" / "external_citation_audit_v12.json"


def main() -> None:
    with TRUTH.open(encoding="utf-8", newline="") as file:
        truth = list(csv.DictReader(file))
    with PREDICTIONS.open(encoding="utf-8", newline="") as file:
        predictions = list(csv.DictReader(file))
    expected_ids = [f"EXT_{number:02d}" for number in range(1, 21)]
    if [row["case_id"] for row in truth] != expected_ids:
        raise ValueError("Reviewed truth must contain EXT_01 through EXT_20 once, in order.")
    if [row["case_id"] for row in predictions] != expected_ids:
        raise ValueError("Predictions must contain EXT_01 through EXT_20 once, in order.")

    metrics = evaluate(TRUTH, PREDICTIONS, REGISTRY, AUDIT, INDEX)
    truth_by_id = {row["case_id"]: row for row in truth}
    metrics["ground_truth_label_counts"] = dict(Counter(row["ground_truth_label"] for row in truth))
    metrics["prediction_label_counts"] = dict(Counter(row["predicted_label"] for row in predictions))
    metrics["false_negative_case_ids"] = [
        row["case_id"] for row in predictions
        if truth_by_id[row["case_id"]]["ground_truth_label"] == "review_required"
        and row["predicted_label"] != "review_required"
    ]
    metrics["model_calls"] = sum(int(row["api_calls"]) for row in predictions)
    metrics["prompt_tokens"] = sum(int(row["prompt_tokens"]) for row in predictions)
    metrics["completion_tokens"] = sum(int(row["completion_tokens"]) for row in predictions)
    metrics["total_tokens"] = sum(int(row["total_tokens"]) for row in predictions)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
