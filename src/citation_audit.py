"""Validate a locked human citation audit and compute substantive validity."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


VERDICTS = {"supported", "unsupported", "uncertain"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_citation_audit(predictions_path: Path, index_path: Path, audit_path: Path) -> dict[str, float | int]:
    """Score human judgments only after checking they match this exact run and source index."""
    audit: dict[str, Any] = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("predictions_sha256") != sha256(predictions_path):
        raise ValueError("Citation audit does not match the prediction CSV SHA-256.")
    if audit.get("index_sha256") != sha256(index_path):
        raise ValueError("Citation audit does not match the source index SHA-256.")

    with predictions_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    non_abstaining = {row["case_id"]: row for row in rows if row["predicted_label"] != "insufficient_evidence"}
    if len(non_abstaining) != sum(row["predicted_label"] != "insufficient_evidence" for row in rows):
        raise ValueError("Prediction CSV contains duplicate non-abstaining case IDs.")

    with index_path.open(encoding="utf-8") as file:
        chunks = [json.loads(line) for line in file if line.strip()]
    indexed_sections = {(chunk["source_id"], chunk["section"]): chunk for chunk in chunks}
    assessments = audit.get("assessments")
    if not isinstance(assessments, list):
        raise ValueError("Citation audit must contain an assessments list.")
    by_case = {item["case_id"]: item for item in assessments}
    if len(by_case) != len(assessments) or set(by_case) != set(non_abstaining):
        raise ValueError("Citation audit must cover each non-abstaining prediction exactly once.")

    visible_limit = audit.get("visible_characters_per_chunk")
    if not isinstance(visible_limit, int) or visible_limit <= 0:
        raise ValueError("Citation audit has an invalid model-visible excerpt limit.")
    counts = {verdict: 0 for verdict in VERDICTS}
    for case_id, assessment in by_case.items():
        prediction = non_abstaining[case_id]
        pair = (prediction["source_id"], prediction["source_section"])
        if (assessment.get("source_id"), assessment.get("source_section")) != pair:
            raise ValueError(f"Citation audit locator differs from prediction for {case_id}.")
        if pair not in indexed_sections:
            raise ValueError(f"Citation audit references an unknown PDF section for {case_id}.")
        anchor = assessment.get("reference_anchor", "")
        if not anchor or anchor.casefold() not in indexed_sections[pair]["text"][:visible_limit].casefold():
            raise ValueError(f"Citation audit anchor is absent from the model-visible page for {case_id}.")
        if "evidence_json" in prediction:
            try:
                evidence = json.loads(prediction["evidence_json"])
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid evidence JSON for {case_id}.") from error
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(f"Missing cited evidence for {case_id}.")
            first = evidence[0]
            if (first.get("source_id"), first.get("source_section")) != pair:
                raise ValueError(f"Primary citation differs from evidence for {case_id}.")
            for item in evidence:
                cited = (item.get("source_id"), item.get("source_section"))
                source = indexed_sections.get(cited)
                if source is None or not isinstance(item.get("quote"), str):
                    raise ValueError(f"Unknown cited evidence for {case_id}.")
                if item["quote"].casefold() not in source["text"][:visible_limit].casefold():
                    raise ValueError(f"Cited quote is absent from the model-visible section for {case_id}.")
        if assessment.get("verdict") not in VERDICTS or not assessment.get("note", "").strip():
            raise ValueError(f"Citation audit has an invalid verdict or empty note for {case_id}.")
        counts[assessment["verdict"]] += 1

    total = len(non_abstaining)
    return {
        "citation_audited_count": total,
        "citation_supported_count": counts["supported"],
        "citation_unsupported_count": counts["unsupported"],
        "citation_uncertain_count": counts["uncertain"],
        "citation_validity": counts["supported"] / total if total else 0.0,
    }
