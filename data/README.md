# Data protocol

## External cases

`external_cases_raw.csv` is the verbatim set of 20 externally authored cases received on 28 September 2026. Treat it as immutable input.

An assistant-authored `external_cases_ground_truth.csv` was committed as a provisional v0 proposal before any external model run. It was disputed after the product goal was clarified and is **not** independently reviewed ground truth. On 3 October the user reported that human review agreed with all v0 labels. `external_cases_ground_truth.reviewed.csv` locks those reported labels before model prediction, while `external_review_provenance.json` records that no independently annotated file or per-case rationale was supplied. Do not overstate this as independently auditable adjudication, and do not use external predictions to tune prompts, retrieval settings, rules or thresholds.

## Important quality note

Several raw clauses include meta-commentary such as "the clause does not state" or "the Tenant may wish to ask". Those sentences reveal likely review concerns and would make the system's task easier than a real contract. Preserve this raw file for provenance, but prepare a separately documented, sanitized blind-evaluation copy before final scoring. The sanitized copy must retain the original substantive contractual terms while removing only editorial commentary.

## Data restrictions

Do not commit real tenancy agreements or personal data. Reference sources must be recorded by URL and retrieval date; do not redistribute source documents unless their licences permit it.
