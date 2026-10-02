# Development citation audit follow-up (2026-10-02)

The first development report showed 100% for a **registered-source/nonempty-locator check**. That was not a substantive citation-validity measure. I reviewed all 27 non-abstaining predictions from the revised 30-case development run against the cited, model-visible CEA page excerpts. The machine-readable judgments and case-specific reasons are in `data/development_citation_audit_v2.json`.

| Measure | Revised development run |
| --- | ---: |
| Registered ID + nonempty locator | 27/27 (100%) |
| Substantively supported citation, internal first pass | 18/27 (66.7%) |
| Unsupported citation | 9/27 (33.3%) |

This is **not an independent blind annotation** and not the external-set result. It is a transparent internal audit of already-seen development predictions. It does not change any ground-truth label or the earlier recall, precision and unsafe-non-abstention counts. The 20 external cases remain unused.

## Rubric and failure pattern

A citation passes only when the cited page, within the 2,200 characters actually shown to the model, directly supports every material *reference claim in the explanation*. A topic heading, an unfilled schedule field, a rule on a different page, or an inference from the absence of a term does not count. The rubric scores the cited explanation, independently of whether the prediction matches its case label. It does not yet score omission of a separate issue in a multi-topic clause; DEV_09, for example, cites the utilities rule but does not analyse its rent sentence. A second reviewer should check these judgments before they are presented as definitive.

The nine unsupported cases are:

| Case | Why the citation failed |
| --- | --- |
| DEV_01 | The template refers to a configurable deposit in ITEM 9; it does not prescribe the one-month amount claimed in the explanation. |
| DEV_06 | The cited page has service methods and a specific damage-related termination, not the general termination-ground claim or a rule invalidating all text messages. |
| DEV_10 | The explanation infers a billing-transparency rule absent from its cited excerpt. |
| DEV_13 | The cited subletting text does not support the claimed HDB-approval exception. |
| DEV_15 | The cited page has written termination, but the delivery methods asserted in the explanation are on the next page. |
| DEV_23 | The cited private-template page concerns storage/use; the relevant occupancy limit is elsewhere. |
| DEV_24 | The page supports the rent term, but the utility-duty claim in the explanation is on the next page. |
| DEV_25 | A rent schedule field cannot establish that no late charge exists; the template elsewhere specifies default interest. |
| DEV_26 | The cited page discusses termination and late rent, not an agent's authority to change rent or fees. |

The JSON audit records the prediction and index SHA-256 hashes, the exact source/page pair, a short text anchor, verdict and rationale for every non-abstaining case. `src/citation_audit.py` rejects missing cases, changed files, mismatched locators and anchors absent from the excerpt. It **verifies audit integrity, not the human semantic judgment**. `src/evaluate.py` now returns `citation_validity: null` without a matching audit, rather than silently reporting 100%; the old mechanical measure is retained separately as `citation_locator_validity`.

To score the already-generated development run offline, with its ignored prediction CSV and indexed CEA pages present locally:

```powershell
python scripts/score_development_citation_audit.py
```

No API call is made. The next implementation priority is a passage-level evidence requirement in the live output (for example, a short extractive quote validated against the cited page), followed by development-only retesting. That alone will not prove semantic relevance; an independent human citation review and rubric-based adjudication of DEV_08/DEV_23 remain necessary before freezing the system for the one-time external evaluation.
