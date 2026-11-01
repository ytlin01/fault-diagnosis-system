# V2-TASK006_phase2_masking_identity

## Identity

- Owner: `data_contract_engineer`
- Reviewer: `data_workflow_lead`
- Decision state: `reviewed_proposal`
- Affected consumers: structured and unstructured masking configuration loaders

## Goal

Correct the active masking configuration and ingestion package identity so they
describe the v2 data line while preserving the inherited Phase 1 method
provenance and existing masking-rules revision semantics.

## Scope

- State the active program lifecycle as Phase 2 / v2 data line.
- Keep top-level `version: 2` as the existing masking-rules revision.
- Correct the documented canonical and serving-candidate zone paths.
- State that masking success does not grant serving, Route A truth, KG, or gold
  eligibility.
- Update the active ingestion package description consistently.

## Non-goals

- No source-rule, masking-action, classification, loader, manifest, lineage, or
  governance-log behavior changes.
- No rewriting of historical Phase 1 provenance or append-only records.
- No inspection or modification of file contents under `data/`.
- No serving, route, KG, gold, review, Data RC, or release decision.

## Write set

- `configs/masking_rules.yaml`, limited to introductory comments and additive
  program-identity metadata.
- `services/ingestion/__init__.py`, limited to the package description.
- This task package.

## Compatibility and rollback

The change is additive. Existing consumers continue reading top-level
`version: 2`; unknown `program_identity` metadata is ignored. Rollback removes
the additive metadata and restores the descriptions without touching source
rules, historical manifests, or governance logs.
