"""Explicit source-to-clause contrasts that require review, not legal judgments."""

from __future__ import annotations

import re

from src.rag_review import ReviewResult
from src.retrieval import RetrievedChunk


def direct_late_rent_review(clause_text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    """Compare a daily late charge with the template's explicit default-interest term."""
    if len(clause_text) > 250 or not all(re.search(pattern, clause_text, re.IGNORECASE) for pattern in (
        r"\b(?:late|unpaid|overdue)\b", r"\brent\b", r"S\$\s*\d+", r"\b(?:daily|per day)\b",
    )):
        return None
    source = next((item for item in chunks if "default in rent" in item.text.lower()
                   and "ten percent (10%) per annum" in item.text), None)
    if source is None:
        return None
    return ReviewResult(
        label="review_required", clause_category="rent_utilities",
        reason="The clause imposes a fixed daily late-rent charge, while the cited CEA template sets interest at 10% per annum after rent remains unpaid seven days.",
        follow_up_question="How is the proposed daily charge calculated and agreed?",
        source_id=source.source_id, source_section=source.section, abstained=False,
        evidence=({"source_id": source.source_id, "source_section": source.section,
                   "topic": "rent", "quote": source.text},),
    )


def direct_discretionary_rent_review(clause_text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    """Flag unilateral rent variation against the agreement's recorded ITEM 8 amount."""
    if len(clause_text) > 250 or not all(re.search(pattern, clause_text, re.IGNORECASE) for pattern in (
        r"\brent\b", r"\b(?:change|adjust|increase|vary)\b",
        r"\b(?:absolute|sole|unilateral|own)\b.{0,25}\bdiscretion\b",
    )):
        return None
    schedule = next((item for item in chunks if item.clause_id == "ITEM8" and "rent amount" in item.text.lower()), None)
    operative = next((item for item in chunks if item.clause_id in {"1.3", "1.4"}
                      and "ITEM 8" in item.text), None)
    if schedule is None or operative is None:
        return None
    return ReviewResult(
        label="review_required", clause_category="rent_utilities",
        reason="The clause permits unilateral changes to monthly rent, while the cited template records the rent amount in ITEM 8 and defines Rent by that amount.",
        follow_up_question="How would a rent change be agreed and recorded in the agreement?",
        source_id=schedule.source_id, source_section=schedule.section, abstained=False,
        evidence=(
            {"source_id": schedule.source_id, "source_section": schedule.section,
             "topic": "rent", "quote": schedule.text[:560]},
            {"source_id": operative.source_id, "source_section": operative.section,
             "topic": "rent", "quote": operative.text[:560]},
        ),
    )
