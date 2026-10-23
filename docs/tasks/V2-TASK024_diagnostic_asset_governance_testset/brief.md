# V2-TASK024 Diagnostic-asset governance plan and synthetic test set

## Identity

- Owner: `data_workflow_lead` with `data_contract_engineer` and independent
  `data_quality_reviewer` review
- Decision state: `planned`
- Source evidence: `legacy/data/docs/diagnostic_asset_bridge_data_issues.pdf`
  and `legacy/data/docs/cad_kg_query_results_v1.pdf`
- Contract target: frozen TPDX KG Schema 4.2; CAD KG Schema v3.2 and legacy
  `TRIGGERS`/`HAS_STEP` vocabulary are historical compatibility evidence only
- Downstream consumers: Tasks 019-023, governed Route A candidate review, and
  the Schema 4.2 validation-query registry

## Goal

Convert the two historical reports into a reviewable data-governance baseline
and a machine-readable synthetic test set. Preserve the reports as evidence,
but do not promote their graph counts, mappings, query screenshots, or legacy
relationships to reviewed production truth.

## Scope

- source registration, lineage, sensitivity, masking, and serving decisions;
- CAD topology identity, alias matching, collision handling, and review queues;
- diagnostic-to-asset mapping, `MappingRecord` authority, and Route A gates;
- 5M1E coverage gaps and Layer B acquisition backlog;
- BOM version normalization, quantity discrepancy handling, and exclusions;
- graph structural checks and migration from historical query vocabulary;
- deterministic, leakage-safe synthetic tests for governance, contract,
  pipeline, graph, query, provenance, and safety behavior.

## Non-goals

- no raw-data import, masking-log mutation, Neo4j mutation, or runtime change;
- no modification of `Faultdx_ref/` or legacy source PDFs;
- no automatic promotion of `mapped`, extracted, similar, or historical records;
- no final Data RC recommendation or global release decision;
- no replacement of the frozen Schema 4.2 contract.

## Write set

- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/brief.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/acceptance.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/notes.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/data_governance_plan.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/test_set_v1.jsonl`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/test_set_v1.md`

All fixtures are synthetic and contain no copied source records, raw device
logs, customer data, credentials, or unmasked work orders.

## Required handoff

The governance plan is a `DRAFT` proposal. Before implementation or real-data
validation, the workflow lead must record exact source registrations, versions,
sensitivity and masking states, serving eligibility, reviewers, promotion
decisions, and bounded content permission. The independent quality reviewer
must review the test applicability and labels separately from any candidate
implementation.
