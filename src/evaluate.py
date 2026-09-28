"""Compute the four project evaluation metrics from locked labels and predictions."""

from __future__ import annotations

import csv
from pathlib import Path


REVIEW = "review_required"
ABSTAIN = "insufficient_evidence"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def evaluate(ground_truth_path: Path, predictions_path: Path, registry_path: Path) -> dict[str, float | int]:
    truth_rows = {row["case_id"]: row for row in read_csv(ground_truth_path)}
    prediction_rows = {row["case_id"]: row for row in read_csv(predictions_path)}
    registry_ids = {row["source_id"] for row in read_csv(registry_path)}

    if set(truth_rows) != set(prediction_rows):
        raise ValueError("Ground truth and predictions must contain exactly the same case IDs.")

    true_review = [case_id for case_id, row in truth_rows.items() if row["ground_truth_label"] == REVIEW]
    predicted_review = [case_id for case_id, row in prediction_rows.items() if row["predicted_label"] == REVIEW]
    true_positive = sum(case_id in predicted_review for case_id in true_review)

    non_abstaining = [row for row in prediction_rows.values() if row["predicted_label"] != ABSTAIN]
    citation_valid = [
        row
        for row in non_abstaining
        if row.get("source_id") in registry_ids and bool(row.get("source_section", "").strip())
    ]
    unsafe_non_abstentions = [
        case_id
        for case_id, truth in truth_rows.items()
        if truth["ground_truth_label"] == ABSTAIN
        and prediction_rows[case_id]["predicted_label"] != ABSTAIN
    ]

    return {
        "case_count": len(truth_rows),
        "review_required_recall": true_positive / len(true_review) if true_review else 0.0,
        "review_required_precision": true_positive / len(predicted_review) if predicted_review else 0.0,
        "citation_validity": len(citation_valid) / len(non_abstaining) if non_abstaining else 0.0,
        "unsafe_non_abstention_rate": len(unsafe_non_abstentions) / len(truth_rows) if truth_rows else 0.0,
    }
