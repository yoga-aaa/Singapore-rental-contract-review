"""Strict comparisons where an explicit template condition decides the issue."""

from __future__ import annotations

import re

from src.rag_review import ReviewResult
from src.retrieval import RetrievedChunk


def _matches(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _entry(chunk: RetrievedChunk, topic: str) -> dict[str, str]:
    return {"source_id": chunk.source_id, "source_section": chunk.section,
            "topic": topic, "quote": chunk.text}


def direct_structural_repair_review(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 300 or not _matches(text, r"\bTenant\b", r"\b(?:all|every)\b.*\brepair\w*\b",
                                       r"\bstructural\b", r"\b(?:pipes|wiring)\b", r"\b(?:whatever|regardless)\b"):
        return None
    source = next((item for item in chunks if item.clause_id == "7.1" and "structural condition" in item.text
                   and "Landlord shall bear the full cost" in item.text), None)
    if source is None:
        return None
    return ReviewResult(
        label="review_required", clause_category="minor_repair",
        reason="The clause assigns structural pipes and concealed wiring repairs to the Tenant regardless of fault; cited Clause 7.1(f) makes the Landlord maintain those structural components and bear replacement cost absent Tenant fault.",
        follow_up_question="Will structural repairs and replacement costs follow Clause 7.1(f)?",
        source_id=source.source_id, source_section=source.section, abstained=False,
        evidence=(_entry(source, "minor_repair"),),
    )


def direct_unrestricted_termination_review(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 260 or not _matches(text, r"\b(?:end|terminat\w*)\b", r"\bany time\b",
                                       r"\bany reason\b", r"\b(?:text message|same day)\b"):
        return None
    source = next((item for item in chunks if item.clause_id in {"7.2", "8.2"}
                   and _matches(item.text, r"terminated by the Landlord in writing", r"seven \(7\) days",
                                r"fourteen \(14\) days")), None)
    if source is None:
        return None
    return ReviewResult(
        label="review_required", clause_category="termination_notice",
        reason="The clause permits same-day termination for any reason by text; the cited template instead specifies written Landlord termination on enumerated triggers, including seven-day unpaid rent or breach not rectified within fourteen days after written notice.",
        follow_up_question="Which stated termination trigger and written-notice process would apply?",
        source_id=source.source_id, source_section=source.section, abstained=False,
        evidence=(_entry(source, "termination_notice"),),
    )


def direct_deposit_process_match(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 400 or not _matches(text, r"\bdeposit\b", r"\bsigning\b", r"\bwritten notice\b",
                                       r"\b(?:fourteen|14)[ -]?days\b", r"\brefund\w*\b"):
        return None
    if re.search(r"one month's rent|S\$\s*\d+", text, re.IGNORECASE):
        return None  # A specified amount also needs the blank ITEM 9 evidence.
    source = next((item for item in chunks if item.clause_id == "2.2" and _matches(
        item.text, r"signing", r"written notice", r"fourteen \(14\) days", r"refunded")), None)
    if source is None:
        return None
    return ReviewResult(
        label="no_material_difference_found", clause_category="security_deposit",
        reason="The clause and cited Clause 2.2 both require deposit payment at signing, written notice and a fourteen-day opportunity to remedy before deduction, and refund of the balance at term end.",
        follow_up_question="", source_id=source.source_id, source_section=source.section,
        abstained=False, evidence=(_entry(source, "security_deposit"),),
    )


def direct_advance_rent_utilities_match(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 310 or not _matches(text, r"\brent\b", r"\badvance\b", r"\bTenant\b",
                                       r"\bwater\b", r"\belectricity\b", r"\bgas\b", r"\bsewerage\b"):
        return None
    rent = next((item for item in chunks if item.clause_id in {"1.3", "1.4"}
                 and "payable in advance" in item.text), None)
    utilities = next((item for item in chunks if item.clause_id == "2.3"
                      and "supply of water, electricity" in item.text), None)
    if rent is None or utilities is None:
        return None
    return ReviewResult(
        label="no_material_difference_found", clause_category="rent_utilities",
        reason="The clause's rent-in-advance and Tenant-paid water, electricity, gas and sewerage terms match the cited rental-amount and utilities clauses.",
        follow_up_question="", source_id=rent.source_id, source_section=rent.section,
        abstained=False, evidence=(_entry(rent, "rent"), _entry(utilities, "utilities")),
    )
