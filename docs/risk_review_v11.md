# Risk-focused clause review (v11, pre-evaluation)

## Product decision

Help a student renter identify a *small set of actionable questions* about an English HDB or private-residential tenancy clause. Compare rights, obligations, costs, triggers, deadlines and remedies with the matching CEA template, not word overlap. The template is a versioned comparison reference, not mandatory law. A result never certifies legality, fairness or safety to sign.

| Output token | Operational meaning |
|---|---|
| `review_required` | A source-supported, potentially tenant-adverse term or concrete uncertainty about the tenant's obligation; give a specific consequence and question. |
| `no_material_difference_found` | Legacy token: relevant evidence covers the clause and no *actionable tenant-adverse* difference is found. Paraphrases and clearly beneficial variations do not trigger review. Describe a beneficial variation honestly rather than saying the texts are identical. |
| `insufficient_evidence` | The text or reference cannot support a reliable comparison; do not turn silence or a missing phrase in one isolated clause into a contract-wide claim. |

The three output tokens remain compatible with the proposal. Their user-facing descriptions must carry this operational meaning. A narrower `review_required` criterion is intended to reduce noise, **not** to meet an arbitrary quota: precision and recall must still be reported together. The number flagged in 20 constructed cases is not an estimate of the flag rate on real contracts.

## What changed in code

- Draft and independent verifier prompts now ask for meaning and tenant consequence, reject lexical-only and benign differences, and explicitly address isolated-clause omissions.
- Local validation requires a concrete tenant question for every model-generated `review_required`. An omission-only explanation without an explicit excluding term in the supplied clause becomes `insufficient_evidence`.
- Exact source/section and quote validation, topic coverage, fixed-amount safeguards, two-model checking and existing narrow direct comparisons remain in place.

This is a **policy and regression-test change**, not a new model performance result. V10's 23/24 citation support was measured under the earlier rubric and cannot be presented as v11 risk-focused performance.

## Independent review of the external 20

The assistant-authored `data/external_cases_ground_truth.csv` (15 review, 1 no-difference, 4 insufficient) was committed before any external model predictions but is disputed and **not a human-reviewed gold set**. Preserve it as v0 provenance. A reviewer should receive only `data/external_cases_sanitized.csv`, `data/labeling_guide.md`, the neutral `docs/cea_locator_map.md` and the official PDFs. Do not show this internal status report, the v0 labels or model outputs during the independent first pass.

The neutral locator map helps reduce PDF-search effort, but its passages are only candidates. If a candidate section is not directly comparable, search the original matching PDF with synonyms. If no source supports a concrete risk, abstain and note the search limitation; do not infer risk from template silence. After independent labeling and disagreement adjudication, save `data/external_cases_ground_truth.reviewed.csv`, commit it, then perform one separately authorized external API run and a separate citation audit. The runner refuses to start until that reviewed file exists. No external model call or spending was made for v11 at the time of this document.
