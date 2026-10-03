"""Verify layout-index reproducibility and run exposed development data locally.

No new external cases or labels are loaded, and no performance score is reported.
API-key and network access are blocked during the local review diagnostic.
"""

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.index_paths import CURRENT_PAGE_INDEX, CURRENT_SECTION_INDEX  # noqa: E402
from src.live_review import ModelReviewRequired, review_clause  # noqa: E402
from src.pdf_text import extract_layout_pages  # noqa: E402
from src.retrieval import LocalBM25Retriever  # noqa: E402
from src.source_sections import ANNEXURE_START, CLAUSE_START, compact  # noqa: E402


LOCKED_HASHES = {
    "data/derived/source_sections.jsonl": "caf61131e2cdc05c9390b3ed7661c2e4316c7d4a7eca641a47ed8d24c87f20f1",
    "data/derived/source_pages.jsonl": "2ae147d687de577102f14ef1540eee39e6ad6228b155e774a3727500f9c4a6e6",
    "data/source_registry.csv": "9f6a7d44bd3ee93ca1915907fa320fcd4483ff9699d6f15f13ac678aaa7176e6",
    "data/source_documents/cea_hdb_tenancy_agreement_template_v1_4.pdf": "ec914123e04142de531f8995a528760e7157936017efc2620d94c74e184f8622",
    "data/source_documents/cea_private_tenancy_agreement_template_v1_4.pdf": "bca8b00b386351e1d1a69892c44412af0d0ab90007d379aa045d12122ef8b02a",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    """Byte hash, including line endings; do not normalize binary PDFs."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def operative_ids(pages):
    result = set()
    active = False
    for _, text in pages:
        for raw_line in text.splitlines():
            line = compact(raw_line)
            if line == "OPERATIVE PART":
                active = True
            if not active:
                continue
            if ANNEXURE_START.match(line):
                return result
            match = CLAUSE_START.match(line)
            if match:
                result.add(match.group(1))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save a new diagnostic snapshot; never overwrite.")
    args = parser.parse_args()
    require(args.output is None or not args.output.exists(), "Diagnostic output already exists")
    missing_legacy = []
    for name, expected in LOCKED_HASHES.items():
        if name in {'data/derived/source_sections.jsonl', 'data/derived/source_pages.jsonl'} and not (REPO_ROOT / name).exists():
            missing_legacy.append(name)
            continue
        require(sha256(REPO_ROOT / name) == expected, f"Locked historical reference changed: {name}")

    sections = [json.loads(line) for line in CURRENT_SECTION_INDEX.read_text(encoding="utf-8").splitlines()]
    pages = [json.loads(line) for line in CURRENT_PAGE_INDEX.read_text(encoding="utf-8").splitlines()]
    locators = [(row["source_id"], row["section"]) for row in sections]
    require(len(locators) == len(set(locators)), "Duplicate section locator")
    registry = read_rows(REPO_ROOT / "data/source_registry.csv")
    agreement_sources = {row["source_id"]: row for row in registry
                         if row["use_in_mvp"].lower() == "true"
                         and row["source_kind"] == "tenancy_agreement_template"}
    coverage = []
    for identifier, source in agreement_sources.items():
        source_sections = [row for row in sections if row["source_id"] == identifier]
        expected = operative_ids(extract_layout_pages(
            REPO_ROOT / "data/source_documents" / source["local_filename"]))
        actual = {row["clause_id"] for row in source_sections if not row["clause_id"].startswith("ITEM")}
        require(expected == actual, f"Numbered clause ID coverage mismatch: {identifier}")
        coverage.append({"source_id": identifier, "operative_clause_id_count": len(actual),
                         "section_count": len(source_sections), "missing_or_extra_ids": []})
    for row in sections:
        source = agreement_sources.get(row["source_id"])
        require(source is not None, "A checklist entered the operative-clause index")
        require(row["housing_type"] == source["housing_type"], "Mixed housing metadata")
        require(row["source_kind"] == "tenancy_agreement_template", "Wrong clause source kind")
        if not row["clause_id"].startswith("ITEM"):
            require(35 <= len(row["text"]) <= 1700, "Unbounded or empty operative excerpt")
        require("ANNEXURE A" not in row["text"], "Annexure leaked into operative index")
    require({row["source_id"] for row in pages} ==
            {row["source_id"] for row in registry if row["use_in_mvp"].lower() == "true"},
            "Page-index source coverage mismatch")

    scratch_parent = REPO_ROOT.parent / "v15-scratch"
    scratch_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=scratch_parent) as temporary:
        scratch = Path(temporary).resolve()
        require(scratch.is_relative_to(scratch_parent.resolve()), "Unexpected temporary cleanup target")
        for script, current in (("build_section_index.py", CURRENT_SECTION_INDEX),
                                ("build_source_index.py", CURRENT_PAGE_INDEX)):
            rebuilt = scratch / current.name
            subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / script),
                            "--output", str(rebuilt)], check=True, cwd=REPO_ROOT,
                           capture_output=True, text=True)
            require(sha256(rebuilt) == sha256(current), f"Non-deterministic rebuild: {current.name}")
            attempted_overwrite = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / script), "--output", str(rebuilt)],
                cwd=REPO_ROOT, capture_output=True, text=True)
            require(attempted_overwrite.returncode != 0
                    and "Refusing to overwrite" in attempted_overwrite.stderr,
                    f"Overwrite guard failed: {script}")
            require(sha256(rebuilt) == sha256(current), f"Overwrite attempt modified {current.name}")

    retriever = LocalBM25Retriever.from_jsonl(CURRENT_SECTION_INDEX)
    development = []
    with ExitStack() as stack:
        for target in ("src.live_review.local_api_key", "src.live_review._request_openrouter",
                       "src.evidence_verifier._request_openrouter", "src.rag_review.urlopen",
                       "urllib.request.urlopen", "socket.create_connection", "socket.socket.connect"):
            stack.enter_context(patch(target, side_effect=AssertionError("Offline key/network access attempted")))
        for case in read_rows(REPO_ROOT / "data/development_cases.csv"):
            try:
                result = review_clause(case["housing_type"], case["clause_text"], retriever, allow_api=False)
                development.append({"case_id": case["case_id"],
                                    "status": "local_abstention" if result.abstained else "direct_result"})
            except ModelReviewRequired:
                development.append({"case_id": case["case_id"], "status": "model_needed"})
    report = {
        "version": "v15-offline-index-repair", "api_calls": 0, "api_tokens": 0,
        "hash_method": "SHA-256 of exact file bytes, not the historical text-normalized audit hash",
        "section_index_sha256": sha256(CURRENT_SECTION_INDEX),
        "page_index_sha256": sha256(CURRENT_PAGE_INDEX),
        "section_count": len(sections), "page_count": len(pages),
        "fixed_reference_hash_checks": "passed",
        "legacy_hash_checks": "not available in this checkout" if missing_legacy else "passed",
        "missing_legacy_indices": missing_legacy,
        "deterministic_rebuild_checks": "passed", "overwrite_guards": "passed",
        "numbered_clause_id_coverage": coverage,
        "development_status_counts": dict(Counter(row["status"] for row in development)),
        "development": development,
        "new_external_case_predictions": "not run",
        "scope": "Extraction, boundaries, routing and exposed development local execution only. ID coverage is not a semantic completeness audit. Model-needed cases are not evaluated. No accuracy, substantive citation score or independent generalization claim.",
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as file:
            file.write(serialized)
    print(serialized)


if __name__ == "__main__":
    main()
