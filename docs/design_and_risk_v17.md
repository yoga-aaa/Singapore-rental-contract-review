# Design and release decision

## Intended use

First-time international student renters are the primary user group. HDB and private housing are separate reference domains, not rental-versus-purchase categories. Whole-unit and room rental text may be compared, but room-specific arrangements unsupported by these whole-property templates must not be treated as equivalent. Only synthetic readable English input is allowed in the course prototype. There is no signing recommendation, legal validity judgment, OCR, automated correspondence or production deployment.

## Ownership and course coverage

| Layer | Choice | Reason and limit |
|---|---|---|
| Interface and serving | Python Streamlit, loopback address | One local process, no account system or public hosting |
| Orchestration | Owned deterministic gates and bounded two-stage pipeline | No autonomous agent or tool execution from contract text |
| Model | Rented GPT-4.1 draft, GPT-4o check via OpenRouter | Structured reasoning at additional cost; verifier is not truth |
| Data and retrieval | Fixed CEA PDFs, pypdf layout extraction, local BM25 | Inspectable and no embedding charges; limited semantic reach |
| Evaluation and observability | Frozen exact-byte manifests, separate scoring, cost accounting | Preserve failure evidence; private raw responses are not GitHub content |

| Course theme | Implementation evidence |
|---|---|
| 1 AI selection and ownership | Named rules baseline; own-versus-rent choices; no classifier training |
| 2 Retrieval augmented generation | Housing filters, schedule/operative sections and exact evidence IDs |
| 3 Prompting and structured output | JSON schema, contract-span IDs and reference comparisons |
| 4 Orchestration and agents | Bounded draft/check stages; autonomous agents deliberately excluded |
| 5 Cost and delivery | Actual clause costs, document accounting, before-call stop and download/bootstrap |
| 6 Responsible use | Data boundaries, abstention, privacy confirmation and limited-use release decision |

These map respectively to AI selection, build/validation, justified alternatives and communication across the four learning outcomes. They demonstrate relevant treatment, not use of every possible course technology.

## Risks with actual controls

| Risk or silent failure | Implemented control | Remaining limitation |
|---|---|---|
| A real citation supports a different claim | Exact spans, per-comparison verifier, scope/procedure guards, separately scored audit | Substantive first-pass support: v16 1/4; exposed v17 regression 2/6; not solved |
| Excessive abstention misses useful risks | Recall reported alongside precision, with full denominators | v17 recall 5/14 and 14/20 abstentions; do not deploy as a risk filter |
| Unsupported pass covers only one part of a complex clause | Topic coverage and report-fee mechanism checks; full input shown | Broad topic matching is not exhaustive obligation coverage |
| PDF silently loses a scanned page | Low-text-page, size, encryption and page-count rejection | Readable but malformed layouts still need user verification |
| Contract instructions override system rules | Contract/reference text kept as data; fixed schema and no model tools | Prompt robustness is not mathematically guaranteed |
| Wrong housing template | Selected-type filtering and explicit mismatch block | Property type cannot always be inferred from text |
| Personal information leaves the machine | Synthetic-only gate, identifier detection, live off by default, memory-only uploads | Names and indirect identifiers may escape detection; not a redaction service |
| Unexpected charges | Model/provider price ceilings, reservations, native accounting, no retry, unknown usage stop | Per-review limits are not account hard caps; repeat clicks are new reviews |
| Label or evaluation leakage | Input-only cases, labels separately frozen, scorer separated from predictor | New cases were exposed during source repair; not untouched generalization |
| API key or private cases get published | Ignore rules and allowlisted source/evidence packaging | Manual uploads still need the owner's check |

No law-compliance certification is claimed. The source templates are recommended comparison material, not statutory requirements. The detector and disclaimer do not replace implemented controls or legal review.

## Changes from the original proposal

The primary group and both housing types remain. The proposed Streamlit and readable-PDF workflow are implemented. FAISS/embeddings became local BM25; the initial single mini model became a more costly draft/check pair. Data became 30 development cases and separate 20-case external batches rather than the planned 200. The test is clause-level, so live per-agreement cost and real contract task completion have not been demonstrated. Automatic clause boundaries are provisional. A fully new generator or blind-review transcript cannot be retroactively invented for the old synthetic corpus.

## Release criteria

The completed engineering checks support a local classroom demo and reproducible failure analysis. The one additional authorized paid v17 regression completed for US$0.2722430. Its 5/5 precision and 0/4 unsafe rate do not establish independent reliability: recall is 5/14 and substantive citation support only 2/6 on an assistant first pass. The 95% citation goal remains unmet. Both exact-byte freezes, inputs, labels, responses and audits are preserved; interface-only result display updates do not change their evaluated predictor code. Genuine generalization requires new independent cases and pre-locked labels, after substantive reasoning improves. No further paid run is scheduled. Future runs need fresh authorization and a separate freeze, including errors and abstentions, not overwritten results.
