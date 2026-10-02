# Singapore Rental Contract Review

An individual PE6201 prototype that compares selected English clauses from Singapore residential tenancy agreements with the relevant CEA agreement template. Choose **HDB** or **Private Residential** before review. The output is one of `review_required`, `no_material_difference_found`, or `insufficient_evidence`, with source-backed evidence when it does not abstain. It is **not legal advice** or a verdict that a contract is safe to sign.

## Current result

The local development set has 30 synthetic cases. On the locked v10 run, review-required precision and recall are both 12/12, unsafe non-abstention is 0/5, and **substantively supported citation is 23/24 (95.83%) on an internal first pass**, counting one uncertain citation as not supported. This is a repeatedly tuned development result, not external validation. The 20 independently authored case texts have been read for provisional labeling, but no external model predictions have been generated or used for tuning. Read the [v10 evidence and citation report](docs/retrieval_and_citation_v10.md) for the full denominator, SHA-256-locked audit, costs, limits and reproduction commands. Earlier [error](docs/development_error_audit.md) and [citation](docs/citation_audit_followup.md) audits remain for comparison.

The subsequent [v11 risk-focused rubric](docs/risk_review_v11.md) changes the decision criterion from any material template difference to a concrete, potentially tenant-adverse and actionable difference. The [v12 development check](docs/risk_focused_v12.md) reports the resulting local tests, a new paid run on the same 30 synthetic development cases and a separately locked citation audit. It is still **not external validation**. The 20 external clauses have not been sent to OpenRouter or scored. An assistant-authored v0 label file exists, but is provisional and must not be treated as independent ground truth.

## Run locally

Install `requirements.txt`, download the registered CEA PDFs with `python scripts/download_sources.py`, and build the local index with `python scripts/build_section_index.py`. Run tests with `python -m unittest discover -s tests -q`. The final synthetic predictions are in `results/development_rag_predictions_v10.csv`, and their separate human-review verdicts are in `data/development_citation_audit_v10.json`.

For a new live review, keep `OPENROUTER_API_KEY=...` in the ignored repository-root `.env`; never commit it. The live path uses clause-level retrieval, exact numbered evidence spans, a structured draft, a second evidence check, and safe abstention. The development runner caps calls and tokens and refuses to overwrite existing results.

## Safety and scope

CEA templates are comparison references, not mandatory legal standards. HDB and private references never mix. The registered checklists are not used as contract-clause sources. This project is for synthetic development cases only: do not upload real contracts, addresses, NRIC/passport numbers, signatures or other personal data to the model API. The external 20-case set must not be used for further tuning before its separate evaluation.
