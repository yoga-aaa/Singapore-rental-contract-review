# Risk-focused development check (v12)

The product should surface a concrete, potentially tenant-adverse issue that a renter can ask about, not flag every wording difference from a recommended CEA template. The technical three-label interface is unchanged. `no_material_difference_found` is a legacy token whose operational meaning is **no actionable tenant-adverse difference found in the covered issues**; it never means the agreement is approved or that the text is identical.

## Changes and self-checks

1. The draft and quote-bounded verifier compare rights, costs, deadlines, remedies and tenant consequences rather than lexical similarity. A beneficial variation alone does not require review; source silence or an isolated clause's omission cannot establish a contract-wide missing protection.
2. Model-generated `review_required` now needs a substantive tenant question. An omission-only explanation without an explicit exclusion in the selected clause abstains. A narrow deterministic match handles equivalent personal-delivery/Certificate-of-Posting notice wording.
3. Stand-alone claims about legality, validity, enforceability or fairness are removed from model explanations before release. This addressed a new v11 explanation that inferred legal enforceability from a notice-method comparison; the remaining comparison is still source-backed.
4. The first v11 diagnostic preserved 12/12 review precision and recall and 0/5 unsafe non-abstentions but lost one no-review notice case to abstention. The v12 direct paraphrase match restored it. All 52 local tests pass, including omission-only, explicit exclusion, equivalent wording, legal-overclaim and external-run gate tests.

## Locked internal first pass

The same 30 synthetic development cases were used for prompt tuning and regression checks. They are **not** an independent estimate of real-world performance or flag rate. No external model predictions were inspected or used for these changes.

| Measure | v12 result |
|---|---:|
| `review_required` recall | 12/12 = 100% |
| `review_required` precision | 12/12 = 100% |
| Unsafe non-abstention | 0/5 = 0% |
| Non-abstaining coverage | 24/30 = 80% |
| Citation locator validity | 24/24 = 100% |
| Substantively supported citation, internal first pass | **23/24 = 95.83%** |
| Uncertain citation, conservatively not supported | 1/24 (DEV_29) |

The v12 prediction CSV is `results/development_rag_predictions_v12.csv`, canonical SHA-256 `5e32eb2cdd1ec937cec3f3e56d87443368ec141025619d91e386bc9065618c19`. The source index canonical SHA-256 is `144d3e32bd50512938d0a1de67ce4c0f348078f2206f038826039143504de9ea`. Canonical hashing normalizes Windows/Unix line endings before SHA-256 so a Git checkout is reproducible across platforms. `data/development_citation_audit_v12.json` reviews all 24 non-abstaining results; the scorer rejects hash or locator mismatches. DEV_29 remains uncertain because the reference assigns occupier-document production to the **tenant**, while the test clause assigns it to the **occupants**. Do not round 95.83% to 100% or describe this agent-authored audit as independent human validation.

The v12 run used 8 paid model calls, 11,466 input and 820 output tokens (12,286 total). The earlier v11 diagnostic used 9 calls and 14,234 tokens; together these two development checks used 17 calls and 26,520 tokens. No external clauses were sent and no real contract was processed.

Reproduce the local tests and locked audit after rebuilding the registered PDF index:

```powershell
python -m unittest discover -s tests -q
python scripts/score_development_citation_audit.py --predictions results/development_rag_predictions_v12.csv --index data/derived/source_sections.jsonl --audit data/development_citation_audit_v12.json
```

## External evaluation remains pending

The previously committed `data/external_cases_ground_truth.csv` is an assistant-authored, disputed v0 label proposal and must **not** be used as the external gold standard. An independent reviewer should use only the sanitized cases, the revised labeling guide, the neutral PDF locator map and original CEA PDFs, then lock a separate `data/external_cases_ground_truth.reviewed.csv` before prediction. `scripts/run_external_evaluation.py` refuses to start until that reviewed file exists. Sending these externally authored clauses to OpenRouter also requires the user's separate confirmation that they are synthetic, contain no real or personal data, and may consume a small amount of credits. No external run has happened.
