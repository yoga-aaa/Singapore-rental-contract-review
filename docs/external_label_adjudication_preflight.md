# External 20-case label preflight (not a final gold lock)

On 2026-10-03 the user reported that a human review agreed with the assistant-authored v0 labels. No independently annotated file, reviewer identity, method or per-case notes were supplied in this chat, so this report records the user's attestation rather than claiming an independently auditable gold set.

Read-only structural checks passed: the 20 sanitized case IDs and housing types match the v0 label CSV in order; all labels are valid, all rationales are nonempty, all 16 non-abstaining expected source/section pairs exist in the frozen local CEA index, and the four abstention labels have blank expected citations. No external API run or prediction file exists.

However, v0 was written under a broader "material template difference" interpretation. The current v12 rubric requires a *specific, potentially tenant-adverse and actionable* difference. Before treating identical v0 labels as final, ask the reviewer to re-adjudicate these cases **against v12**, without showing model predictions:

| Case | Why the current rationale needs a second look | What to record |
|---|---|---|
| `EXT_01` | It flags absent written notice/cure language in one isolated deposit paragraph; that does not prove the full agreement excludes it. | Is there another explicit tenant-adverse term (for example a demonstrably later refund trigger) with a direct CEA contrast? If not, revise the label/rationale. |
| `EXT_07` | It flags permission to sublet with landlord consent against a template prohibition. Greater permission alone is not necessarily tenant-adverse; HDB approval is outside the cited `5.1(d)` contrast. | Identify a concrete adverse obligation supported by the registered CEA source, or mark the comparison unsupported. |
| `EXT_11` | It relies on missing notice/cure wording in one paragraph, although the clause expressly lets the landlord hold a disputed amount until resolution. | If retaining `review_required`, ground it in the explicit withholding term and a directly relevant CEA passage, not an inferred whole-contract omission. |
| `EXT_12` | Its cited difference is an emergency-repair exception to *prior* approval, which may benefit the tenant. | If another condition is tenant-adverse, identify it and cite the exact contrast; otherwise revise. |
| `EXT_16` | It cites a template subletting restriction while the clause conditionally permits subletting. Possible higher rent/deposit is a potential burden, but the cited passage does not state charge terms. | Explain the actionable disadvantage and direct source support, or abstain from a claim the source cannot substantiate. |

This table is an adjudication checklist, not a replacement set of labels. Preserve `data/external_cases_ground_truth.csv` as v0. Only after the reviewer resolves the above should a separate `data/external_cases_ground_truth.reviewed.csv` be committed. The external runner remains gated on that file. Sending the 20 clauses to OpenRouter also requires separate explicit confirmation that the payload is synthetic, contains no real or personal data, and may incur a small API charge.
