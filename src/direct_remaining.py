"""High-confidence reference comparisons for common tenancy terms."""

from __future__ import annotations

import re

from src.rag_review import ReviewResult
from src.retrieval import RetrievedChunk


def _find(chunks: list[RetrievedChunk], clause_id: str) -> RetrievedChunk | None:
    return next((item for item in chunks if item.clause_id == clause_id), None)


def _evidence(chunk: RetrievedChunk, topic: str) -> dict[str, str]:
    return {"source_id": chunk.source_id, "source_section": chunk.section,
            "topic": topic, "quote": chunk.text}


def _has(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def direct_complete_deposit_match(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    """Treat the chosen deposit amount as a filled template field, not a mandate."""
    if len(text) > 550 or not _has(text, r"\bdeposit\b", r"one month's rent|S\$\s*\d+",
                                    r"\bsigning\b", r"\bwritten notice\b", r"\b(?:fourteen|14)[ -]?day",
                                    r"\brefund\w*\b", r"\bnot be used as rent\b"):
        return None
    schedule = _find(chunks, "ITEM9")
    operative = _find(chunks, "2.2")
    if schedule is None or operative is None or "equivalent to _______ month" not in schedule.text:
        return None
    if not _has(operative.text, r"written notice", r"fourteen \(14\) days", r"refunded", r"not be utilised"):
        return None
    return ReviewResult(
        label="no_material_difference_found", clause_category="security_deposit",
        reason="The chosen deposit amount fills blank Schedule ITEM 9; the clause and cited Clause 2.2 match on payment at signing, written notice and cure before deductions, refund, and no rent set-off.",
        follow_up_question="", source_id=schedule.source_id, source_section=schedule.section,
        abstained=False, evidence=(_evidence(schedule, "security_deposit"), _evidence(operative, "security_deposit")),
    )


def direct_deferred_deposit_review(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 280 or not _has(text, r"\bdeposit\b", r"\bverbal\w*\b", r"\bafter\b.*\bmov\w*\s+in\b"):
        return None
    operative = _find(chunks, "2.2")
    if operative is None or not _has(operative.text, r"signing", r"written notice"):
        return None
    return ReviewResult(
        label="review_required", clause_category="security_deposit",
        reason="The clause postpones deposit terms until a verbal discussion after move-in; cited Clause 2.2 places deposit payment at signing and states a written-notice process before deductions.",
        follow_up_question="What deposit amount and deduction process will be written into the signed agreement?",
        source_id=operative.source_id, source_section=operative.section, abstained=False,
        evidence=(_evidence(operative, "security_deposit"),),
    )


def direct_unlimited_repair_review(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 290 or not _has(text, r"\bTenant\b", r"\b(?:all|every)\b.*\brepairs?\b",
                                    r"\b(?:regardless|whatever)\b", r"\bcost\b"):
        return None
    if not re.search(r"\bTenant\b\s+(?:(?:shall|must|will)\s+)?(?:pays?|bears?)\b[^.;]*\brepairs?\b", text, re.I):
        return None
    if re.search(r"structural|concealed", text, re.IGNORECASE):
        return None
    schedule = _find(chunks, "ITEM10")
    operative = _find(chunks, "4.2")
    if schedule is None or operative is None or "S$____" not in schedule.text:
        return None
    return ReviewResult(
        label="review_required", clause_category="minor_repair",
        reason="The clause puts all repair costs on the Tenant regardless of cost or cause; Schedule ITEM 10 and Clause 4.2 instead use a per-item cap and put excess cost on the Landlord unless the Tenant caused the damage.",
        follow_up_question="Will the agreement use an ITEM 10 cap and preserve the excess-cost allocation?",
        source_id=schedule.source_id, source_section=schedule.section, abstained=False,
        evidence=(_evidence(schedule, "minor_repair"), _evidence(operative, "minor_repair")),
    )


def direct_variable_notice_review(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 250 or not _has(text, r"\b(?:end|terminat\w*)\b", r"\bnotice\b",
                                    r"\b(?:length|period)\b.*\bdecided later\b.*\bLandlord\b"):
        return None
    operative = _find(chunks, "7.2")
    if operative is None or not _has(operative.text, r"terminate", r"seven \(7\) days", r"fourteen \(14\) days"):
        return None
    return ReviewResult(
        label="review_required", clause_category="termination_notice",
        reason="The contract leaves the notice length to a later Landlord decision; cited Clause 7.2 instead ties Landlord termination to specified events, including seven-day rent default or written breach notice with fourteen days to rectify.",
        follow_up_question="Which termination ground and notice process is intended?",
        source_id=operative.source_id, source_section=operative.section, abstained=False,
        evidence=(_evidence(operative, "termination_notice"),),
    )


def direct_occupant_documents_match(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 260 or not _has(text, r"\bforeign\b", r"\boccup\w*\b", r"\bdocuments?\b",
                                    r"\blawful\b", r"\bwhen required by the Landlord\b"):
        return None
    if not re.search(r"\bTenant\b\s+(?:shall|must|will)\s+(?:provide|produce)\b", text, re.I):
        return None  # The template places production on the tenant, not the occupiers.
    operative = _find(chunks, "3.3")
    if operative is None or not _has(operative.text, r"Where required by the Landlord", r"documents of all occupiers"):
        return None
    return ReviewResult(
        label="no_material_difference_found", clause_category="occupancy_subletting",
        reason="The clause's lawful-residence document requirement matches the cited template's production of occupier identity and lawful-stay documents when required by the Landlord.",
        follow_up_question="", source_id=operative.source_id, source_section=operative.section,
        abstained=False, evidence=(_evidence(operative, "occupancy_subletting"),),
    )


def direct_discretionary_utilities_review(text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    if len(text) > 300 or not _has(text, r"\bLandlord\b", r"\b(?:decide|determine|set)\b",
                                    r"\butilit\w*\b", r"\bexcess\b"):
        return None
    operative = _find(chunks, "2.3")
    if operative is None or not _has(operative.text, r"Tenant agrees to pay all charges", r"supply of water"):
        return None
    return ReviewResult(
        label="review_required", clause_category="rent_utilities",
        reason="The clause lets the Landlord set a discretionary utility threshold and extra charge; cited Clause 2.3 allocates the charges for utility supply to the Tenant. The basis of the extra charge needs clarification.",
        follow_up_question="How is any excess utility charge linked to the actual supply charges?",
        source_id=operative.source_id, source_section=operative.section,
        abstained=False, evidence=(_evidence(operative, "utilities"),),
    )
