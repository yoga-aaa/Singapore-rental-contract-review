"""Guarded single-clause comparison with local and model-backed review paths."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.evidence_spans import spans_for_chunks
from src.evidence_verifier import merged_usage, verify_candidate
from src.comparison_checks import comparison_issue, direct_no_review_allowed, omission_issue
from src.grounding import grounding_issue
from src.direct_matches import direct_minor_repair_match, direct_named_occupancy_match
from src.direct_differences import direct_late_rent_review, direct_discretionary_rent_review
from src.direct_remaining import (
    direct_complete_deposit_match, direct_deferred_deposit_review, direct_unlimited_repair_review,
    direct_variable_notice_review, direct_occupant_documents_match, direct_discretionary_utilities_review,
)
from src.direct_common import (
    direct_structural_repair_review, direct_unrestricted_termination_review,
    direct_deposit_process_match, direct_advance_rent_utilities_match, direct_notice_delivery_match,
)
from src.rag_review import LABELS, OUTPUT_SCHEMA, ReviewResult, _request_openrouter, abstain, build_request
from src.retrieval import LocalBM25Retriever, RetrievedChunk, query_topics


REPO_ROOT = Path(__file__).resolve().parents[1]


COMPARISON_TOPICS = re.compile(
    r"\b(deposit\w*|deduct\w*|rent\w*|repair\w*|maintenan\w*|terminat\w*|end|expir\w*|renew\w*|notice\w*|occup\w*|resid\w*|sublet\w*|utilit\w*|electric\w*|water|gas|sewer\w*|fee\w*|charg\w*|premises|flat|property)\b",
    flags=re.IGNORECASE,
)


def precheck_abstention_reason(clause_text: str) -> str | None:
    """Avoid model calls for clauses without a concrete comparison point."""
    if not COMPARISON_TOPICS.search(clause_text):
        return "The clause does not state a tenancy term covered by the registered reference excerpts."
    if query_topics(clause_text) == {"occupancy_subletting"} and re.search(r"\bused?\b", clause_text, re.IGNORECASE):
        if not re.search(r"\b(occup\w*|resid\w*|liv\w*|stay\w*|sublet\w*|assign\w*)\b", clause_text, re.IGNORECASE):
            return "Use of a property alone does not establish who resides or occupies it."
    if query_topics(clause_text) == {"occupancy_subletting"} and re.search(
        r"\b(?:reasonable|suitable|appropriate) number of (?:people|persons|occupants)\b",
        clause_text, re.IGNORECASE,
    ):
        return "A qualitative occupancy limit cannot be compared with the reference's configurable headcount."
    if re.search(r"\bsublet\w*\b", clause_text, re.IGNORECASE) and "HDB" in clause_text.upper() and re.search(r"\b(?:except|unless|permitted)\b", clause_text, re.IGNORECASE):
        return "The registered template does not establish whether HDB approval overrides its subletting restriction."

    if re.search(r"\b(repair\w*|maintenance)\b", clause_text, flags=re.IGNORECASE):
        assigns_responsibility = re.search(
            r"\b(tenant|landlord|equally|jointly|split|share\w*|\d+\s*%|S\$\s*\d+)\b",
            clause_text,
            flags=re.IGNORECASE,
        )
        if not assigns_responsibility:
            return "The clause does not identify who is responsible for repairs or how costs are allocated."
    return None


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


def normalized_quote(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def unsupported_fixed_amount_claim(reason: str, evidence: list[dict[str, str]]) -> bool:
    """Reject fixed amounts attributed to the reference but absent from its quotes."""
    quoted = normalized_quote(" ".join(item["quote"] for item in evidence))
    amount_pattern = re.compile(
        r"S\$\s*\d+(?:\.\d+)?|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+months?'?s?\s+rent\b",
        flags=re.IGNORECASE,
    )
    for sentence in re.split(r"(?<=[.!?])\s+", reason):
        attribution = re.search(
            r"\b(?:both|reference|template|CEA)\b.{0,100}\b(?:stipulat\w*|requir\w*|specif\w*|stat\w*|set\w*|provid\w*)\b",
            sentence,
            flags=re.IGNORECASE,
        )
        if attribution:
            for amount in amount_pattern.findall(sentence[attribution.start():]):
                if normalized_quote(amount) not in quoted:
                    return True
    return False


def unsupported_omission_review(reason: str, clause_text: str) -> bool:
    return omission_issue(reason, clause_text)


def without_unsupported_legal_verdicts(reason: str) -> str:
    """Drop stand-alone legal verdicts that CEA template quotations cannot establish."""
    sentences = re.split(r"(?<=[.!?])\s+", reason.strip())
    unsupported = re.compile(
        r"\b(?:legal(?!\s+(?:costs?|fees?|expenses?))|illegal|unlawful|enforceab\w*|validity|void|unfair|safe to sign)\b",
        re.IGNORECASE,
    )
    return " ".join(sentence for sentence in sentences if not unsupported.search(sentence)).strip()


def validate_output(
    raw: dict[str, Any],
    chunks: list[RetrievedChunk],
    usage: dict[str, int] | None = None,
    clause_text: str | None = None,
    require_grounding: bool = False,
    structural_only: bool = False,
) -> ReviewResult:
    required_fields = set(OUTPUT_SCHEMA["schema"]["required"])
    if require_grounding or (isinstance(raw, dict) and "comparisons" in raw):
        required_fields.add("comparisons")
    if not isinstance(raw, dict) or set(raw) != required_fields:
        return abstain("The model output did not match the required review schema.", usage, api_called=True)

    label = raw.get("label")
    if not isinstance(label, str) or label not in LABELS or not isinstance(raw.get("abstained"), bool):
        return abstain("The model output contained an invalid label or abstention state.", usage, api_called=True)
    if label == "insufficient_evidence":
        return abstain(str(raw.get("reason") or "The available references were insufficient for a supported comparison."), usage, api_called=True)

    if not isinstance(raw.get("reason"), str):
        return abstain("The model did not explain the clause-to-reference comparison.", usage, api_called=True)
    reason = without_unsupported_legal_verdicts(raw["reason"])
    if require_grounding and (not isinstance(raw.get("clause_category"), str)
                             or raw["clause_category"] not in OUTPUT_SCHEMA["schema"]["properties"]["clause_category"]["enum"]
                             or not isinstance(raw.get("follow_up_question"), str)):
        return abstain("The model returned invalid review fields.", usage, api_called=True)
    if require_grounding and (len(reason) > 500 or len(raw["follow_up_question"]) > 300):
        return abstain("The model returned an unbounded explanation or question.", usage, api_called=True)
    if len(reason) < 25:
        return abstain("The model did not explain the clause-to-reference comparison.", usage, api_called=True)
    if label == "review_required":
        question = raw.get("follow_up_question")
        if not isinstance(question, str) or len(question.strip()) < 20 or "?" not in question:
            return abstain("The review flag did not include an actionable tenant question.", usage, api_called=True)
        if not structural_only and clause_text is not None and unsupported_omission_review(reason, clause_text):
            return abstain("An omitted phrase in one clause does not establish a contract-wide adverse term.", usage, api_called=True)
    evidence = raw.get("evidence")
    if raw.get("abstained") or not isinstance(evidence, list) or not 1 <= len(evidence) <= 3:
        return abstain("A non-abstaining result requires one to three reference excerpts.", usage, api_called=True)
    verified: list[dict[str, str]] = []
    indexed_spans = {span.evidence_id: span for span in spans_for_chunks(chunks)}
    for item in evidence:
        if not isinstance(item, dict):
            return abstain("An evidence entry did not match the citation schema.", usage, api_called=True)
        if set(item) == {"evidence_id", "topic"}:
            if not isinstance(item["evidence_id"], str) or not isinstance(item["topic"], str):
                return abstain("The selected evidence ID or topic was invalid.", usage, api_called=True)
            span = indexed_spans.get(item["evidence_id"])
            if span is None or item["topic"] not in span.chunk.topics or len(normalized_quote(span.quote)) < 25:
                return abstain("The selected evidence ID or topic was invalid.", usage, api_called=True)
            verified.append({
                "source_id": span.chunk.source_id,
                "source_section": span.chunk.section,
                "topic": item["topic"],
                "quote": span.quote,
                "context_quote": span.chunk.text[:2200],
            })
            continue
        evidence_fields = {"source_id", "source_section", "topic", "quote"}
        if set(item) not in (evidence_fields, evidence_fields | {"context_quote"}):
            return abstain("An evidence entry did not match the citation schema.", usage, api_called=True)
        source_id = item["source_id"]
        source_section = item["source_section"]
        topic = item["topic"]
        quote = item["quote"]
        if not all(isinstance(value, str) for value in (source_id, source_section, topic, quote)):
            return abstain("An evidence entry contained a non-text value.", usage, api_called=True)
        if len(normalized_quote(quote)) < 25:
            return abstain("The cited quote was too short to substantiate a reference rule.", usage, api_called=True)
        matching = [
            chunk for chunk in chunks
            if chunk.source_id == source_id
            and (
                chunk.section == source_section
                or (
                    (page := re.fullmatch(r"Page\s+(\d+)", source_section, flags=re.IGNORECASE))
                    and int(page.group(1)) in {chunk.page_number, chunk.page_number - 1}
                )
            )
        ]
        if not matching or not any(
            topic in chunk.topics and normalized_quote(quote) in normalized_quote(chunk.text[:2200])
            for chunk in matching
        ):
            return abstain("The citation quote or topic was not supported by the retrieved reference excerpt.", usage, api_called=True)
        context = item.get("context_quote")
        if context is not None and (not isinstance(context, str) or not any(
            context == chunk.text[:2200] and quote in context for chunk in matching
        )):
            return abstain("The citation context was not the registered model-visible section.", usage, api_called=True)
        if require_grounding and not any(chunk.section == source_section and quote in chunk.text[:2200] for chunk in matching):
            return abstain("A grounded comparison requires an exact reference quote and locator.", usage, api_called=True)
        entry = {"source_id": source_id, "source_section": source_section, "topic": topic, "quote": quote.strip()}
        if context is not None:
            entry["context_quote"] = context
        verified.append(entry)

    if not structural_only and unsupported_fixed_amount_claim(reason, verified):
        return abstain("The explanation attributed an unsupported fixed amount to the reference.", usage, api_called=True)
    if not structural_only and label == "review_required" and re.search(
        r"\b(?:align\w*|match\w*|equivalent|same)\b", reason, re.IGNORECASE
    ):
        if not re.search(r"\b(contrast\w*|differ\w*|conflict\w*|contradict\w*|whereas|instead)\b", reason, re.IGNORECASE):
            return abstain("The explanation did not identify a concrete difference after describing alignment.", usage, api_called=True)
    if not structural_only and label == "no_material_difference_found" and re.search(
        r"\b(?:does not (?:explicitly )?(?:mention|forbid|prohibit|address)|not mentioned|silent about)\b",
        reason, re.IGNORECASE,
    ):
        return abstain("Equivalence cannot be inferred solely from a reference's silence.", usage, api_called=True)
    primary = verified[0]
    if (raw.get("source_id"), raw.get("source_section")) != (primary["source_id"], primary["source_section"]):
        return abstain("The primary citation did not match its evidence entry.", usage, api_called=True)
    if clause_text is not None:
        needed_topics = query_topics(clause_text)
        cited_topics = {item["topic"] for item in verified}
        if not structural_only and label == "no_material_difference_found" and not needed_topics.issubset(cited_topics):
            return abstain("The reference evidence did not cover every material topic in the clause.", usage, api_called=True)
        if label == "review_required" and needed_topics and not needed_topics.intersection(cited_topics):
            return abstain("The material difference was not tied to a relevant reference topic.", usage, api_called=True)
    comparisons = raw.get("comparisons")
    if require_grounding or comparisons is not None:
        issue = grounding_issue(comparisons, clause_text, verified, label, query_topics(clause_text or ""), check_decision=not structural_only)
        if issue:
            return abstain(issue, usage, api_called=True)
    if not structural_only and clause_text is not None:
        for item in comparisons or []:
            if normalized_quote(without_unsupported_legal_verdicts(item["reference_claim"])) != normalized_quote(item["reference_claim"]):
                return abstain("A structured reference claim included an unsupported legal verdict.", usage, api_called=True)
        issue = comparison_issue(label, reason + " " + str(raw["follow_up_question"]), clause_text, verified, comparisons)
        if issue:
            return abstain(issue, usage, api_called=True)

    return ReviewResult(
        label=label,
        clause_category=str(raw["clause_category"]),
        reason=reason,
        follow_up_question=str(raw["follow_up_question"]),
        source_id=primary["source_id"],
        source_section=primary["source_section"],
        abstained=False,
        usage=usage,
        evidence=tuple(verified),
        api_called=True,
        comparisons=tuple(comparisons or []),
    )


def direct_breach_termination_match(clause_text: str, chunks: list[RetrievedChunk]) -> ReviewResult | None:
    """Use a narrow deterministic match for an otherwise identical breach/cure process."""
    if len(clause_text) > 240 or not re.search(r"\b(?:terminat\w*|end\s+(?:the\s+)?tenancy)\b", clause_text, re.IGNORECASE):
        return None
    required = (
        r"\bwritten notice\b",
        r"\b(?:fail\w*\s+to\s+rectify|failure\s+to\s+rectify)\b",
        r"\b(?:fourteen|14)[ -]?days\b",
    )
    if any(not re.search(pattern, clause_text, re.IGNORECASE) for pattern in required):
        return None
    if re.search(r"\b(?:any time|any reason|text message|emoji|immediately)\b", clause_text, re.IGNORECASE):
        return None
    quote_pattern = re.compile(
        r"if, upon the Landlord giving written notice to the Tenant.*?"
        r"fails to rectify such breach within fourteen \(14\) days from the service of such written notice",
        re.IGNORECASE,
    )
    for chunk in chunks:
        if chunk.clause_id not in {"7.2", "8.2"} or "termination_notice" not in chunk.topics:
            continue
        match = quote_pattern.search(chunk.text)
        if match:
            quote = match.group(0)
            return ReviewResult(
                label="no_material_difference_found",
                clause_category="termination_notice",
                reason="The clause and cited template both make breach termination conditional on written notice and an unremedied breach after fourteen days.",
                follow_up_question="",
                source_id=chunk.source_id,
                source_section=chunk.section,
                abstained=False,
                evidence=({"source_id": chunk.source_id, "source_section": chunk.section,
                           "topic": "termination_notice", "quote": quote},),
            )
    return None


def apply_verification(
    raw: dict[str, Any],
    verification: dict[str, Any],
    chunks: list[RetrievedChunk],
    usage: dict[str, int],
    clause_text: str,
    require_grounding: bool = False,
) -> ReviewResult:
    """Only release a result approved or corrected using its exact cited evidence."""
    expected = {"decision", "label", "reason", "issue"}
    structured = require_grounding or "comparisons" in raw
    if structured:
        expected.update({"comparison_verdicts", "follow_up_question"})
    if not isinstance(verification, dict) or set(verification) != expected:
        return abstain("The independent evidence check returned an invalid response.", usage, api_called=True)
    if any(not isinstance(verification[field], str) for field in ("decision", "label", "reason", "issue")):
        return abstain("The independent evidence check returned invalid field types.", usage, api_called=True)
    if structured and not isinstance(verification["follow_up_question"], str):
        return abstain("The independent evidence check returned an invalid question.", usage, api_called=True)
    if structured:
        comparisons = raw.get("comparisons")
        verdicts = verification.get("comparison_verdicts")
        if not isinstance(comparisons, list) or not isinstance(verdicts, list) or len(verdicts) != len(comparisons):
            return abstain("The independent evidence check did not assess every comparison.", usage, api_called=True)
        reviewed: list[dict] = []
        for index, (comparison, verdict) in enumerate(zip(comparisons, verdicts)):
            if not isinstance(verdict, dict) or set(verdict) != {"comparison_index", "verdict", "relation", "note", "tenant_consequence", "reference_claim"}:
                return abstain("The independent comparison assessment was malformed.", usage, api_called=True)
            if type(verdict["comparison_index"]) is not int or verdict["comparison_index"] != index:
                return abstain("The independent comparison indices did not match.", usage, api_called=True)
            if verdict["verdict"] != "supported" or not isinstance(verdict["note"], str) or len(verdict["note"].strip()) < 12:
                return abstain("The independent evidence check could not substantiate every comparison.", usage, api_called=True)
            if verification["decision"] == "approve" and verdict["relation"] != comparison["relation"]:
                return abstain("Approval changed a comparison without a revision.", usage, api_called=True)
            if verification["decision"] == "approve" and verdict["tenant_consequence"] != comparison["tenant_consequence"]:
                return abstain("Approval changed a tenant consequence without a revision.", usage, api_called=True)
            if verification["decision"] == "approve" and verdict["reference_claim"] != comparison["reference_claim"]:
                return abstain("Approval changed a reference claim without a revision.", usage, api_called=True)
            reviewed.append({**comparison, "relation": verdict["relation"],
                             "tenant_consequence": verdict["tenant_consequence"], "reference_claim": verdict["reference_claim"]})
        raw = {**raw, "comparisons": reviewed}
    decision = verification["decision"]
    if decision == "approve" and verification["label"] == raw["label"]:
        # Approval can paraphrase the explanation. Do not assume equivalent
        # wording: validate the returned prose again against the same immutable
        # contract spans, evidence, relations and per-comparison assessments.
        approved = {**raw, "reason": verification["reason"]}
        if structured:
            approved["follow_up_question"] = verification["follow_up_question"]
        return validate_output(approved, chunks, usage, clause_text, require_grounding=require_grounding)
    if decision == "revise" and verification["label"] in LABELS and isinstance(verification["reason"], str):
        if verification["label"] == "insufficient_evidence":
            return abstain("The independent evidence check found the draft citation insufficient.", usage, api_called=True)
        revised = {**raw, "label": verification["label"], "reason": verification["reason"],
                   "follow_up_question": "" if verification["label"] == "no_material_difference_found"
                   else verification.get("follow_up_question", raw["follow_up_question"])}
        return validate_output(revised, chunks, usage, clause_text, require_grounding=require_grounding)
    return abstain("The independent evidence check could not substantiate the draft comparison.", usage, api_called=True)


class ModelReviewRequired(RuntimeError):
    """An offline check reached the model stage; this is not an abstention prediction."""


def review_clause(housing_type: str, clause_text: str, retriever: LocalBM25Retriever, limit: int = 4,
                  api_key: str | None = None, allow_api: bool = True) -> ReviewResult:
    if housing_type not in {"HDB", "Private Residential"}:
        return abstain("Select HDB or Private Residential before requesting a review.")
    if not clause_text.strip():
        return abstain("Provide a contract clause before requesting a review.")
    precheck_reason = precheck_abstention_reason(clause_text)
    if precheck_reason:
        return abstain(precheck_reason)

    chunks = [chunk for chunk in retriever.search(clause_text, housing_type, limit=limit)
              if chunk.housing_type == housing_type and chunk.source_kind == "tenancy_agreement_template"]
    if not chunks:
        return abstain("No relevant registered reference evidence was retrieved.")
    for matcher in (
        direct_minor_repair_match, direct_named_occupancy_match, direct_breach_termination_match,
        direct_late_rent_review, direct_discretionary_rent_review,
        direct_complete_deposit_match, direct_deferred_deposit_review, direct_unlimited_repair_review,
        direct_variable_notice_review, direct_occupant_documents_match, direct_discretionary_utilities_review,
        direct_structural_repair_review, direct_unrestricted_termination_review,
        direct_deposit_process_match, direct_advance_rent_utilities_match, direct_notice_delivery_match,
    ):
        direct_match = matcher(clause_text, chunks)
        if direct_match is not None:
            if direct_match.label == "no_material_difference_found" and not direct_no_review_allowed(clause_text):
                continue
            raw_direct = {key: getattr(direct_match, key) for key in OUTPUT_SCHEMA["schema"]["required"]}
            raw_direct["evidence"] = list(direct_match.evidence)
            validated = validate_output(raw_direct, chunks, clause_text=clause_text)
            if not validated.abstained:
                return replace(validated, api_called=False)

    if not allow_api:
        raise ModelReviewRequired("Local rules did not settle this clause; model evaluation was not run.")
    api_key = api_key or local_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required in the environment or local .env file.")
    raw, usage = _request_openrouter(build_request(housing_type, clause_text, chunks), api_key)
    draft = validate_output(raw, chunks, usage, clause_text, require_grounding=True, structural_only=True)
    if draft.abstained:
        return draft
    resolved_raw = {**raw, "reason": draft.reason, "evidence": list(draft.evidence)}
    checked, verification_usage = verify_candidate(housing_type, clause_text, resolved_raw, api_key)
    return apply_verification(resolved_raw, checked, chunks, merged_usage(usage, verification_usage), clause_text, require_grounding=True)
