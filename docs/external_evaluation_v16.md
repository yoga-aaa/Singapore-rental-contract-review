# v16 external source diagnostic evaluation

The authorized frozen run completed all 20 clauses on 3 October 2026. This is the original live result, not the repaired v17 result. Labels were locked before prediction and were not changed afterward.

## Results and denominators

| Measure | v16 RAG | Unchanged keyword baseline |
|---|---:|---:|
| Risk precision | 1/2 = 50.00% | 3/4 = 75.00% |
| Risk recall | 1/14 = 7.14% | 3/14 = 21.43% |
| Unsafe non-abstention, lower is better | 2/4 = 50.00% | 4/4 = 100.00% |
| Citation locator validity | 4/4 results, 8/8 excerpt entries exact | Not substantively audited |
| Substantively supported citation, internal first pass | 1/4 = 25.00% | Not assessed |

The citation audit was performed by the project assistant, not by an independent legal expert. Project-owner confirmation of this new audit is pending. The 95% substantive-support target is not achieved. Sixteen of 20 results abstained; abstention cannot be used to disguise the 13 missed risks. The baseline beats RAG on precision and recall in this batch, although it fails to abstain on all four evidence-insufficient cases.

NEW_07's configurable per-item cap and extra annual ceiling support its limited passing comparison; it is not a complete agreement approval. NEW_08 omits a material plumber-report/cost mechanism. NEW_17 asserts an exhaustive rent-review rule from extension excerpts. NEW_19 confuses seven-day post-deduction replenishment with pre-deduction remedy and omits the reference's agreed-period exception. These latter three fail the audit despite valid source locators.

## What the batch represents

There are 10 HDB and 10 private clauses, with 14 review, 2 pass and 4 insufficient-evidence confirmed labels. DeepSeek generated the cases and reviewed them in separate chats, according to the owner. Exact model versions and full chats are unavailable. The project assistant read these cases during reference parsing diagnosis and proposed corrections accepted by the owner. Therefore this is an AI-authored external-source diagnostic set, not expert-blind gold, real-contract validation, or a strictly untouched generalization test. The older external set and 30 repeatedly tuned development clauses are reported separately in historical reports.

## Cost and integrity

Actual provider accounting: 29 calls, 73,953 input tokens, 9,610 output tokens, 83,563 total tokens and US$0.2383215. Average over the 20 fragments is US$0.011916075 per clause. This does not measure one agreement. A 20-clause cost projection using this average is US$0.2383, not an observed agreement cost. Offline document demonstrations have zero model charges, but may leave clauses as `model_needed`.

The approved run cap was US$1, 40 calls and 200,000 tokens. Provider-only routing, price ceilings, before-call reservations and native usage accounting were applied. No retries, missing usage or unaccounted attempts occurred. Application-level limits do not guarantee account-level billing caps during provider anomalies.

Exact-byte SHA-256 values:

- Frozen manifest: `595f140fc49bb45e33ee6d7a44961046608fcb13cf173d29f478fdc0a62cd921`
- Predictions: `64d56ea370624bb36959197a4c3722879148447ed9195c5bc924240ac5cbb53b`
- Calls: `d9dd37d44b17c8913af976bb78dd120ae2fea962c5b1ff59b5fe0e541856533b`
- Labels: `4f3dcc47121990136b951952fabea988203522fee945237ac00697ffefee2b1f`
- Section index: `a29c34e93271281696a74766fc18b854c7d175f08004ca592c160749290d0018`
- Assistant audit: `b96a3d1b584d851e9f7b5f9140573d2901f8c35563b1fa973c57032647eeadc6`

The private evidence bundle contains inputs, confirmed labels, response bodies, frozen predictor code and audit. It excludes the API key. On the supplied private folder, recompute without API calls:

```powershell
python scripts/score_frozen_results.py --bundle ../external-deepseek-2026-10-03/freeze_v16 --run ../external-deepseek-2026-10-03/run_v16 --audit ../external-deepseek-2026-10-03/citation_audit_v16.json
```

## Failure diagnosis and v17 response

Nine clauses were rejected for abbreviated contract quotes containing ellipses, despite the prompt requesting exact spans. Three failed the second evidence check, and four failed local semantic/precheck rules. v17 requests contract-span IDs and inserts exact text locally; unknown IDs are rejected. New guards reject the observed procedure confusion, unsupported exhaustive rent claims and unassessed report-fee mechanisms. They are unit-tested. They have **not** been evaluated with a fresh paid model run.

Saved-final-output replay is a zero-credit regression diagnostic only. It does not recover model responses for the nine structurally rejected drafts, does not perform missing verifier calls, and does not prove that the new ID-selection prompt works at production accuracy. A one-result supported replay denominator must not be advertised as 100% external reliability. Further quality claims need new authorization and, ideally, a fresh independently labelled set.
