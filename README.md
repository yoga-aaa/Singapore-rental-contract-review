# Singapore Rental Contract Review

An individual PE6201 prototype that compares selected English clauses from Singapore residential tenancy agreements with the relevant CEA agreement template. Choose **HDB** or **Private Residential** before review. The output is one of `review_required`, `no_material_difference_found`, or `insufficient_evidence`, with source-backed evidence when it does not abstain. It is **not legal advice** or a verdict that a contract is safe to sign.

## Current result

The [v13 local improvements](docs/offline_improvements_v13.md) add exact contract-to-reference comparisons, per-comparison verification, reference context, multi-topic retrieval and stricter inference checks. All 91 local tests pass; this iteration used **zero API calls/tokens**. Real-model performance for v13 is still untested. Saved v12 external failures are now regression material, so a fresh holdout is needed for a new generalization estimate.

The local development set has 30 synthetic cases. On the locked v10 run, review-required precision and recall are both 12/12, unsafe non-abstention is 0/5, and **substantively supported citation is 23/24 (95.83%) on an internal first pass**, counting one uncertain citation as not supported. This is a repeatedly tuned development result, not external validation. Read the [v10 evidence and citation report](docs/retrieval_and_citation_v10.md) for the full denominator, SHA-256-locked audit, costs, limits and reproduction commands. Earlier [error](docs/development_error_audit.md) and [citation](docs/citation_audit_followup.md) audits remain for comparison.

The subsequent [v11 risk-focused rubric](docs/risk_review_v11.md) changes the decision criterion from any material template difference to a concrete, potentially tenant-adverse and actionable difference. The [v12 development check](docs/risk_focused_v12.md) reports a 23/24 (95.83%) internally audited citation result on the same 30 repeatedly tuned cases. The [completed external 20-case evaluation](docs/external_evaluation_v12.md) found 10/10 review precision, 10/15 recall, 0/4 unsafe non-abstentions, but only **5/13 (38.46%) substantively supported citations on an internal first pass**. Thus the 95% citation target has not generalized. The user reported label agreement, but no independently annotated file or per-case adjudication notes were supplied; see `data/external_review_provenance.json`.

## Run locally

Install `requirements.txt`, download the registered CEA PDFs with `python scripts/download_sources.py`, and build the local index with `python scripts/build_section_index.py`. Run tests with `python -m unittest discover -s tests -q`. The final synthetic predictions are in `results/development_rag_predictions_v10.csv`, and their separate human-review verdicts are in `data/development_citation_audit_v10.json`.

For a new live review, keep `OPENROUTER_API_KEY=...` in the ignored repository-root `.env`; never commit it. The live path uses clause-level retrieval, exact numbered evidence spans, a structured draft, a second evidence check, and safe abstention. The development runner caps calls and tokens and refuses to overwrite existing results.

For local checking without credits, run `python scripts/check_v13_offline.py` or add `--offline` to `scripts/review_clause_live.py`. A clause requiring the model is reported as `model_needed`, not as a completed prediction. New development runs save grounded comparisons as well as reasons and reference evidence.

## Safety and scope

CEA templates are comparison references, not mandatory legal standards. HDB and private references never mix. The registered checklists are not used as contract-clause sources. This project is for synthetic development cases only: do not upload real contracts, addresses, NRIC/passport numbers, signatures or other personal data to the model API. The evaluated 20-case external set is now exposed regression material; future independent performance claims require a fresh holdout.
