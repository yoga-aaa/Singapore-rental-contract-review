# Data protocol

## External cases

`external_cases_raw.csv` is the verbatim set of 20 externally authored cases received on 28 September 2026. Treat it as immutable input.

An assistant-authored `external_cases_ground_truth.csv` was committed as a provisional v0 proposal before any external model run. It was disputed after the product goal was clarified and is **not** independently reviewed ground truth. On 3 October the user reported that human review agreed with all v0 labels. `external_cases_ground_truth.reviewed.csv` locks those reported labels before model prediction, while `external_review_provenance.json` records that no independently annotated file or per-case rationale was supplied. Do not overstate this as independently auditable adjudication, and do not use external predictions to tune prompts, retrieval settings, rules or thresholds.

## Subsequent evaluation status

The instruction above describes the original holdout intention. After diagnosis and repairs, those twenty cases became exposed regression material; do not claim independent generalization from later results. The newer DeepSeek-authored and separately AI-reviewed set is outside this public repository. Its unchanged pre-prediction labels and original v16 results are preserved, followed by a separately frozen paid v17 regression on the same exposed inputs. It is not expert-blind gold. See `docs/regression_evaluation_v17.md`; do not pool versions or datasets.

The thirty development clauses are synthetic and repeatedly tuned. A complete original generation conversation is unavailable, so no retrospective “unseen” generation recipe is claimed. Five new demo fixtures are declared in `demo_examples.json`: short, manually selected synthetic variants representing a clear adverse termination, rent/utility equivalence, vague evidence, private notice delivery and an unresolved pet-repair arrangement. Their PDF text is the fixture clause with a numbered synthetic housing prefix, using ReportLab. Expected outputs are declared in `scripts/check_product.py`. These reused functional demos are not randomized cases or a statistical accuracy benchmark.

## Important quality note

Several raw clauses include meta-commentary such as "the clause does not state" or "the Tenant may wish to ask". Those sentences reveal likely review concerns and would make the system's task easier than a real contract. Preserve this raw file for provenance, but prepare a separately documented, sanitized blind-evaluation copy before final scoring. The sanitized copy must retain the original substantive contractual terms while removing only editorial commentary.

## Data restrictions

Do not commit real tenancy agreements or personal data. Reference sources must be recorded by URL and retrieval date; do not redistribute source documents unless their licences permit it.
