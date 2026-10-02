"""Recompute original live and repaired replay development scores without API."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_v13_development_check import CASES, INDEX, REGISTRY, OUTPUT, CALL_LOG, MANIFEST  # noqa: E402
from scripts.replay_v13_development_check import OUTPUT as REPLAY, REPLAY_MANIFEST  # noqa: E402
from src.citation_audit import sha256  # noqa: E402
from src.evaluate import evaluate, read_csv  # noqa: E402


def score(predictions: Path, audit: Path) -> dict:
    rows, truth = read_csv(predictions), read_csv(CASES)
    if [row["case_id"] for row in rows] != [f"DEV_{number:02d}" for number in range(1, 31)]:
        raise ValueError("Development predictions must contain every approved case exactly once in order.")
    metrics = evaluate(CASES, predictions, REGISTRY, audit, INDEX)
    predicted = {row["case_id"]: row for row in rows}
    actual_risks = [row["case_id"] for row in truth if row["ground_truth_label"] == "review_required"]
    metrics.update(
        prediction_label_counts=dict(Counter(row["predicted_label"] for row in rows)),
        true_positive_risk_count=sum(predicted[case_id]["predicted_label"] == "review_required" for case_id in actual_risks),
        ground_truth_risk_count=len(actual_risks),
        false_negative_case_ids=[case_id for case_id in actual_risks if predicted[case_id]["predicted_label"] != "review_required"],
        non_abstaining_count=sum(row["predicted_label"] != "insufficient_evidence" for row in rows),
        abstention_case_ids=[row["case_id"] for row in rows if row["predicted_label"] == "insufficient_evidence"],
    )
    return metrics


def summary() -> dict:
    original_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    replay_manifest = json.loads(REPLAY_MANIFEST.read_text(encoding="utf-8"))
    for manifest in (original_manifest, replay_manifest):
        if manifest["cases_sha256"] != sha256(CASES) or manifest["index_sha256"] != sha256(INDEX):
            raise ValueError("Cases or source index differ from the recorded run.")
    if replay_manifest["recorded_call_log_sha256"] != sha256(CALL_LOG) or replay_manifest["original_manifest_sha256"] != sha256(MANIFEST):
        raise ValueError("Replay provenance no longer matches the saved live run.")
    if replay_manifest["predictions_sha256"] != sha256(REPLAY):
        raise ValueError("Replay predictions differ from their manifest.")
    calls = [json.loads(line) for line in CALL_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [entry["call_number"] for entry in calls] != list(range(1, 11)):
        raise ValueError("Expected the ordered complete ten-call log.")
    live_rows = read_csv(OUTPUT)
    tokens = sum(entry["usage"]["total_tokens"] for entry in calls)
    if len(calls) != sum(int(row["api_calls"]) for row in live_rows) or tokens != sum(int(row["total_tokens"]) for row in live_rows):
        raise ValueError("Live prediction usage differs from the saved provider call log.")
    for row in read_csv(REPLAY):
        if row["api_called"] != "False" or any(int(row[field]) for field in ("api_calls", "prompt_tokens", "completion_tokens", "total_tokens")):
            raise ValueError("Offline replay must record zero newly charged API usage.")
    return {
        "scope": "Repeatedly tuned synthetic development set; internal first-pass citation audit; NOT fresh external validation.",
        "original_v13_live": {
            "pipeline_freeze_commit": original_manifest["pipeline_freeze_commit"],
            "metrics": score(OUTPUT, REPO_ROOT / "data" / "development_citation_audit_v13.json"),
            "model_calls": len(calls), "prompt_tokens": sum(entry["usage"]["prompt_tokens"] for entry in calls),
            "completion_tokens": sum(entry["usage"]["completion_tokens"] for entry in calls), "total_tokens": tokens,
        },
        "v13_1_recorded_response_replay": {
            "run_type": replay_manifest["run_type"],
            "metrics": score(REPLAY, REPO_ROOT / "data" / "development_citation_audit_v13_1_replay.json"),
            "new_model_calls": 0, "new_api_tokens": 0,
            "reused_recorded_calls": replay_manifest["reused_recorded_calls"],
            "uncertain_citation_case_ids": [item["case_id"] for item in json.loads(
                (REPO_ROOT / "data" / "development_citation_audit_v13_1_replay.json").read_text(encoding="utf-8"))["assessments"]
                if item["verdict"] == "uncertain"],
        },
    }


def main() -> None:
    print(json.dumps(summary(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
