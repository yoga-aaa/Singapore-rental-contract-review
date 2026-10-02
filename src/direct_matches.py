"""Narrow, auditable comparisons for filled fields in CEA templates."""

from __future__ import annotations

import re

from src.evidence_spans import spans_for_chunks
from src.rag_review import ReviewResult
from src.retrieval import RetrievedChunk


def direct_minor_repair_match(clause_text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    """Recognize a filled ITEM 10 cap with the same excess-cost allocation."""
    if len(clause_text) > 260:
        return None
    patterns = (
        r"\bminor repairs?\b", r"S\$\s*\d+", r"per item per incident",
        r"\b(?:above|exceed\w*)\b", r"\bLandlord\b", r"\bnegligence\b",
    )
    if any(not re.search(pattern, clause_text, re.IGNORECASE) for pattern in patterns):
        return None
    if not re.search(
        r"\bLandlord\b[^.;]{0,50}\b(?:pays?|bears?|responsible)\b[^.;]{0,50}\b(?:above|excess|exceed\w*)\b|"
        r"\bcosts?\b[^.;]{0,35}\b(?:above|excess|exceed\w*)\b[^.;]{0,35}\b(?:borne|paid|covered) by (?:the )?Landlord\b",
        clause_text, re.I,
    ):
        return None
    schedule = next((item for item in chunks if item.clause_id == "ITEM10" and "S$____" in item.text), None)
    operative = next((item for item in chunks if item.clause_id == "4.2" and "ITEM 10" in item.text), None)
    if schedule is None or operative is None:
        return None
    operative_quote = next(
        (span.quote for span in spans_for_chunks([operative])
         if "cost per item per incident" in span.quote and "borne by the Landlord" in span.quote),
        None,
    )
    if operative_quote is None:
        return None
    evidence = (
        {"source_id": schedule.source_id, "source_section": schedule.section,
         "topic": "minor_repair", "quote": schedule.text},
        {"source_id": operative.source_id, "source_section": operative.section,
         "topic": "minor_repair", "quote": operative_quote},
    )
    return ReviewResult(
        label="no_material_difference_found", clause_category="minor_repair",
        reason="The clause fills the template's variable ITEM 10 repair cap; both assign excess cost to the Landlord unless the Tenant caused the damage.",
        follow_up_question="", source_id=schedule.source_id, source_section=schedule.section,
        abstained=False, evidence=evidence,
    )


def direct_named_occupancy_match(clause_text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    """Read ITEM 6's actual named-occupier field before comparing residence use."""
    if len(clause_text) > 240 or re.search(r"\b(sublet\w*|assign\w*|guest\w*)\b", clause_text, re.IGNORECASE):
        return None
    if not re.search(r"\b(?:named|listed)\b", clause_text, re.IGNORECASE) or not re.search(
        r"\boccup\w*\b", clause_text, re.IGNORECASE
    ):
        return None
    if not re.search(r"\b(?:only|limited to)\b", clause_text, re.I):
        return None
    schedule = next((item for item in chunks if item.clause_id == "ITEM6" and "NAME(S) OF OCCUPIER(S)" in item.text), None)
    operative = next((item for item in chunks if item.clause_id == "1.1" and "ITEM" in item.text), None)
    if schedule is None or operative is None:
        return None
    matched = [schedule, operative]
    if schedule.housing_type == "HDB" and "HDB" in clause_text.upper():
        approval = next((item for item in chunks if item.clause_id == "1.2" and "HDB" in item.text), None)
        if approval is None:
            return None
        matched.append(approval)
    evidence = tuple({
        "source_id": item.source_id, "source_section": item.section,
        "topic": "occupancy_subletting", "quote": item.text[:560],
    } for item in matched)
    reason = "The template's ITEM 6 names allowed occupiers, and Clause 1.1 ties residence occupancy to ITEMS 5 and 6."
    if len(matched) == 3:
        reason += " Clause 1.2 also requires HDB rental-condition compliance."
    return ReviewResult(
        label="no_material_difference_found", clause_category="occupancy_subletting",
        reason=reason, follow_up_question="", source_id=schedule.source_id,
        source_section=schedule.section, abstained=False, evidence=evidence,
    )
