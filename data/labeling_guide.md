# External evaluation labelling guide

Use this guide only after the source registry is fixed. Label each sanitized external case once before the final system run. Record the result in `external_cases_ground_truth.csv`; do not change it after evaluating the RAG system.

## Allowed labels

### `review_required`

Use when the selected clause has a material difference from a relevant retrieved reference passage, omits a material term necessary to understand the party's obligation, or contains a condition that a tenant should clarify before signing. The result must identify a specific clause feature and cite a specific source passage. This is not a finding that a clause is illegal, unfair, or unenforceable.

### `no_material_difference_found`

Use only when the available reference material is relevant and sufficient, and the clause contains no material difference for the selected category. This label means only that no material difference was found against the cited reference passage; it is not approval to sign the agreement.

### `insufficient_evidence`

Use when the selected housing type is uncertain or mismatched, the clause is too vague to compare, the relevant reference source is unavailable, or the system cannot establish a supported comparison. The expected output must abstain rather than infer a legal conclusion.

## Ground-truth procedure

1. Freeze the source registry, including source URLs, housing-type metadata, and retrieval dates.
2. Read each sanitized external clause without running the RAG system.
3. Record one label, one expected source identifier, one expected source section, and a brief rationale.
4. Commit the completed ground-truth file before the final evaluation run.
5. Generate the final result table without changing prompts, retrieval settings, rule logic, or thresholds in response to the external-case results.

## Scoring rules

- A `review_required` prediction is a true positive only if its label is correct and its cited source identifier and section exist in the source registry.
- A non-abstaining result without a valid source citation is invalid, regardless of whether its label happens to match the ground truth.
- Report recall, precision, citation validity, and unsafe non-abstention separately for the external 20 cases.

