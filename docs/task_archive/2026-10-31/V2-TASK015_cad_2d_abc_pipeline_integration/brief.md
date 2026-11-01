# V2-TASK015 CAD 2D A/B/C pipeline integration

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_workflow_lead`, `data_contract_engineer`, downstream
  asset/KG consumer owner, independent `data_quality_reviewer`
- Decision state: `frozen`
- Source/candidate version: S's cleaned July 2026 CAD 2D A/B/C handoff;
  historical `feature/material-layer` drawing subset as comparison input
- Dependencies: governed CAD/drawing inventory and source eligibility; explicit
  bounded permission before approved local drawing or classification content is
  read
- Downstream consumers: drawing index, material/asset joins, Route A asset KG
  candidate, project-owner output consumer, and `V2-TASK016`

## Goal

Selectively integrate the canonical dry-run-first CAD 2D A/B/C pipeline from
S's cleaned handoff, including BOM audit and relationship-output stages omitted
from `feature/material-layer`, while adapting it to current v2 governance,
contracts, manifests, and task boundaries.

## Background

S's branch integrated a smaller modular subset covering classification merge,
title extraction, drawing-index support, and ASM BOM extraction. The cleaned
handoff declares a complete A/B/C pipeline canonical and adds text/vector
diagnostics, BOM audit, manual-override governance, ASM/PRT relationship
construction, final project-owner output, and Tasks 044-045. Historical
`TASK-*` records and code are reference inputs, not active v2 task authority.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- current CAD extraction contract and runbook named during implementation
- S's cleaned CAD handoff manifest, runbook, A/B/C scripts, task records, and
  synthetic tests from the user-provided local package
- `origin/feature/material-layer` drawing subset for compatibility comparison

Before inspecting approved drawings or any file content under `data/`, obtain
explicit permission for the exact bounded paths. Do not send drawing text or
business identifiers to external services.

## Scope

- Establish one canonical current-v2 implementation for A01 classification
  merge, A02 field extraction, A03 drawing index, B01 ASM BOM extraction, B02
  audit, C01 relationships, and C02 final governed output.
- Retain T00/T01 as local diagnostic tools with explicit approved-sample gates.
- Preserve preview-before-write behavior and configuration-driven coordinates,
  thresholds, keywords, suffix normalization, and template profiles.
- Preserve classification authority, empty-value missingness, field-only-key
  exclusions, and explicit audit counts.
- Govern manual BOM and audit overrides with source anchors, reviewer, reason,
  decision state, and immutable generated outputs.
- Block C01/C02 promotion when unresolved high-priority B02 findings remain.
- Generate deterministic intermediate/final candidates, exclusions, audits,
  lineage, and run manifests.
- Add synthetic and contract-compatibility tests before local PDF validation.
- Prepare a frozen candidate/evidence handoff for `V2-TASK016`.

## Non-goals

- No blind cherry-pick or whole-branch merge from `feature/material-layer`.
- No reuse of the retired spreadsheet governance store or historical task IDs.
- No raw/unmasked PDF, classification, title, project, part, BOM, relationship,
  or generated-output content committed to Git.
- No OCR/external-model processing without a separately approved governed path.
- No invention of missing BOM rows, relationships, titles, projects, or drawing
  types.
- No graph activation, project-owner contract release, or Data RC claim.

## Write set

Initial synthetic implementation writes are limited to:

- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/`
- `configs/pipelines/cad_2d_pipeline_v2.yaml`
- `services/ingestion/cad_2d_pipeline_v2/`
- `scripts/pipelines/cad_2d_v2/`
- `tests/unit/cad_2d_v2/`

No real `data/` input/output paths are authorized by task creation. Exact
governed paths must be recorded after explicit permission and before use.

## Failure behavior and rollback

- Each stage validates its declared input contract and fails nonzero on unsafe,
  contradictory, duplicate, or structurally invalid input.
- Reviewable uncertainty is emitted with reason codes and never silently
  promoted downstream.
- The new v2 path remains separate until validated; rollback leaves the current
  graph and existing CAD pipeline unchanged.

## Deliverables

- [ ] canonical current-v2 A01-A03, B01-B02, and C01-C02 pipeline
- [ ] governed diagnostic tools and manual-override contracts
- [ ] controlled configuration, exact commands, and preview/write gates
- [ ] deterministic candidates, exclusions, audits, lineage, and manifests
- [ ] synthetic, compatibility, determinism, and negative tests
- [ ] local approved-sample validation evidence after permission
- [ ] independent-review handoff to `V2-TASK016`
- [ ] exact changed files, validation, risks, and state in `notes.md`
