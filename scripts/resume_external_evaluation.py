"""Append only missing external cases to the hash-locked 18-row v12 checkpoint.

This is an evaluation-harness recovery, not a change to the review model,
retriever, prompt, rules, or locked ground-truth labels.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_external_evaluation import (  # noqa: E402
    CASES, FIELDS, INDEX, OUTPUT, REVIEWED_TRUTH, read_holdout,
)
from src.live_review import local_api_key, review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


EXPECTED_PARTIAL_SHA256 = "658c0d9760e7118e9c8d5b4beda50c7b57ed3af71fa95600fb11ad5efe1d0063"
EXPECTED_CASES_SHA256 = "446b3084fbe59157bb137a7e574ecdd3a9af358d7a29ea418ae71350d56e0020"
EXPECTED_TRUTH_SHA256 = "1ecdae6bb643223439f871bbedda6f4a858e7a0e17ff00b98551db4b4103a8e7"
EXPECTED_INDEX_SHA256 = "caf61131e2cdc05c9390b3ed7661c2e4316c7d4a7eca641a47ed8d24c87f20f1"
EXTRA_MODEL_CALLS = 4
EXTRA_TOTAL_TOKENS = 20000
TOKEN_RESERVE = 8000


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_checkpoint() -> list[dict[str, str]]:
    for path, expected in (
        (CASES, EXPECTED_CASES_SHA256),
        (REVIEWED_TRUTH, EXPECTED_TRUTH_SHA256),
        (INDEX, EXPECTED_INDEX_SHA256),
        (OUTPUT, EXPECTED_PARTIAL_SHA256),
    ):
        if not path.exists() or file_sha256(path) != expected:
            raise RuntimeError(f"Frozen input or 18-row checkpoint changed: {path}")
    with OUTPUT.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != FIELDS:
            raise ValueError("Partial prediction schema changed.")
        rows = list(reader)
    if [row["case_id"] for row in rows] != [f"EXT_{number:02d}" for number in range(1, 19)]:
        raise ValueError("Partial predictions must contain exactly EXT_01 through EXT_18.")
    if sum(int(row["api_calls"]) for row in rows) != 30 or sum(int(row["total_tokens"]) for row in rows) != 53026:
        raise ValueError("Partial usage does not match the frozen run.")
    return rows


def main() -> None:
    cases = read_holdout()
    checkpoint = checked_checkpoint()
    api_key = local_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required in the environment or local .env file.")
    retriever = LocalBM25Retriever.from_jsonl(INDEX)
    added_calls = added_tokens = 0
    with OUTPUT.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        for case in cases[len(checkpoint):]:
            if added_calls + 2 > EXTRA_MODEL_CALLS or added_tokens + TOKEN_RESERVE > EXTRA_TOTAL_TOKENS:
                raise RuntimeError("Additional authorized budget is exhausted; partial output preserved.")
            result = review_clause(case["housing_type"], case["clause_text"], retriever, limit=4, api_key=api_key)
            data = asdict(result)
            usage = data["usage"] or {}
            calls = int(usage.get("api_calls", 1)) if result.api_called else 0
            used = int(usage.get("total_tokens", 0)) if result.api_called else 0
            if result.api_called and (calls < 1 or used < 1):
                raise RuntimeError(f"Provider usage missing for {case['case_id']}; no unmetered result recorded.")
            if added_calls + calls > EXTRA_MODEL_CALLS or added_tokens + used > EXTRA_TOTAL_TOKENS:
                raise RuntimeError(f"Additional authorized budget exceeded at {case['case_id']}; result not recorded.")
            writer.writerow({
                "case_id": case["case_id"], "predicted_label": result.label,
                "clause_category": result.clause_category, "source_id": result.source_id,
                "source_section": result.source_section,
                "evidence_json": json.dumps(data["evidence"], ensure_ascii=False),
                "reason": result.reason, "follow_up_question": result.follow_up_question,
                "abstained": result.abstained, "api_called": result.api_called,
                "api_calls": calls, "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0), "total_tokens": used,
            })
            file.flush()
            added_calls += calls
            added_tokens += used
            print(f"{case['case_id']} recorded", flush=True)
    print(json.dumps({"additional_model_calls": added_calls, "additional_tokens": added_tokens,
                      "completed_cases": len(checkpoint) + 2}, indent=2))


if __name__ == "__main__":
    main()
