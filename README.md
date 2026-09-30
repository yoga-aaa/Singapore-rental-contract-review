# Singapore Rental Contract Review

An individual PE6201 project that compares a selected clause from a text-readable Singapore residential tenancy agreement with the relevant CEA reference material.

## Scope

The MVP supports English, text-readable PDF tenancy agreements for either HDB flats or private residential properties. It returns one of three outcomes for a selected clause:

- `review_required`
- `no_material_difference_found`
- `insufficient_evidence`

Every non-abstaining result must cite a retrieved source passage. The system is a reference-comparison tool, not legal advice or a recommendation to sign a contract.

## Repository status

Project foundation and the first 30-case development evaluation are complete. See [the development error audit](docs/development_error_audit.md) for the corrected metrics and open citation/label questions. The external cases supplied by an independent author are preserved in `data/external_cases_raw.csv` and must not be used for prompt tuning or rule changes.

## Planned structure

- `src/` - application, retrieval, baseline, guardrail, and evaluation modules.
- `data/` - source registry, development data, and locked external cases.
- `scripts/` - reproducible source-download and evaluation commands.
- `tests/` - automated tests.
- `results/` - generated evaluation outputs; excluded from version control except `.gitkeep`.

## Safety boundary

The project will use only synthetic cases for development. It will not upload real contracts, personal data, NRIC/passport numbers, addresses, signatures, or chat logs to a model API.

