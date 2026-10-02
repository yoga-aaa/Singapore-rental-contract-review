"""Run the approved v13 synthetic development check once with a metered call log.

The review pipeline is unchanged. Both model entrypoints are wrapped for a
conservative before-call token reservation and after-call provider accounting.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_rag_evaluation import GROUNDED_FIELDS  # noqa: E402
from src.citation_audit import sha256  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.live_review import review_clause  # noqa: E402
from src.rag_review import _request_openrouter  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


CASES = REPO_ROOT / "data" / "development_cases.csv"
INDEX = REPO_ROOT / "data" / "derived" / "source_sections.jsonl"
REGISTRY = REPO_ROOT / "data" / "source_registry.csv"
OUTPUT = REPO_ROOT / "results" / "development_rag_predictions_v13.csv"
CALL_LOG = REPO_ROOT / "results" / "development_rag_predictions_v13_calls.jsonl"
MANIFEST = REPO_ROOT / "results" / "development_rag_predictions_v13_manifest.json"
MODEL_CALL_LIMIT = 10
TOKEN_LIMIT = 40000


class MeteredRequests:
    def __init__(self, request: Callable, log: TextIO, max_calls: int = MODEL_CALL_LIMIT,
                 max_tokens: int = TOKEN_LIMIT) -> None:
        self.request = request
        self.log = log
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.calls = self.tokens = 0
        self.case_id = ""
        self.stopped = False

    @staticmethod
    def reservation(payload: dict[str, Any]) -> int:
        # UTF-8 payload bytes are deliberately much more conservative than an
        # English token/character estimate. Include schema and a framing reserve.
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return len(body) + int(payload["max_tokens"]) + 1024

    def __call__(self, payload: dict[str, Any], api_key: str):
        reserve = self.reservation(payload)
        if self.stopped or self.calls >= self.max_calls or self.tokens + reserve > self.max_tokens:
            raise RuntimeError("Before-call budget stop; saved predictions and call log preserved.")
        self.calls += 1
        try:
            response, usage = self.request(payload, api_key)
        except Exception as error:
            self.stopped = True
            self.log.write(json.dumps({"case_id": self.case_id, "call_number": self.calls,
                                       "model": payload["model"], "error_type": type(error).__name__,
                                       "usage": "unavailable; stop without retry"}) + "\n")
            self.log.flush()
            raise
        entry = {"case_id": self.case_id, "call_number": self.calls,
                 "model": payload["model"], "request_sha256": hashlib.sha256(
                     json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
                 "reserved_tokens": reserve, "usage": usage, "response": response}
        self.log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.log.flush()
        if not isinstance(usage, dict) or type(usage.get("total_tokens")) is not int or usage["total_tokens"] < 1:
            self.stopped = True
            raise RuntimeError("Provider usage is missing; no more calls may be made.")
        self.tokens += usage["total_tokens"]
        if self.tokens > self.max_tokens or usage["total_tokens"] > reserve:
            self.stopped = True
            raise RuntimeError("Provider usage exceeded the reservation; stopped with call log preserved.")
        return response, usage


def main() -> None:
    if any(path.exists() for path in (OUTPUT, CALL_LOG, MANIFEST)):
        raise FileExistsError("A v13 run artifact exists; do not overwrite or silently repeat the run.")
    with CASES.open(encoding="utf-8", newline="") as file:
        cases = list(csv.DictReader(file))
    if [case["case_id"] for case in cases] != [f"DEV_{number:02d}" for number in range(1, 31)]:
        raise ValueError("Expected exactly the approved 30 ordered synthetic development cases.")
    manifest = {"pipeline_freeze_commit": "599bfb51ac5120d1315067576d548c149a6fd00b",
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "harness_sha256": sha256(Path(__file__)),
                "cases_sha256": sha256(CASES), "index_sha256": sha256(INDEX),
                "source_hashes": {path.relative_to(REPO_ROOT).as_posix(): sha256(path)
                                  for path in sorted((REPO_ROOT / "src").glob("*.py"))},
                "max_model_calls": MODEL_CALL_LIMIT, "max_total_tokens": TOKEN_LIMIT,
                "reservation": "UTF-8 JSON request bytes + max completion tokens + 1024 framing reserve."}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")
    retriever = LocalBM25Retriever.from_jsonl(INDEX)
    with CALL_LOG.open("x", encoding="utf-8", newline="\n") as log, \
         OUTPUT.open("x", encoding="utf-8", newline="") as file, ExitStack() as stack:
        meter = MeteredRequests(_request_openrouter, log)
        stack.enter_context(patch("src.live_review._request_openrouter", meter))
        stack.enter_context(patch("src.evidence_verifier._request_openrouter", meter))
        writer = csv.DictWriter(file, fieldnames=GROUNDED_FIELDS)
        writer.writeheader()
        file.flush()
        for case in cases:
            meter.case_id = case["case_id"]
            result = review_clause(case["housing_type"], case["clause_text"], retriever, limit=4)
            data = asdict(result)
            usage = data["usage"] or {}
            writer.writerow({"case_id": case["case_id"], "predicted_label": result.label,
                             "clause_category": result.clause_category, "source_id": result.source_id,
                             "source_section": result.source_section,
                             "evidence_json": json.dumps(data["evidence"], ensure_ascii=False),
                             "reason": result.reason, "follow_up_question": result.follow_up_question,
                             "abstained": result.abstained, "api_called": result.api_called,
                             "api_calls": usage.get("api_calls", 1) if result.api_called else 0,
                             "prompt_tokens": usage.get("prompt_tokens", 0),
                             "completion_tokens": usage.get("completion_tokens", 0),
                             "total_tokens": usage.get("total_tokens", 0),
                             "comparisons_json": json.dumps(data["comparisons"], ensure_ascii=False)})
            file.flush()
            print(f"{case['case_id']} recorded", flush=True)
    summary = evaluate(CASES, OUTPUT, REGISTRY)
    summary.update(model_calls=meter.calls, total_tokens=meter.tokens)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
