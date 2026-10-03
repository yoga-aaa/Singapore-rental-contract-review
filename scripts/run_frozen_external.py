"""Validate a frozen private batch, or perform one separately authorized run.

Without --live this does not read an API key, run case predictions, or write results.
Gold annotations are not parsed here; only their file bytes are integrity-hashed.
"""

import argparse
import json
import re
import sys
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.frozen_external import (MeteredTransport, byte_hash, require, safe_member,
                                 verify_authorization, verify_bundle)  # noqa: E402
from src.live_review import local_api_key, review_clause  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--run-name", default="run_v16", help="New private output name; never overwrite a previous run")
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    checked = verify_bundle(bundle, REPO_ROOT)
    if not args.live:
        print(json.dumps({"status": "preflight_passed_authorization_pending",
                          "case_count": len(checked["cases"]),
                          "manifest_sha256": checked["manifest_sha256"],
                          "api_calls": 0, "api_tokens": 0, "case_predictions": 0,
                          "proposed_budget_usd": checked["config"]["max_cost_usd"]}, indent=2))
        return
    approval = verify_authorization(args.authorization, checked["manifest_sha256"], checked["config"])
    require(args.authorization.resolve().is_relative_to(bundle.parent), "Keep approval in the private batch folder")
    require(bool(re.fullmatch(r'run_[A-Za-z0-9_]+', args.run_name)), 'Invalid private run name')
    output_dir = safe_member(bundle.parent, args.run_name)
    require(not output_dir.exists(), "Run directory exists: do not overwrite, resume or silently repeat")
    api_key = local_api_key()
    require(bool(api_key), "An API key is required; never put it in the frozen bundle")
    retriever = LocalBM25Retriever.from_jsonl(safe_member(bundle, checked["manifest"]["section_index_path"]))
    output_dir.mkdir()
    started = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
               "bundle_manifest_sha256": checked["manifest_sha256"],
               "authorization_sha256": byte_hash(args.authorization),
               "run_type": checked['manifest'].get('evaluation_type', 'external-source diagnostic, not strictly unexposed holdout'),
               "freeze_version": checked['manifest']['freeze_version'],
               "budget": {key: checked["config"][key] for key in
                          ("max_cost_usd", "max_model_calls", "max_total_tokens")},
               "case_count": len(checked["cases"])}
    with (output_dir / "run_started.json").open("x", encoding="utf-8") as file:
        json.dump(started, file, ensure_ascii=False, indent=2)
    completed = []
    status, failure = "complete", None
    with (output_dir / "calls.jsonl").open("x", encoding="utf-8", newline="\n") as log, \
            (output_dir / "predictions.jsonl").open("x", encoding="utf-8", newline="\n") as output, \
            ExitStack() as stack:
        meter = MeteredTransport(checked["config"], log)
        stack.enter_context(patch("src.live_review._request_openrouter", meter))
        stack.enter_context(patch("src.evidence_verifier._request_openrouter", meter))
        try:
            for case in checked["cases"]:
                # Catch source edits even between cases; inputs remain in locked memory.
                require(byte_hash(bundle / "manifest.json") == checked["manifest_sha256"],
                        "Manifest changed during the run")
                verify_bundle(bundle, REPO_ROOT)
                meter.case_id = case["case_id"]
                before = meter.accounting()
                result = review_clause(case["housing_type"], case["clause_text"], retriever,
                                       limit=checked["config"]["retrieval_limit"], api_key=api_key)
                after = meter.accounting()
                cost = str(meter.cost - Decimal(before["cost_usd"]))
                row = {"case_id": case["case_id"], "result": asdict(result),
                       "accounting": {"api_calls": after["api_calls"] - before["api_calls"],
                                      "total_tokens": after["total_tokens"] - before["total_tokens"],
                                      "cost_usd": cost}}
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                completed.append(case["case_id"])
                print(f"{case['case_id']} recorded", flush=True)
        except Exception as error:
            status, failure = "partial_stopped", type(error).__name__
        final = {"status": status, "completed_case_ids": completed, "failure_type": failure,
                 "accounting": meter.accounting(), "metrics": None,
                 "citation_audit": "pending; verifier approval is not a human audit",
                 "predictions_sha256": byte_hash(output_dir / "predictions.jsonl"),
                 "calls_sha256": byte_hash(output_dir / "calls.jsonl"),
                 "cost_reporting": "cost per clause in prediction accounting; batch total is not per-agreement cost",
                 "finished_at_utc": datetime.now(timezone.utc).isoformat()}
        with (output_dir / "run_finished.json").open("x", encoding="utf-8") as file:
            json.dump(final, file, ensure_ascii=False, indent=2)
    print(json.dumps(final, ensure_ascii=False, indent=2))
    if status != "complete":
        raise RuntimeError("Run stopped; partial artifacts preserved; no automatic retry or metrics")


if __name__ == "__main__":
    main()
