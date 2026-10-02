# External 20-case evaluation: frozen v12 pipeline

Completed on 2026-10-03. This is an evaluation result, **not a successful 95% external citation-validation claim**. The 95.83% substantive-citation result on the repeatedly tuned 30-case development set did not generalize to this holdout under the same conservative first-pass rubric.

## Protocol and provenance

The 20 synthetic, sanitized clause texts were written outside the development set. The user confirmed they contain no personal data and authorized OpenRouter transmission and API-credit use. The user also reported agreement with the assistant's 20 provisional labels. However, no independently annotated file, reviewer identity/method, or per-case review notes were provided. The rationales and expected sections remain assistant-authored v0 material, so this is a **user-attested label set, not independently demonstrated ground truth**. See [`data/external_review_provenance.json`](../data/external_review_provenance.json).

The reviewed-label file was committed at `43c9161343f724e71e9f0ca36a350c9525f901fa` before any external prediction. The review model, retrieval index, prompts, rules, and labels were not changed after that freeze. The first run stopped at 18 cases because of its conservative token reserve. The user then approved up to four more calls and 20,000 more tokens. [`scripts/resume_external_evaluation.py`](../scripts/resume_external_evaluation.py) checked SHA-256s for the sanitized input, reviewed labels, source index, and exact 18-row checkpoint before appending only `EXT_19` and `EXT_20`. It made two additional calls and used 3,095 additional tokens. The completed predictions have canonical (line-ending-normalized) SHA-256 `220cfab4e95d80fe61a882f6385bb4d81d22568f4dd5bdbc54bbe5b1868ec27d`; the source-section index has canonical SHA-256 `144d3e32bd50512938d0a1de67ce4c0f348078f2206f038826039143504de9ea`.

## Locked results

| Measure | Result |
|---|---:|
| Cases | 20 |
| True `review_required` | 15 |
| `review_required` precision | 10/10 = 100% |
| `review_required` recall | 10/15 = 66.67% |
| True `insufficient_evidence` | 4 |
| Unsafe non-abstention | 0/4 = 0% |
| Citation locator validity | 13/13 = 100% |
| **Substantively supported citation, internal first pass** | **5/13 = 38.46%** |
| Unsupported / uncertain citations | 7 / 1; both count against support |
| API usage | 32 model calls; 51,963 prompt + 4,158 completion = 56,121 tokens |

The 95% substantive-citation target was **not met** on this holdout. Even with every prediction's source ID and section structurally valid, a correct locator often did not substantiate the generated comparison. The 13-case audit is in [`data/external_citation_audit_v12.json`](../data/external_citation_audit_v12.json); it is hash-locked to the predictions and source index, but is **an agent's internal first pass**, not independent human citation adjudication. A second reviewer should inspect the original CEA PDFs and the exact reasons before treating 5/13 as a final human-validated figure.

### Case-level failures

Five of the 15 locked review cases were missed: `EXT_05` and `EXT_14` (broad early-termination rights were rejected by the reference-topic check), `EXT_07` (conditional subletting was incorrectly treated as matching a prohibition), `EXT_12` (the emergency-repair-before-approval exception and extra late-reporting cost condition were overlooked), and `EXT_16` (conditional subletting and possible higher charges were treated as an omission-only issue). The first two and `EXT_16` abstained; `EXT_07` and `EXT_12` were wrongly marked no actionable difference.

Among the 13 non-abstaining reasons, `EXT_01`, `EXT_02`, and `EXT_20` inferred permission to bypass deposit notice/cure from a single clause's silence. `EXT_11` conflated holding a disputed deposit balance with making a deduction. `EXT_06` described the reference's termination grounds as exhaustive while its model-visible section also contains immigration/status-based automatic termination. `EXT_07` contradicted its own subletting source. `EXT_12` ignored an express emergency exception. `EXT_09` was marked uncertain: the late-charge comparison is cited, but “only” and the claimed absence of a payment-allocation rule overstate what the cited excerpts prove. The remaining five (`EXT_03`, `EXT_04`, `EXT_13`, `EXT_15`, `EXT_17`) were supported on this first pass. The per-case notes and primary source anchors are in the audit file.

### Label-quality limitation

The fixed labels were **not revised after seeing predictions**. Some v0 rationales should nevertheless be blind-adjudicated for consistency with the later v12 criterion of an actionable, potentially tenant-adverse issue. In particular, `EXT_12` calls the tenant's emergency-repair exception a review trigger even though that exception may be tenant-beneficial; `EXT_07`, `EXT_15`, and `EXT_16` treat conditional subletting as a material template difference without fully separating a tenant-adverse risk from a potentially more permissive term. `EXT_01` and `EXT_11` also merit review because an isolated omission or temporary holding of funds need not establish a contract-wide loss of protection. These caveats do **not** license post-hoc relabeling of this scored run. Any later adjudicated set must be versioned separately, with both original and revised scores disclosed.

The CEA templates are non-mandatory comparison references, not statements of legal validity or enforceability. The system should not characterize all differences from them as unlawful or dangerous.

## Reproduce, without further API calls

After restoring the repository's registered source PDFs/index and prediction CSV, run:

```powershell
python -m unittest discover -s tests -q
python scripts/score_external_evaluation.py
```

The scorer requires exactly `EXT_01`–`EXT_20`, checks the citation audit's prediction/index hashes and all 13 evidence quotes against the model-visible indexed excerpts, then prints the metrics and usage. The prediction CSV is [`results/external_rag_predictions_v12.csv`](../results/external_rag_predictions_v12.csv). Neither command calls OpenRouter.

## Decision for the next project iteration

Do not present the current pipeline as meeting a 95% external citation standard or as safe for real contracts. First obtain a genuinely independent, blind adjudication of case labels and of the 13 citation judgments; separately investigate reference-topic gating (`EXT_05`, `EXT_14`, `EXT_16`), conditional-permission logic (`EXT_07`, `EXT_15`, `EXT_16`), and reason-level entailment/omission handling (`EXT_01`, `EXT_02`, `EXT_06`, `EXT_09`, `EXT_11`, `EXT_12`, `EXT_20`) on **new development examples**. Freeze a new version, then evaluate once on a **fresh** holdout. Do not tune against these 20 and then report them as an unbiased external test.
