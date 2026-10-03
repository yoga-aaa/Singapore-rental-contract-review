# Singapore Rental Contract Review

An individual PE6201 prototype that compares selected English clauses from Singapore residential tenancy agreements with the relevant CEA agreement template. Choose **HDB** or **Private Residential** before review. The output is one of `review_required`, `no_material_difference_found`, or `insufficient_evidence`, with source-backed evidence when it does not abstain. It is **not legal advice** or a verdict that a contract is safe to sign.

## Current deliverable: v17 local web prototype

The app supports synthetic English text, readable PDF upload, extracted-fragment preview, housing selection, exact reference excerpts, actionable questions and JSON export. Offline mode is the default and makes no model calls. Unresolved clauses display `model_needed`, not a fabricated prediction. Live mode remains experimental and needs server enablement plus explicit synthetic-data and spending confirmations. This is not deployed for real contracts.

Tested with Python 3.12 on Windows. Start a fresh checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/bootstrap.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts/check_product.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://127.0.0.1:8501. On macOS/Linux use `.venv/bin/python` in place of the Windows executable. Internet is needed for packages and official reference downloads, not for offline review. Source PDFs and indexes are not redistributed in the public repository. Bootstrap checks the template and index hashes; changed upstream documents stop setup rather than silently certifying old scores.

Five readable synthetic PDFs are in `data/demo_pdfs/`. Their expected outputs are declared before execution in `scripts/check_product.py`: supported risk, limited pass, insufficient evidence, private notice pass, and unfinished `model_needed`. They are reused demonstrations, not a new benchmark. The full offline suite includes browser-independent Streamlit interaction tests.

The current suite discovers 167 tests. With the original local legacy index available, all 167 run; a fresh checkout intentionally skips two historical v13 score-reproduction tests because bootstrap builds only the corrected v15 index. All other 165 tests run, including current PDF/layout, safety, budget and UI checks. Historical scores must not be recomputed using a different index. The original archive remains available locally, rather than reassigning its hashes to the new parser output.

The [original v16 live diagnostic](docs/external_evaluation_v16.md) completed all 20 external-source cases for **US$0.2383215**: **50% precision, 7.14% recall, 50% unsafe non-abstention, 100% locator validity, and 25% substantive citation support on an assistant first pass**. The unchanged keyword baseline beat v16 on precision and recall. The separately authorized [v17 paid regression](docs/regression_evaluation_v17.md), on the **same exposed cases and unchanged labels**, cost **US$0.2722430**: **5/5 precision, 5/14 recall, 0/4 unsafe non-abstention, 6/6 locator validity, but only 2/6 (33.33%) substantive support**; 14/20 abstained. Citation audits await owner confirmation, not expert validation. The 95% goal remains unmet, and correct labels do not certify explanations. Total spend is US$0.5105645. Do not present this regression or historical tuned development scores as independent generalization.

Read [the final English report](docs/final_report_en.md), [Chinese handover guide](docs/submission_guide_zh.md), [bilingual demonstration script](docs/demo_script_bilingual.md), and [design and risk record](docs/design_and_risk_v17.md). The final PDF/video and private evidence archive are kept outside Git publication in the ignored `submission/` folder.

The [source-expansion and recall diagnosis](docs/reference_expansion_plan.md) identifies seven newly checked official background links and their permitted scope. They are candidates, not sources used in either scored run; no improved model performance is claimed from finding links. The plan prioritizes per-obligation evidence coverage and correct reasoning as well as targeted source expansion.

For a separately authorized paid synthetic review, place `OPENROUTER_API_KEY=...` in the ignored repository-root `.env`, set `$env:RENTAL_ENABLE_LIVE="1"` before starting the server and confirm the paid action in the UI. Budget limits apply per review-button operation, not as a permanent account cap. No automatic retries are made. Do not enable or upload real personal documents for a class demonstration.

## Reference repair and frozen evaluation provenance

The [v15 source/index repair](docs/pdf_index_repair_v15.md) fixes PDF number/body misalignment, including vertically centred labels, and switches current review/query commands to versioned layout indexes. There are 135 section excerpts and 45 source pages. With the [v16 freeze and metered preflight](docs/frozen_external_preflight_v16.md), 143 local tests pass. The original PDFs, legacy indexes and saved evaluations remain unchanged. This is engineering verification, **not a new model evaluation or a 95% citation result**.

For current local checking without credits:

    python scripts/check_v15_offline.py
    python -m unittest discover -s tests -q

Current defaults are data/derived/source_pages_v15.jsonl and data/derived/source_sections_v15.jsonl. Build them with build_source_index.py and build_section_index.py if absent. Builders refuse to overwrite; choose a new --output filename for another candidate. The older check_v13_offline.py and saved-result scoring commands below remain historical legacy-index diagnostics. Their scores cannot certify the corrected index's source locators or substantive support; a new, separately audited run is required.

The new AI-authored, separately AI-reviewed batch is outside the public repository. Adjudicated labels were accepted and frozen before v16 prediction, then copied byte-for-byte to the separate v17 freeze. The batch is not expert-blind gold and was exposed during diagnosis and regression. Default preflight makes no API calls. Private snapshots preserve both evaluated predictors; old freezes do not certify different runtime code. Current interface-only result display updates are not a new predictor evaluation.

## Historical results (legacy index, not validated v15 scores)

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
