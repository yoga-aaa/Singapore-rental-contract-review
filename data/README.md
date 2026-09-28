# Data protocol

## External cases

`external_cases_raw.csv` is the verbatim set of 20 externally authored cases received on 28 September 2026. Treat it as immutable input.

Before running the final evaluation, create a separate ground-truth file containing the label and expected reference source for each case. Do this once, before the system is tested on these cases. Do not use the external cases to tune prompts, retrieval settings, rules, or thresholds.

## Important quality note

Several raw clauses include meta-commentary such as "the clause does not state" or "the Tenant may wish to ask". Those sentences reveal likely review concerns and would make the system's task easier than a real contract. Preserve this raw file for provenance, but prepare a separately documented, sanitized blind-evaluation copy before final scoring. The sanitized copy must retain the original substantive contractual terms while removing only editorial commentary.

## Data restrictions

Do not commit real tenancy agreements or personal data. Reference sources must be recorded by URL and retrieval date; do not redistribute source documents unless their licences permit it.

