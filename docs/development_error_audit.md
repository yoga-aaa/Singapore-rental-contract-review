# Development-set error audit (2026-09-30)

This audit concerns only the 30 synthetic development cases. The 20 independently authored external cases were not opened, sent to the model, or used for tuning. The original development labels in `data/development_cases.csv` remain unchanged. Generated prediction CSVs are local, ignored artifacts under `results/`.

## Comparison on the unchanged labels

| System | Review-required recall | Review-required precision | Unsafe non-abstention | Registered ID + nonempty locator |
| --- | ---: | ---: | ---: | ---: |
| Rules baseline | 7/12 (58.3%) | 7/7 (100%) | 1/5 (20%) | 100% |
| Initial RAG | 12/12 (100%) | 12/15 (80%) | 5/5 (100%) | 100% |
| Revised RAG | 12/12 (100%) | 12/14 (85.7%) | 2/5 (40%) | 100% |

The earlier report divided unsafe non-abstentions by all 30 cases and displayed 16.7% for the initial RAG. The correct conditional denominator is the five cases labelled `insufficient_evidence`, yielding 100%; counts and the corrected denominator are now emitted by `src/evaluate.py`. The revised run used 50,092 prompt tokens and 2,864 completion tokens (52,956 total) for 27 model calls; three cases were rejected before an API call. These numbers are development-set diagnostics, not final-test or population estimates. With only five abstention cases, percentages are especially unstable.

## Case-level findings

| Case | Initial result | Revised result | Audit decision |
| --- | --- | --- | --- |
| DEV_11 | `no_material_difference_found` | `insufficient_evidence` | “Responsible party” does not identify an actor or repair-cost allocation; the old equivalence claim was unsupported. |
| DEV_27 | `review_required` | `insufficient_evidence` | “Handled fairly by the parties” specifies no concrete maintenance duty or allocation. |
| DEV_30 | `no_material_difference_found` | `insufficient_evidence` | A request for respectful cooperation contains no comparison term in the registered reference scope. |
| DEV_08 | `review_required` | `review_required` | Unresolved label dispute: allowing an unspecified number of people to reside may materially differ from the HDB template's stated occupancy limit. The locked label is still `insufficient_evidence`; do not quietly relabel it after seeing predictions. |
| DEV_23 | `review_required` | `review_required` | Unresolved label dispute: “anyone connected with the Tenant” may materially differ from named-occupant wording. The locked label is still `insufficient_evidence`. Its model citation also needs evidence-level review. |

The precheck is intentionally general: a clause with no supported topic, or a repair/maintenance clause with no actor or cost allocation, abstains. It is not keyed to case IDs. Broad occupancy permissions still go to the model because suppressing a potentially material difference merely to improve precision would be unsafe. The rule can still miss paraphrases and should be challenged with independently written cases.

## Citation limitation

The automated 100% figure is **registered-ID/nonempty-locator validity only**, not proof that the cited passage supports the decision. At runtime the source ID and page must now match the *same retrieved chunk*. The index also uses physical PDF page numbers instead of headings guessed from a regex. However, `src/evaluate.py` presently checks that the source ID is registered and the section is non-empty; it does not semantically verify the explanation against the passage. For example, DEV_23 cites private-template PDF page 10, whose visible content concerns storage/use restrictions rather than the named-occupant clause; DEV_26 cites page 12's termination provisions for a unilateral rent-change question. Neither should be called substantively citation-valid without a further evidence audit. Report the locator statistic with this qualification, and do not present it as the instructor's full citation-validity outcome metric.

Before the blind external run, independently adjudicate the two disputed development labels using a written rubric, without consulting model predictions as the deciding criterion. Then implement and manually test a passage-level citation check (for example, an extractive evidence quote verified against the cited page, plus human relevance review). Freeze the model, prompts, sources, rules, and labels before evaluating the external 20 exactly once.

## Reproduction

With the registered CEA PDFs downloaded and `OPENROUTER_API_KEY` configured locally:

```powershell
python -m unittest discover -s tests -v
python scripts/build_source_index.py
python scripts/run_rag_evaluation.py --output results/development_rag_predictions_v2.csv
```

The final command sends only `data/development_cases.csv` to OpenRouter; its script explicitly rejects other input filenames. It consumes API credits. Do not run it on real contracts or the external blind cases during development.
