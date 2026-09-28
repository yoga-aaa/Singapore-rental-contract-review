"""Deterministic, non-AI baseline for tenancy-clause review."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


LABEL_REVIEW = "review_required"
LABEL_NO_DIFFERENCE = "no_material_difference_found"
LABEL_ABSTAIN = "insufficient_evidence"


@dataclass(frozen=True)
class BaselineResult:
    predicted_label: str
    clause_category: str
    source_id: str
    source_section: str
    reason: str
    abstained: bool


CATEGORY_PATTERNS = {
    "security_deposit": r"\b(deposit|deduct(?:ion|ed)?|refund)\b",
    "minor_repair": r"\b(repair|maintenance|plumbing|electrical|fixture|fitting)\b",
    "termination_notice": r"\b(terminat(?:e|ion)|notice|vacate|breach)\b",
    "occupancy_subletting": r"\b(occup(?:y|ant|ancy)|sublet|sub-?tenant|resident|guest)\b",
    "rent_utilities": r"\b(rent|utilities?|water|electricity|gas|late charge|maintenance fee)\b",
}

RISK_PATTERNS = (
    r"without (?:written )?notice",
    r"immediately",
    r"absolute discretion",
    r"any reason",
    r"any loss",
    r"any expense",
    r"any liability",
    r"regardless of (?:cause|cost|age)",
    r"all (?:repairs|plumbing|electrical)",
    r"sufficient notice",
    r"shall be final",
    r"decided later by the landlord",
    r"may change",
    r"verbally after",
    r"group chat",
)


def _category(text: str) -> str:
    lowered = text.lower()
    for category, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, lowered):
            return category
    return "unknown"


def _citation(housing_type: str, category: str) -> tuple[str, str]:
    source_id = "CEA_HDB_TA" if housing_type == "HDB" else "CEA_PRIVATE_TA"
    sections = {
        "security_deposit": "Operative Part 2.2 Security Deposit",
        "minor_repair": "Schedule Item 10 and Operative Part 4.2 Minor Repair",
        "termination_notice": "Operative Part 8 Termination and 11 Notices",
        "occupancy_subletting": "Operative Part 1.1 Premises and Term",
        "rent_utilities": "Operative Part 2.1 Rent and 2.3 Utilities",
    }
    return source_id, sections[category]


def review_clause(housing_type: str, clause_text: str) -> BaselineResult:
    """Return a conservative rule-based comparison result for one clause."""
    category = _category(clause_text)
    if housing_type not in {"HDB", "Private Residential"} or category == "unknown":
        return BaselineResult(
            LABEL_ABSTAIN,
            category,
            "",
            "",
            "The housing type or clause category cannot be compared to a registered source.",
            True,
        )

    source_id, section = _citation(housing_type, category)
    lowered = clause_text.lower()
    matched_pattern = next((pattern for pattern in RISK_PATTERNS if re.search(pattern, lowered)), None)
    if matched_pattern:
        return BaselineResult(
            LABEL_REVIEW,
            category,
            source_id,
            section,
            f"The rule baseline found a review signal matching /{matched_pattern}/.",
            False,
        )

    return BaselineResult(
        LABEL_NO_DIFFERENCE,
        category,
        source_id,
        section,
        "No predefined review signal was found; this is not legal approval.",
        False,
    )


def result_as_dict(result: BaselineResult) -> dict[str, object]:
    return asdict(result)
