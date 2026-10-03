# v17 paid regression: better labels, unsupported reasoning remains

## Release decision

Use as a synthetic local classroom prototype and reproducible failure analysis, **not a real-contract screening service**. The 95% substantive citation support goal is not met. The evaluated predictor is preserved in a separate exact-byte snapshot; subsequent UI-only evidence displays do not change that evaluated model pipeline. There is no scheduled extra paid run.

## Design and provenance

After the original v16 diagnostic, the owner authorized one additional v17 batch in response to a request specifying at most US$0.50, 40 calls, 200,000 tokens and no automatic retries. The owner's reply was “所有都授权”; it was recorded as this bounded batch, not unlimited spending. Only the same twenty synthetic cases were transmitted, never real agreements or personal records.

The twenty cases were authored by DeepSeek and reviewed in a separate DeepSeek chat according to the owner. The original complete chats and exact model versions are unavailable. A project-assistant source adjudication, accepted by the owner before v16 prediction, produced 14 risk, 2 limited-pass and 4 insufficient-evidence labels. These exact labels were copied unchanged into v17. No label changed after either prediction run. The cases were already exposed in source diagnosis and v16 error analysis: **this is regression, not independent generalization or legal-expert gold**. The old separate twenty-case batch and thirty development cases are not pooled into these denominators.

v17 selects contract-span IDs, locally attaches exact input text, repairs rent/deposit topic routing, and rejects several procedure and coverage mistakes. It uses the same corrected v15 CEA index, GPT-4.1 drafts and GPT-4o evidence checks through OpenRouter. Provider price ceilings, pre-call budget reservations and usage accounting were enforced. The model-side evidence checker is a component under test, not the final substantive auditor.

## Results, complete denominators

| Measure | Frozen v16 | Paid v17 regression | Unchanged keyword baseline |
|---|---:|---:|---:|
| Risk precision = TP / (TP + FP) | 1/2 = 50% | 5/5 = 100% | 3/4 = 75% |
| Risk recall = TP / 14 labelled risks | 1/14 = 7.14% | 5/14 = 35.71% | 3/14 = 21.43% |
| Unsafe non-abstention / 4 insufficient-evidence cases | 2/4 = 50% | 0/4 = 0% | 4/4 = 100% |
| Valid exact source locator / non-abstaining results | 4/4 = 100% | 6/6 = 100% | Not audited |
| Substantively supported citation / all non-abstaining results | 1/4 = 25% | 2/6 = 33.33% | Not assessed |
| Abstentions / all cases | 16/20 | 14/20 | 0/20 |

v17 has TP=5, FP=0, FN=9. `review_required`: NEW_01, NEW_02, NEW_11, NEW_16, NEW_18. Limited pass: NEW_03. All other fourteen cases abstained; the four gold insufficient-evidence cases are included, not removed. Precision's numerator means a risk label matches the frozen label, **not that its explanation or cited quote is correct**. Fourteen abstentions and nine missed labelled risks limit usefulness even though precision and unsafe rates improve.

## Substantive citation first pass

The project assistant checked the exact original predicted claims against the cited paragraphs and qualifying PDF context. Every claim and applicable condition must be supported for a result-level pass. A real locator alone is insufficient. Uncertain items remain in the denominator and count as failures. The owner has not yet confirmed this new audit; it is neither a law student's independent blind review nor a statistical generalization claim.

| Case | First pass | Reason for this result-level decision |
|---|---|---|
| NEW_01 | Unsupported | Permission to deduct does not itself establish immediate deduction or an express waiver; the explanation omits the agreed deposit exception and does not match the labelled refund-timing concern. |
| NEW_02 | Unsupported | Claims after refund are not the same as the quoted deposit-deduction process; the needed joint-inspection protection is not supplied by that comparison. |
| NEW_03 | Unsupported | A passing mediation comparison omits the refund-timing obligation and a qualifying agreed-period exception; it does not cover all material obligations in the input. |
| NEW_11 | Uncertain; counted as failure | A documentation concern may be useful, but the combined comparison of evidence and use-once scope is not fully supported by the chosen span. |
| NEW_16 | Supported, limited claim | The actual residence-related termination trigger differs from the cited rent or breach triggers. This does not establish an exhaustive legal list or approve all occupancy arrangements. |
| NEW_18 | Supported, limited claim | The weekly/part-week interest trigger and preserved cap differ from the cited annual rate and waiting period. No extrapolated annual-rate or illegality claim is approved. |

Two of six results pass (33.33%); three fail and one is uncertain. The contract-quotation abbreviation failure seen in nine v16 cases disappears, but the dominant remaining problem is substantive reasoning, including omitted conditions and incomplete multi-obligation coverage. Citation validity and safety cannot be collapsed into one “accuracy” figure. A correct model label must not be used to override a failed substantive audit.

## Actual costs and preservation

v17 completed 20/20: 36 calls, 91,115 prompt tokens, 8,469 completion tokens, 99,584 total tokens, **US$0.2722430**, no failed or unaccounted calls. v16 cost US$0.2383215; together US$0.5105645, 65 calls, 183,147 tokens. This is measured clause-batch spending, not one complete agreement. v17 average US$0.01361215 per fragment; twenty clauses at that average project US$0.272243, not a measured document-wide review. App JSON records actual accounting for a selected document operation. These model batches are not replayed to open a report or record the offline demo.

Exact-byte SHA-256 locks:

| Artifact | SHA-256 |
|---|---|
| v17 manifest | 5180b2abc1eff1949901b8ed2d0ecb1f4f2dac969ebd463e731b73cce64439c2 |
| Original v16 manifest | 595f140fc49bb45e33ee6d7a44961046608fcb13cf173d29f478fdc0a62cd921 |
| Labels, identical in both freezes | 4f3dcc47121990136b951952fabea988203522fee945237ac00697ffefee2b1f |
| v17 predictions | 922e2dcb9e3730882dd23393cc092944bb46df66afd6b590901509b1050825c4 |
| v17 call ledger | 60c31386deb951314549b2dcd913cc60630e7b9a4999d14b03a8d90cf686972f |
| v15 section index, both runs | a29c34e93271281696a74766fc18b854c7d175f08004ca592c160749290d0018 |
| v17 citation audit | 33c8054618779c0e20a876ce1944d1dfbfe2cd20aecdd102d15b7bec184cd8fd |

The original private batch folders are kept unchanged outside GitHub. The course-only evidence package excludes credentials and original CEA PDFs; restore those two PDFs through verified official downloads before running the hash-verifying scorer. Do not publicly upload this evidence archive. Only aggregate outcomes and methods are published in this document.

```powershell
python scripts/restore_private_references.py --bundle PATH_TO_PRIVATE/regression_v17/freeze_v17
python scripts/score_frozen_results.py --bundle PATH_TO_PRIVATE/regression_v17/freeze_v17 --run PATH_TO_PRIVATE/regression_v17/run_v17 --audit PATH_TO_PRIVATE/regression_v17/citation_audit_v17.json
```

The restoration and scoring commands do not call model APIs or change labels. Follow the corresponding v16 command for the original diagnostic. No further model inference, relabeling or selection of only supported outputs is hidden in these numbers. A new generalization claim requires a genuinely new independent set and locked labels, after substantive support improves.
