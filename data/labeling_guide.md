# External evaluation labelling guide

Use this guide only after the source registry and risk criterion are fixed. The existing `external_cases_ground_truth.csv` is an **assistant-authored v0 proposal, not independently reviewed ground truth**. Do not score against it. Give an independent reviewer the sanitized cases and CEA templates **without** that file or any system predictions. Record adjudicated labels in a new `external_cases_ground_truth.reviewed.csv`, commit it before the first external model run, and never change it in response to those predictions.

## Allowed labels

### `review_required`

Use only for a concrete, potentially tenant-adverse difference or a specific uncertainty about the tenant's obligation that a renter can act on before signing. Record the contract term, the explicitly contrasting reference passage, the potential tenant consequence, and a useful question to ask. Different wording or an explicit tenant-beneficial variation alone does not qualify. A missing phrase in one isolated clause does not prove the full agreement excludes a protection. This is not a finding that a clause is illegal, unfair, or unenforceable.

### `no_material_difference_found`

The historical machine-readable name is retained for compatibility. Operationally it means that relevant evidence covers all material issues in the selected clause and **no actionable tenant-adverse difference** was found. Equivalent obligations expressed in different words pass. A clearly tenant-beneficial variation may pass, but the rationale must disclose that actual variation rather than falsely saying the texts are identical. This is not approval to sign the agreement.

### `insufficient_evidence`

Use when the selected housing type is uncertain or mismatched, the isolated clause is too vague to compare, the relevant reference source is unavailable, or a suspected risk depends only on an unproven omission or source silence. The expected output must abstain rather than infer a legal conclusion.

## Ground-truth procedure

1. Freeze the source registry, including source URLs, housing-type metadata, and retrieval dates.
2. Use the neutral topic-to-clause map in `docs/cea_locator_map.md` to locate likely PDF passages. Verify the PDF original; candidate retrieval is only navigation, not proof.
3. Read each sanitized external clause without seeing the assistant's v0 labels or any system predictions. Compare meaning and tenant consequence, not wording. Do not infer contract-wide omissions from an isolated clause.
4. Record one label, one expected source identifier and section for non-abstaining labels, a brief contrast and tenant consequence, and an actionable question for `review_required`. For `insufficient_evidence`, leave source fields blank and explain what evidence is missing.
5. Resolve disagreements with a second reviewer where possible. Commit the independently reviewed ground truth before the final evaluation run; retain the v0 file for provenance.
6. Generate predictions once without changing prompts, retrieval settings, rules or thresholds in response to the external-case results. Do not force a target percentage of flagged clauses.

## Scoring rules

- A `review_required` prediction is a true positive only if its label is correct and its cited source identifier and section exist in the source registry.
- A non-abstaining result without a valid source citation is invalid, regardless of whether its label happens to match the ground truth.
- Report recall, precision, citation validity, and unsafe non-abstention separately for the external 20 cases.
