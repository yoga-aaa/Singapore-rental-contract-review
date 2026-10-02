"""Run the frozen risk-focused pipeline once on 20 sanitized external clauses.

This runner deliberately never reads the ground-truth file. Do not change the
review pipeline or use these predictions for further tuning.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_rag_evaluation import FIELDS  # noqa: E402
from src.live_review import local_api_key, review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


CASES = REPO_ROOT / "data" / "external_cases_sanitized.csv"
INDEX = REPO_ROOT / "data" / "derived" / "source_sections.jsonl"
REVIEWED_TRUTH = REPO_ROOT / "data" / "external_cases_ground_truth.reviewed.csv"
OUTPUT = REPO_ROOT / "results" / "external_rag_predictions_v12.csv"
MAX_MODEL_CALLS = 40
MAX_TOTAL_TOKENS = 60000
TOKEN_RESERVE_PER_CLAUSE = 8000


def read_holdout() -> list[dict[str, str]]:
    with CASES.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["case_id", "housing_type", "clause_text"]:
            raise ValueError("Unexpected sanitized holdout schema.")
        cases = list(reader)
    expected = [f"EXT_{number:02d}" for number in range(1, 21)]
    if [case["case_id"] for case in cases] != expected:
        raise ValueError("Expected exactly 20 ordered and unique external cases.")
    if any(
        case["housing_type"] not in {"HDB", "Private Residential"} or not case["clause_text"].strip()
        for case in cases
    ):
        raise ValueError("An external case has an invalid housing type or empty clause.")
    return cases


def main() -> None:
    cases = read_holdout()
    if not REVIEWED_TRUTH.exists():
        raise RuntimeError("Independent-reviewed external labels must be locked before prediction.")
    if OUTPUT.exists():
        raise FileExistsError(f"The locked external predictions already exist: {OUTPUT}")
    api_key = local_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required in the environment or local .env file.")
    retriever = LocalBM25Retriever.from_jsonl(INDEX)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    model_calls = total_tokens = 0
    with OUTPUT.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        file.flush()
        for position, case in enumerate(cases, start=1):
            if model_calls + 2 > MAX_MODEL_CALLS or total_tokens + TOKEN_RESERVE_PER_CLAUSE > MAX_TOTAL_TOKENS:
                raise RuntimeError(f"Budget stop after {position - 1} cases; partial output saved at {OUTPUT}.")
            result = review_clause(case["housing_type"], case["clause_text"], retriever, limit=4, api_key=api_key)
            result_data = asdict(result)
            usage = result_data["usage"] or {}
            calls = int(usage.get("api_calls", 1)) if result.api_called else 0
            used = int(usage.get("total_tokens", 0)) if result.api_called else 0
            if result.api_called and (not used or calls < 1):
                raise RuntimeError(f"Provider usage was missing for {case['case_id']}; stopped before recording an unmetered result.")
            model_calls += calls
            total_tokens += used
            writer.writerow({
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
                "api_calls": calls,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": used,
            })
            file.flush()
            print(f"[{position}/20] {case['case_id']} recorded", flush=True)
            if model_calls > MAX_MODEL_CALLS or total_tokens > MAX_TOTAL_TOKENS:
                raise RuntimeError(f"Budget stop after {position} cases; partial output saved at {OUTPUT}.")
    print(json.dumps({"case_count": len(cases), "model_calls": model_calls, "total_tokens": total_tokens}, indent=2))


if __name__ == "__main__":
    main()
