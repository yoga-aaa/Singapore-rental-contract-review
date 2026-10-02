"""Diagnose v13 locally and replay known v12 failures; never produce new LLM predictions.

The exposed 20 cases are regression material after v12, not a fresh holdout.
Network entrypoints and API-key access are blocked during this script.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.citation_audit import sha256  # noqa: E402
from src.live_review import ModelReviewRequired, review_clause, validate_output  # noqa: E402
from src.retrieval import LocalBM25Retriever, RetrievedChunk, query_topics  # noqa: E402


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new JSON snapshot; existing files are never overwritten.")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError(args.output)
    index = REPO_ROOT / "data" / "derived" / "source_sections.jsonl"
    predictions = REPO_ROOT / "results" / "external_rag_predictions_v12.csv"
    retriever = LocalBM25Retriever.from_jsonl(index)
    failures: list[dict] = []
    development: list[dict] = []
    retrieval_coverage: list[dict] = []
    with ExitStack() as stack:
        for target in ("src.live_review.local_api_key", "src.live_review._request_openrouter",
                       "src.evidence_verifier._request_openrouter", "src.rag_review.urlopen"):
            stack.enter_context(patch(target, side_effect=AssertionError("Offline diagnostic attempted key/network access.")))
        for case in rows(REPO_ROOT / "data" / "development_cases.csv"):
            try:
                result = review_clause(case["housing_type"], case["clause_text"], retriever, allow_api=False)
                status = "local_abstention" if result.abstained else "direct_result"
                development.append({"case_id": case["case_id"], "status": status, "result": asdict(result)})
            except ModelReviewRequired:
                development.append({"case_id": case["case_id"], "status": "model_needed"})
        cases = {case["case_id"]: case for case in rows(REPO_ROOT / "data" / "external_cases_sanitized.csv")}
        for case in cases.values():
            found = retriever.search(case["clause_text"], case["housing_type"], limit=4)
            required = query_topics(case["clause_text"])
            retrieved_topics = {topic for chunk in found for topic in chunk.topics}
            retrieval_coverage.append({"case_id": case["case_id"], "identified_topics": sorted(required),
                                       "missing_topics": sorted(required - retrieved_topics),
                                       "sections": [chunk.section for chunk in found]})
        for old in rows(predictions):
            if old["predicted_label"] == "insufficient_evidence":
                continue
            case = cases[old["case_id"]]
            evidence = json.loads(old["evidence_json"])
            available = [chunk for chunk in retriever.search(case["clause_text"], case["housing_type"], limit=6)]
            # Replay against exactly the historic cited sections as well as today's
            # retrieval. This separates inference rejection from ranking changes.
            pairs = {(entry["source_id"], entry["source_section"]) for entry in evidence}
            for chunk in retriever.chunks:
                if (chunk["source_id"], chunk["section"]) in pairs and not any(
                    (item.source_id, item.section) == (chunk["source_id"], chunk["section"]) for item in available
                ):
                    available.append(RetrievedChunk(**{key: chunk[key] for key in (
                        "source_id", "housing_type", "source_kind", "title", "page_number", "section", "text", "clause_id", "topics"
                    )}, score=0.0))
            raw = {key: old[key] for key in ("clause_category", "source_id", "source_section", "reason", "follow_up_question")}
            raw.update(label=old["predicted_label"], evidence=evidence, abstained=False)
            checked = validate_output(raw, available, clause_text=case["clause_text"])
            failures.append({"case_id": old["case_id"], "old_label": old["predicted_label"],
                             "status": "rejected_by_local_checks" if checked.abstained else "passes_local_checks_only",
                             "diagnostic": checked.reason if checked.abstained else "Semantic model/human checking is still required.",
                             "identified_topics": sorted(query_topics(case["clause_text"]))})
    report = {
        "version": "v13-offline", "model_calls": 0, "api_tokens": 0,
        "scope": "Local rules, retrieval, and replay of saved v12 reasons only. No new model accuracy or citation score.",
        "prediction_snapshot_sha256": sha256(predictions), "index_sha256": sha256(index),
        "development_status_counts": dict(Counter(case["status"] for case in development)),
        "development": development, "legacy_reason_replay": failures,
        "retrieval_topic_coverage": retrieval_coverage,
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8", newline="\n") as file:
            file.write(serialized)
    else:
        print(serialized, end="")
    print(json.dumps({"model_calls": 0, "api_tokens": 0,
                      "development_status_counts": report["development_status_counts"],
                      "legacy_replay_status_counts": dict(Counter(item["status"] for item in failures)),
                      "retrieval_cases_with_missing_topics": [item["case_id"] for item in retrieval_coverage if item["missing_topics"]]}, indent=2))


if __name__ == "__main__":
    main()
