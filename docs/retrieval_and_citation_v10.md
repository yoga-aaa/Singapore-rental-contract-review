# Clause-level evidence and citation audit (v10)

This is a CEA-template comparison prototype, **not** a legal-validity checker. HDB and private residential contracts are supported as separate domains. CEA agreement templates are comparison references, not mandatory law. No real contract or personal data was sent during this development evaluation.

## What changed

1. `scripts/build_section_index.py` extracts the operative numbered clauses and only five schedule fields needed to interpret them (ITEMS 5, 6, 8, 9 and 10). Every excerpt carries its exact source ID, housing type, PDF page and clause/ITEM locator. HDB and private sources never mix; tenant checklists are excluded from contract-clause comparison.
2. `src/retrieval.py` combines BM25 with topic routing and a four-excerpt limit. Mixed rent/utility clauses must retrieve evidence for both topics. The reference excerpts are divided into exact, numbered spans; the model selects IDs, while code supplies the verbatim source text. This removes model-rewritten quotations and preserves OCR spelling for audit.
3. Strict local validation checks source/section pairs, the selected topic, quote presence, every topic for a `no_material_difference_found` result, and some unsafe fixed-amount and silence-based explanations. A second model checks the draft against only its selected quotes. If either stage lacks support, the response abstains.
4. Narrow, documented direct comparisons handle explicit template fields and conditions (e.g. ITEM 10's blank repair cap, ITEM 6's named occupants, deposit notice/cure, specified late-rent interest). They run before paid model calls. These are not legal conclusions; other clauses still fall back to evidence-bounded AI review or abstention.

## Reproduce the local run

From the repository root, on a machine with Python installed:

```powershell
python -m pip install -r requirements.txt
python scripts/download_sources.py
python scripts/build_section_index.py
python -m unittest discover -s tests -q
python scripts/score_development_citation_audit.py --predictions results/development_rag_predictions_v10.csv --index data/derived/source_sections.jsonl --audit data/development_citation_audit_v10.json
```

The last command checks the SHA-256 of both the checked-in synthetic prediction CSV and the locally rebuilt PDF index before scoring. A changed upstream PDF or changed `pypdf` extraction should fail the hash check; do not silently reuse the old audit. To make a *new* paid evaluation, create an ignored local `.env` with `OPENROUTER_API_KEY=...` and run `python scripts/run_rag_evaluation.py --output results/<new-name>.csv`. The runner refuses to overwrite an existing output and stops at 60 model calls or 100,000 tokens by default. Only `development_cases.csv` is allowed by this runner. Do not use it for external cases or real contracts.

## Iteration self-checks

Each change was tested against the same 30 synthetic development labels, with a new output file rather than overwriting prior runs. The intermediate CSVs are local diagnostics (ignored by Git); only v10 is a locked release artifact.

| Stage | Recall | Precision | Unsafe non-abstention | What the check exposed |
|---|---:|---:|---:|---|
| v4 clause-level retrieval | 83.3% | 83.3% | 1/5 | Exact-quote failures and some unsupported explanations. |
| v5 smaller subclauses | 100% | 80.0% | 1/5 | Better retrieval but variable ITEM fields and vague occupancy caused false positives. |
| v6 second-model check | 58.3% | 100% | 0/5 | Over-conservative verification protected precision but harmed recall. |
| v7 numbered evidence spans | 100% | 75.0% | 0/5 | Verbatim citation was reliable, but schedule fields were still missing. |
| v8 schedule fields | 91.7% | 91.7% | 0/5 | Four field-related false positives resolved; manual review found remaining overclaims. |
| v9 direct source contrasts | 100% | 100% | 0/5 | Audit exposed non-substantive wording and stray citation identifiers despite perfect labels. |
| v10 stricter direct comparisons | 100% | 100% | 0/5 | Locked manual citation audit: 23/24 supported, one uncertain. |

These are tuning diagnostics, not seven independent test sets. The external 20-case result is the relevant future generalization check.

## Locked internal first pass

Ground-truth labels were already present before the v10 run. The 20 independently written external cases were **not** evaluated, read for tuning or sent to OpenRouter. All 30 development cases are synthetic. These numbers are development-set performance after repeated tuning, not an estimate of generalization.

| Measure | v10 result |
|---|---:|
| `review_required` recall | 12/12 = 100% |
| `review_required` precision | 12/12 = 100% |
| Unsafe non-abstention | 0/5 = 0% |
| Non-abstaining coverage | 24/30 = 80% |
| Citation locator validity | 24/24 = 100% |
| Substantively supported citation, internal first pass | **23/24 = 95.83%** |
| Uncertain citation, conservatively counted as not supported | 1/24 (DEV_29) |

The audit in `data/development_citation_audit_v10.json` records a verdict and note for **every** non-abstaining case. DEV_29 is uncertain because the template says the *tenant* produces foreign-occupier documents, while the test clause says the *occupants* provide them. Independent review is needed before claiming this comparison is fully supported. The old page-level audit reported 18/27 supported (66.7%); its denominator and system design differ, so the change is not a held-out improvement claim.

## Token and budget estimate

The v10 run made 10 paid model calls across five clauses, using 12,728 input and 976 output tokens in total (13,704 tokens). The other responses used local high-confidence comparisons or abstained. At the [OpenRouter GPT-4.1 rate](https://openrouter.ai/openai/gpt-4.1) of US$2/US$8 per million input/output tokens and the [GPT-4o rate](https://openrouter.ai/openai/gpt-4o) of US$2.50/US$10, an all-GPT-4o upper-bound estimate from the aggregate tokens is about **US$0.042 for 30 clauses**, or **US$0.0014 per clause** for this development mix. An illustrative 20-clause agreement at the same mix is about **US$0.028**; if all 20 require the two-model path, the observed per-model-processed-clause upper-bound scales to roughly **US$0.17**. These are dated estimates, not provider invoices; source length, route, caching and prices can change. The 100,000-token stop implies a conservative US$1 ceiling at US$10/M if prices remain unchanged, but a production system should also enforce a provider-side spending cap.

## Remaining limits

- The internal citation audit is one reviewer's first pass. A peer should independently adjudicate DEV_29 and a sample of the 23 supported cases.
- The external 20-case set must remain blind until prompts, direct rules and thresholds are frozen. Report it separately; do not tune on it afterward.
- Exact-text citation is not semantic proof. The second model can still accept an over-interpretation. The local abstention checks and manual audit are necessary safeguards.
- The PDF parser assumes English, text-readable CEA v1.4 templates. Scans, changed PDF layouts, non-CEA clauses and atypical contract language may fail or abstain.
- Public-repository evaluation data is synthetic. Do not submit unredacted addresses, identification numbers, signatures or real contracts to the API.
