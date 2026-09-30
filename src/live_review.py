"""Production-ready single-clause RAG entrypoint with resilient PDF page citations."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from src.rag_review import LABELS, OUTPUT_SCHEMA, ReviewResult, _request_openrouter, abstain, build_request
from src.retrieval import LocalBM25Retriever, RetrievedChunk


REPO_ROOT = Path(__file__).resolve().parents[1]


def local_api_key() -> str | None:
    """Read the ignored local .env only when no process-level key is set."""
    configured = os.getenv("OPENROUTER_API_KEY")
    if configured:
        return configured
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def validate_output(raw: dict[str, Any], chunks: list[RetrievedChunk], usage: dict[str, int] | None = None) -> ReviewResult:
    required_fields = set(OUTPUT_SCHEMA["schema"]["required"])
    if not isinstance(raw, dict) or set(raw) != required_fields:
        return abstain("The model output did not match the required review schema.")

    label = raw.get("label")
    if label not in LABELS or not isinstance(raw.get("abstained"), bool):
        return abstain("The model output contained an invalid label or abstention state.")
    if label == "insufficient_evidence":
        return abstain(str(raw.get("reason") or "The available references were insufficient for a supported comparison."))

    source_id = str(raw.get("source_id", ""))
    source_section = str(raw.get("source_section", ""))
    retrieved_source_ids = {chunk.source_id for chunk in chunks}
    exact_section_match = source_section in {chunk.section for chunk in chunks}
    page_match = re.fullmatch(r"Page\s+(\d+)", source_section, flags=re.IGNORECASE)
    printed_page = int(page_match.group(1)) if page_match else None
    page_is_retrieved = printed_page is not None and any(
        printed_page in {chunk.page_number, chunk.page_number - 1} for chunk in chunks
    )

    if raw.get("abstained") or source_id not in retrieved_source_ids or not (exact_section_match or page_is_retrieved):
        return abstain("The model did not provide a citation from the retrieved reference excerpts.")

    return ReviewResult(
        label=label,
        clause_category=str(raw["clause_category"]),
        reason=str(raw["reason"]),
        follow_up_question=str(raw["follow_up_question"]),
        source_id=source_id,
        source_section=source_section,
        abstained=False,
        usage=usage,
    )


def review_clause(housing_type: str, clause_text: str, retriever: LocalBM25Retriever, limit: int = 3) -> ReviewResult:
    if housing_type not in {"HDB", "Private Residential"}:
        return abstain("Select HDB or Private Residential before requesting a review.")
    if not clause_text.strip():
        return abstain("Provide a contract clause before requesting a review.")

    chunks = retriever.search(clause_text, housing_type, limit=limit)
    if not chunks:
        return abstain("No relevant registered reference evidence was retrieved.")

    api_key = local_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required in the environment or local .env file.")
    raw, usage = _request_openrouter(build_request(housing_type, clause_text, chunks), api_key)
    return validate_output(raw, chunks, usage)
