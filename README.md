# Singapore Rental Contract Review

An individual PE6201 prototype that compares selected English clauses from Singapore residential tenancy agreements with the relevant CEA agreement template. Choose **HDB** or **Private Residential** before review. The output is one of `review_required`, `no_material_difference_found`, or `insufficient_evidence`, with source-backed evidence when it does not abstain. It is **not legal advice** or a verdict that a contract is safe to sign.

## Current result

The [v13 local improvements](docs/offline_improvements_v13.md) were followed by an [actual development check and v13.1 postprocessing repair](docs/development_check_v13.md). The original paid run used 10 model calls / 21,586 tokens and scored 8/8 risk precision, 8/12 recall, 0/5 unsafe non-abstentions and 19/19 internally supported citations. Four correctly identified risks were rejected because the verifier paraphrased the explanation. After a local repair, **recorded-response replay, not a fresh live model run**, scored 12/12 precision, 12/12 recall, 0/5 unsafe non-abstentions and **22/23 (95.65%) internally supported citations**, with one uncertain wording claim counted as not supported. Seven of 30 cases abstain. All 109 local tests pass. This repeatedly tuned development/replay result is not an independent external result or a guarantee of reliability.

The v13.1 repair retains exact contract spans, evidence checks and per-comparison verification; it revalidates paraphrased approval prose rather than requiring identical strings. The notice-validity wording in DEV_15 still needs correction, and DEV_29's actor mismatch remains an abstention. Saved v12 external failures are now regression material, so a fresh independently labelled holdout is needed for a new generalization estimate.

The local development set has 30 synthetic cases. On the locked v10 run, review-required precision and recall are both 12/12, unsafe non-abstention is 0/5, and **substantively supported citation is 23/24 (95.83%) on an internal first pass**, counting one uncertain citation as not supported. This is a repeatedly tuned development result, not external validation. Read the [v10 evidence and citation report](docs/retrieval_and_citation_v10.md) for the full denominator, SHA-256-locked audit, costs, limits and reproduction commands. Earlier [error](docs/development_error_audit.md) and [citation](docs/citation_audit_followup.md) audits remain for comparison.

The subsequent [v11 risk-focused rubric](docs/risk_review_v11.md) changes the decision criterion from any material template difference to a concrete, potentially tenant-adverse and actionable difference. The [v12 development check](docs/risk_focused_v12.md) reports a 23/24 (95.83%) internally audited citation result on the same 30 repeatedly tuned cases. The [completed external 20-case evaluation](docs/external_evaluation_v12.md) found 10/10 review precision, 10/15 recall, 0/4 unsafe non-abstentions, but only **5/13 (38.46%) substantively supported citations on an internal first pass**. Thus the 95% citation target has not generalized. The user reported label agreement, but no independently annotated file or per-case adjudication notes were supplied; see `data/external_review_provenance.json`.

## Run locally

Install `requirements.txt`, download the registered CEA PDFs with `python scripts/download_sources.py`, and build the local index with `python scripts/build_section_index.py`. Run tests with `python -m unittest discover -s tests -q`. The final synthetic predictions are in `results/development_rag_predictions_v10.csv`, and their separate human-review verdicts are in `data/development_citation_audit_v10.json`.

For a new live review, keep `OPENROUTER_API_KEY=...` in the ignored repository-root `.env`; never commit it. The live path uses clause-level retrieval, exact numbered evidence spans, a structured draft, a second evidence check, and safe abstention. The development runner caps calls and tokens and refuses to overwrite existing results.

For local checking without credits, run `python scripts/check_v13_offline.py` or add `--offline` to `scripts/review_clause_live.py`. A clause requiring the model is reported as `model_needed`, not as a completed prediction. New development runs save grounded comparisons as well as reasons and reference evidence.

Run `python scripts/score_v13_development_check.py` to recompute the separately locked original and replay results without API calls. Their citation audits are `data/development_citation_audit_v13.json` and `data/development_citation_audit_v13_1_replay.json`. The one-time live/replay harnesses refuse to overwrite saved artifacts; scoring does not repeat a paid run. Raw model responses are saved for the approved synthetic cases only, without an API key.

## Safety and scope

CEA templates are comparison references, not mandatory legal standards. HDB and private references never mix. The registered checklists are not used as contract-clause sources. This project is for synthetic development cases only: do not upload real contracts, addresses, NRIC/passport numbers, signatures or other personal data to the model API. The evaluated 20-case external set is now exposed regression material; future independent performance claims require a fresh holdout.
