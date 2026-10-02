"""Replay the saved v13 responses after a local postprocessing repair, without API.

Every recorded request hash must match the newly constructed request. This is
not a fresh model evaluation and must not be described as one.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_rag_evaluation import GROUNDED_FIELDS  # noqa: E402
from scripts.run_v13_development_check import CASES, INDEX, REGISTRY, CALL_LOG, MANIFEST  # noqa: E402
from src.citation_audit import sha256  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.live_review import review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


OUTPUT = REPO_ROOT / "results" / "development_rag_predictions_v13_1_replay.csv"
REPLAY_MANIFEST = REPO_ROOT / "results" / "development_rag_predictions_v13_1_replay_manifest.json"


class RecordedRequests:
    def __init__(self, entries: list[dict]) -> None:
        self.entries = entries
        self.position = 0
        self.case_id = ""

    def __call__(self, payload: dict, api_key: str):
        if self.position >= len(self.entries):
            raise RuntimeError("Replay needs an unrecorded response; network remains blocked.")
        entry = self.entries[self.position]
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if entry["case_id"] != self.case_id or entry["request_sha256"] != digest:
            raise RuntimeError("Replay request differs from the recorded case/payload; no response may be substituted.")
        self.position += 1
        return copy.deepcopy(entry["response"]), copy.deepcopy(entry["usage"])


def main() -> None:
    if any(path.exists() for path in (OUTPUT, REPLAY_MANIFEST)):
        raise FileExistsError("A replay artifact exists; original and replay results may not be overwritten.")
    original_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(CASES) != original_manifest["cases_sha256"] or sha256(INDEX) != original_manifest["index_sha256"]:
        raise ValueError("Replay cases or source index changed from the paid run.")
    entries = [json.loads(line) for line in CALL_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(entries) != 10 or [entry["call_number"] for entry in entries] != list(range(1, 11)):
        raise ValueError("Expected the complete, ordered ten-call v13 log.")
    with CASES.open(encoding="utf-8", newline="") as file:
        cases = list(csv.DictReader(file))
    if [case["case_id"] for case in cases] != [f"DEV_{number:02d}" for number in range(1, 31)]:
        raise ValueError("Expected the original 30 ordered development cases.")
    manifest = {
        "run_type": "recorded-response replay; NOT a fresh model run",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "new_model_calls": 0, "new_api_tokens": 0,
        "recorded_call_log_sha256": sha256(CALL_LOG), "original_manifest_sha256": sha256(MANIFEST),
        "cases_sha256": sha256(CASES), "index_sha256": sha256(INDEX),
        "harness_sha256": sha256(Path(__file__)),
        "source_hashes": {path.relative_to(REPO_ROOT).as_posix(): sha256(path)
                          for path in sorted((REPO_ROOT / "src").glob("*.py"))},
        "payload_hash_policy": "Every reconstructed draft and verifier request must exactly match its recorded SHA-256.",
    }
    retriever = LocalBM25Retriever.from_jsonl(INDEX)
    recorded = RecordedRequests(entries)
    with OUTPUT.open("x", encoding="utf-8", newline="") as file, ExitStack() as stack:
        stack.enter_context(patch("src.live_review._request_openrouter", recorded))
        stack.enter_context(patch("src.evidence_verifier._request_openrouter", recorded))
        stack.enter_context(patch("src.live_review.local_api_key", side_effect=AssertionError("Offline replay cannot read a key.")))
        stack.enter_context(patch("src.rag_review.urlopen", side_effect=AssertionError("Offline replay cannot access the network.")))
        writer = csv.DictWriter(file, fieldnames=GROUNDED_FIELDS)
        writer.writeheader()
        for case in cases:
            recorded.case_id = case["case_id"]
            result = review_clause(case["housing_type"], case["clause_text"], retriever,
                                   limit=4, api_key="offline-recorded-response")
            data = asdict(result)
            usage = data["usage"] or {}
            writer.writerow({"case_id": case["case_id"], "predicted_label": result.label,
                             "clause_category": result.clause_category, "source_id": result.source_id,
                             "source_section": result.source_section,
                             "evidence_json": json.dumps(data["evidence"], ensure_ascii=False),
                             "reason": result.reason, "follow_up_question": result.follow_up_question,
                             "abstained": result.abstained, "api_called": False, "api_calls": 0,
                             "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                             "comparisons_json": json.dumps(data["comparisons"], ensure_ascii=False)})
            file.flush()
    if recorded.position != len(entries):
        raise RuntimeError("Replay did not consume every recorded response; cannot claim a matching replay.")
    manifest.update(reused_recorded_calls=recorded.position, predictions_sha256=sha256(OUTPUT),
                    metrics_without_citation_audit=evaluate(CASES, OUTPUT, REGISTRY),
                    completed_at_utc=datetime.now(timezone.utc).isoformat())
    with REPLAY_MANIFEST.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps(manifest["metrics_without_citation_audit"], indent=2))
    print("Recorded responses replayed: 10; new model calls: 0; new API tokens: 0.")


if __name__ == "__main__":
    main()
