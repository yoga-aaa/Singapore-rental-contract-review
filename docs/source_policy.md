# Source policy

## Purpose

The MVP compares a selected tenancy-agreement clause with a small, versioned set of official CEA reference documents. It does not determine legal validity, fairness, enforceability, or whether a tenant should sign.

## Included sources

The source registry contains four CEA documents: one tenancy-agreement template and one tenant checklist for each supported housing type, HDB and Private Residential. The templates support clause comparison. The checklists support tenant due-diligence guidance and must not be cited as if they impose a contractual term.

## Versioning and reproducibility

`data/source_registry.csv` is the authority for source identifiers, URLs, versions, update dates, and retrieval dates. `scripts/download_sources.py` downloads the current registered documents into `data/source_documents/`, which is deliberately excluded from Git. This repository stores URLs and metadata rather than redistributing government documents.

Before labelling the external evaluation set, do not add, remove, or replace a registered source. If a source must change, record the reason and create a new registry version before any final evaluation is run.

## Citation rule

Every non-abstaining system result must identify a `source_id` and source section that exist in the registry. If no relevant source can be retrieved, the correct behaviour is `insufficient_evidence`.
