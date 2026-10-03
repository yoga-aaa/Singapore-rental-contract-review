# v18: verified sources and mechanism-level evidence

Status: implemented locally and in the opt-in UI; offline tested, **not paid-evaluated**. Candidate labels will be independently re-reviewed before freezing. No 85% or 95% accuracy/support claim is made.

## Verified first-party sources

Seven official HTTPS pages were checked on 3 October 2026: HDB rental regulations and bedroom terms, URA renting rules, IRAS lease duty and duty payer guidance, Singapore Courts small-claim eligibility, and CEA agent-dispute resolution. See `data/official_reference_registry_v18.json` for exact URLs, publisher, permitted scope, exclusions, original HTML hashes, reviewed article hashes and extraction boundaries.

The registry adds 49 complete local sections to the 135 unchanged CEA template excerpts. Full HTML and derived text remain ignored rather than published with Git. Website navigation and dynamic timestamps are not contract evidence. HDB rich text is read from its own embedded Sitecore `BodyContent` payload, not from a search summary. Header-only pages fail closed.

The bootstrap allows a changed dynamic wrapper only if the complete reviewed article hash is identical. A substantive change stops setup for a new reviewed version. A local snapshot manifest pins each actually cached HTML file's exact bytes. Prediction-time loading checks both the pinned index and snapshots; it does not browse the internet.

## Selection and comparison changes

- Mechanism bundles collect deduction/refund, joint-inspection/post-handover claims, dispute route, repair threshold/allocation, self-help and report fees separately. Dispute and end-of-tenancy text formerly lacking retrieval topics is now discoverable without editing historical source text.
- At most nine complete CEA sections and three scoped official sections are supplied, with a 26,000-character total bound. No excerpt is silently chopped. URA occupancy caps travel with the qualifying relaxation conditions.
- The draft and verifier both see the full same packet. The verifier may correct a wrong reference choice, not just endorse or reject the draft's chosen quotations.
- Contract, obligation and reference identifiers are constrained to enums generated from the actual input/packet. The program attaches exact contract text and complete selected reference sections; the model cannot generate citation quotations.
- Pass requires coverage of all contract spans and all cue-derived mechanisms, no unresolved issue and no packet truncation. This cue inventory is not a claim of perfect legal issue extraction.
- A narrowly supported adverse finding can be returned without approving all other terms. Each returned comparison records unassessed spans and its limited scope. Unsupported claims are never presented as evidence-backed conclusions. The output is still subject to an independent substantive audit.
- Local gates reject mixed housing, wrong source/topic/kind, invented numeric reference conditions, unsupported exhaustive claims, omission-as-waiver reasoning and legal/fairness verdicts. Semantic support remains an empirical evaluation question, not something these gates prove.

Model roles remain GPT-4.1 draft and GPT-4o verifier via the existing OpenRouter configuration. No model migration or new authentication method was introduced. Structured atomic output is capped at 2,400 tokens per call; the same per-review US$1 / 40-call / 200,000-token maximum and stop-on-unknown-usage policy apply. No automatic retries.

Prompt roles, data boundaries and test-driven iteration follow [OpenAI's official prompt-engineering guidance](https://developers.openai.com/api/docs/guides/prompt-engineering). This is prompting guidance, not validation of the product's tenancy conclusions.

## Reproduction, labels and honest scoring

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap.py
.\.venv\Scripts\python.exe scripts/bootstrap_official_v18.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Select `v18 — expanded official sources (unmeasured)` in the UI. Offline review retains the historical local deterministic rules and shows `model_needed` for unsettled clauses; it does not simulate the new two-model pipeline. The retrieved-source expander lets the owner check which new sources would be provided.

Per the owner's new request, create a separately versioned label set under the expanded reference scope before another paid batch. Re-review from input-only cases and the reference pack, without old labels, outputs or score targets. Keep an explicit old/new label-change record and freeze after owner confirmation. A different provider/fresh chat reduces information contamination but does not turn AI labels into expert ground truth.

The existing twenty cases are exposed regression cases. New labels do not make them an unexposed holdout. A new generalization claim needs independently authored and separately reviewed new cases, with a frozen predictor before they are opened. v16/v17 remain immutable historical results under their original evidence/label scope.

Substantive support is judged on **every** released non-abstaining result, including every reference claim and adverse consequence. Uncertain support counts as not supported. Verifier agreement is not the metric. Report counts, denominators, source/rubric versions and exposure status separately. For unsafe non-abstention lower is better; it must not be raised above a percentage target.
