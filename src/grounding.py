"""Validate exact contract spans and the structure of each reference comparison."""

from __future__ import annotations

import copy
from typing import Any


RELATIONS = {"equivalent", "tenant_beneficial", "tenant_adverse", "uncertain"}
TOPICS = {"security_deposit", "minor_repair", "termination_notice", "occupancy_subletting", "rent", "utilities"}
COMPARISON_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "topic": {"type": "string", "enum": sorted(TOPICS)},
        "contract_quote": {"type": "string", "minLength": 12, "maxLength": 500},
        "evidence_indices": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 2}, "minItems": 1, "maxItems": 3},
        "relation": {"type": "string", "enum": sorted(RELATIONS)},
        "reference_claim": {"type": "string", "minLength": 12, "maxLength": 250},
        "tenant_consequence": {"type": "string", "maxLength": 250},
    },
    "required": ["topic", "contract_quote", "evidence_indices", "relation", "reference_claim", "tenant_consequence"],
}


def grounded_schema(legacy: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(legacy)
    schema["name"] = "grounded_tenancy_clause_review_v13"
    schema["schema"]["properties"]["comparisons"] = {
        "type": "array", "items": COMPARISON_SCHEMA, "maxItems": 6,
    }
    schema["schema"]["required"].append("comparisons")
    return schema


def grounding_issue(comparisons: Any, clause_text: str | None, evidence: list[dict[str, str]],
                    label: str, needed_topics: set[str], check_decision: bool = True) -> str | None:
    if not isinstance(comparisons, list) or not 1 <= len(comparisons) <= 6 or clause_text is None:
        return "A non-abstaining result requires grounded clause-to-reference comparisons."
    covered: set[str] = set()
    relations: list[str] = []
    for item in comparisons:
        if not isinstance(item, dict) or set(item) != set(COMPARISON_SCHEMA["required"]):
            return "A structured comparison did not match its schema."
        quote, claim = item["contract_quote"], item["reference_claim"]
        if not isinstance(quote, str) or not 12 <= len(quote) <= 500 or quote not in clause_text:
            return "The asserted contract term was not an exact span of the supplied clause."
        if not isinstance(claim, str) or not 12 <= len(claim) <= 250:
            return "The comparison did not state a bounded reference claim."
        if not isinstance(item["topic"], str) or item["topic"] not in TOPICS:
            return "The structured comparison used an unknown topic."
        if not isinstance(item["relation"], str) or item["relation"] not in RELATIONS:
            return "The structured comparison used an unknown relation."
        indices = item["evidence_indices"]
        if not isinstance(indices, list) or not 1 <= len(indices) <= 3 or any(
            type(index) is not int or not 0 <= index < len(evidence) for index in indices
        ) or len(set(indices)) != len(indices):
            return "The structured comparison referenced invalid evidence indices."
        if any(evidence[index]["topic"] != item["topic"] for index in indices):
            return "The contract comparison and its selected evidence topics differed."
        consequence = item["tenant_consequence"]
        if not isinstance(consequence, str) or len(consequence) > 250:
            return "The structured comparison had an invalid tenant consequence."
        if check_decision and item["relation"] == "tenant_adverse" and len(consequence.strip()) < 12:
            return "The review finding did not identify a concrete tenant consequence."
        if item["relation"] == "tenant_adverse" and item["topic"] not in needed_topics:
            return "The adverse comparison was not tied to an identified contract obligation."
        covered.add(item["topic"])
        relations.append(item["relation"])
    if check_decision and label == "no_material_difference_found" and (
        not needed_topics.issubset(covered) or any(value not in {"equivalent", "tenant_beneficial"} for value in relations)
    ):
        return "A no-review result did not establish a supported comparison for every covered obligation."
    if check_decision and label == "review_required" and "tenant_adverse" not in relations:
        return "A review result had no explicit potentially adverse comparison."
    return None
