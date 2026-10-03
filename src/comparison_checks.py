"""Local contradiction checks, with claim-specific rather than global waivers.

These checks reject known invalid inferences. Passing them is not a proof of
semantic entailment; the quote-bounded verifier must still judge the facts.
"""

from __future__ import annotations

import re


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?;])\s+", text.casefold())


def explicit_waiver(protection: str, clause_text: str) -> bool:
    """Recognize scoped negative terms, not absence of a safeguard in an excerpt."""
    aliases = {"notice": r"(?:notice|notify|notifying|notification)",
               "cure": r"(?:cure|remedy|opportunity)",
               "remedy": r"(?:cure|remedy|opportunity)",
               "cap": r"(?:cap|limit)", "limit": r"(?:cap|limit)"}.get(protection, protection)
    qualifiers = r"(?:first|giving|give|providing|provide|obtaining|obtain|any|prior|written|the|a|an|tenant|landlord|to)"
    for part in sentences(clause_text):
        if re.search(
            rf"\b(?:without\s+(?:{qualifiers}\s+){{0,8}}{aliases}\b|"
            rf"no\s+(?:(?:prior|written|opportunity to)\s+){{0,2}}{aliases}\b|"
            rf"(?:need not|not required to)\s+(?:{qualifiers}\s+){{0,8}}{aliases}\b|"
            rf"{aliases}\s+(?:is|shall be)\s+not required\b)", part
        ):
            return True
        # A negative process declaration can cover a list (notice or remedy).
        # Stop at a comma/contrast, so an affirmative following requirement is
        # not mistakenly treated as part of the negative declaration.
        for process in re.finditer(
            r"\bno\s+(?:process|procedure|requirement|provision)\s+for\s+([^.;,]+)", part
        ):
            scope = re.split(r"\b(?:but|however|whereas|although)\b", process.group(1))[0]
            if re.search(rf"\b{aliases}\b", scope):
                return True
    return False


def omission_issue(reason: str, clause_text: str) -> bool:
    omission = re.compile(
        r"\b(?:omits?|omitted|missing|lacks?|unspecified|not specified|not stated|"
        r"does not (?:state|mention|specify|require|provide)|"
        r"fails? to (?:state|mention|specify|require)|"
        r"without (?:requiring|specifying|mentioning|providing)|"
        r"no (?:express |explicit )?(?:requirement|provision|mention))\b"
    )
    for statement in sentences(reason):
        if not omission.search(statement):
            continue
        protections = [word for word in ("notice", "consent", "approval", "refund", "cap", "limit", "remedy", "cure")
                       if re.search(rf"\b{word}\w*\b", statement)]
        if not protections:
            return True
        for protection in protections:
            if not explicit_waiver(protection, clause_text):
                return True
    return False


def source_scope_issue(reason: str, evidence: list[dict[str, str]]) -> str | None:
    for statement in sentences(reason):
        if not re.search(r"\b(?:reference|template|cea)\b", statement):
            continue
        if re.search(r"\b(?:not in (?:the )?(?:reference|template)|nowhere|silent|"
                     r"no such|does not (?:mention|address|provide for|specify)|"
                     r"not (?:mentioned|addressed|provided))\b", statement):
            return "The explanation treats the silence of cited excerpts as a contract-wide reference rule."
        if re.search(r"\b(?:only (?:allows?|permits?)|(?:allows?|permits?) only|only (?:upon|on|at)|only allowed|not during (?:the )?fixed term)\b", statement):
            quoted = " ".join(item["quote"] for item in evidence).casefold()
            if not re.search(r"\bonly\b", quoted):
                return "The explanation makes an exhaustive reference claim not stated in the cited text."
    return None


def conditional_subletting(text: str) -> bool:
    return bool(re.search(r"\b(?:sublet\w*|assign\w*)\b[^.;]*\b(?:without|with|subject to|only with)\b[^.;]*\bconsent\b", text, re.I))


def comparison_issue(label: str, reason: str, clause_text: str,
                     evidence: list[dict[str, str]], comparisons: list[dict] | None = None) -> str | None:
    if label == "review_required" and omission_issue(reason, clause_text):
        return "An omitted phrase in one clause does not establish a contract-wide adverse term."
    scope = source_scope_issue(reason, evidence)
    if scope:
        return scope
    for protection in ("notice", "consent", "approval", "remedy", "cure"):
        if re.search(rf"\b(?:without\s+(?:prior\s+|written\s+)?{protection}|no\s+(?:written\s+)?{protection})\b", reason, re.I):
            if omission_issue(f"The contract omits {protection}.", clause_text):
                return "The explanation asserts a safeguard waiver that the selected contract clause does not state."
    quoted = " ".join(item["quote"] for item in evidence).casefold()
    comparison_prose = ' '.join(item['reference_claim'] + ' ' + item['tenant_consequence'] for item in comparisons or [])
    if re.search(r'\breplenish\w*\b', clause_text, re.I) and re.search(
        r'\b(?:only|has|have)\b.{0,30}\b(?:7|seven)\b.{0,40}\b(?:remedy|before deduction)\b',
        reason + ' ' + comparison_prose, re.I
    ):
        return 'A post-deduction replenishment deadline was confused with a pre-deduction remedy period.'
    if label == "no_material_difference_found":
        if re.search(r'\b(?:report|surveyor|plumber)\b', clause_text, re.I) and re.search(
            r'\b(?:prima facie|final and binding|cost of such report|fees shall)\b', clause_text, re.I
        ) and not re.search(r'\b(?:prima facie|final and binding|surveyor|cost of (?:such )?report)\b', quoted):
            return 'The cited repair responsibility does not cover the separate dispute-evidence or report-fee mechanism.'
        if conditional_subletting(clause_text) and "sublet" in quoted:
            if re.search(r"\b(?:match\w*|same|equivalent|align\w*)\b", reason, re.I):
                return "Conditional permission to sublet was incorrectly equated with a prohibition."
        if re.search(r"\bemergency\b[^.;]*\b(?:first|before|without)\b", clause_text, re.I):
            if "prior written consent" in quoted and not re.search(r"\b(?:exception|beneficial|different|variation)\b", reason, re.I):
                return "An express emergency-repair exception was not considered in the comparison."
        if re.search(r"\bfailure to report\b", clause_text, re.I):
            if not re.search(r"\b(?:report\w*|notification)\b", reason, re.I):
                return "The additional cost condition tied to reporting was not addressed."
    if re.search(r"\b(?:hold|held|withhold|retain)\w*\b[^.;]*\bdisput\w*\b", clause_text, re.I):
        if re.search(r"\b(?:notice|remedy|cure)\b[^.;]*\b(?:deduct\w*)\b", reason, re.I):
            if not re.search(r"\b(?:refund\w*|return\w*|repay\w*)\b", reason, re.I):
                return "Holding a disputed balance was compared with a deduction procedure without establishing the connection."
    for item in comparisons or []:
        if item["relation"] == "equivalent" and conditional_subletting(item["contract_quote"]):
            ref = " ".join(evidence[index]["quote"] for index in item["evidence_indices"]).casefold()
            if "sublet" in ref and not re.search(r"\bsublet\w*\b[^.;]*\bconsent\b", ref):
                return "The structured comparison equates conditional subletting with an unqualified restriction."
        scope = source_scope_issue("The reference " + item["reference_claim"],
                                   [evidence[index] for index in item["evidence_indices"]])
        if scope:
            return scope
        if label == "review_required" and omission_issue(item["reference_claim"], item["contract_quote"]):
            return "A structured comparison relies on an omission rather than an explicit contract term."
    return None


def direct_no_review_allowed(clause_text: str) -> bool:
    """Do not bypass the model for conditional/negative additions a matcher ignores."""
    return not re.search(
        r"\b(?:emergency|disputed?|sole discretion|absolute discretion|failure to report|"
        r"late charge|late fee|penalty|interest|at any time|however|except)\b|"
        r"\b(?:not required|need not|does not|no written|without (?:written )?notice)\b|"
        r"\bnot\b[^.;]{0,35}\b(?:pay|give|allow|provide|obtain|refund|remedy|rectify)\b",
        clause_text, re.I,
    )
