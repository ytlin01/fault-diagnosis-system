# V2-TASK003 notes

## 2026-07-23 — planned

### Plan

- Preserve the established Route B evidence/policy separation for DEKG.
- Track the governed handoff as non-node `DEKGEvidenceRecord` rather than
  replacing removed Schema 4.1 `DocumentAsset` with another graph node.
- Use `full_document` by default. Use `evidence_residual` only when anchored
  table content is selected for TPDX, and exclude those table anchors from the
  DEKG record set.
- Use an analogous case/policy separation for FHKB.
- Draft contracts only; do not modify runtime, pipelines, governance records,
  active v2/v1 contracts, or files under `data/`.

### Changed files

- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/brief.md`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/acceptance.md`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/notes.md`
- `contracts/evidence/dekg_evidence_v2.json`
- `contracts/policy/dekg_validation_policy_v2.json`
- `contracts/case/fhkb_case_v1.json`
- `contracts/policy/fhkb_validation_policy_v1.json`
- `tests/unit/test_dekg_fhkb_contracts.py`

### Validation

- Confirmed branch: `feature/v2-data-pipeline`.
- Confirmed `V2-TASK003` was unused before task creation.
- Reviewed TASK-017, TASK-035, and TASK-042 boundaries.
- Reviewed the Route B evidence/policy v1 and v2 historical pair before its
  files were deleted in the worktree, plus Route C source boundary v1, TPDX
  Schema 4.1, and affected Route B/Route C consumer code.
- `python -m json.tool` passed for all four new contract artifacts.
- `python -m unittest tests.unit.test_dekg_fhkb_contracts` passed: 9 tests.
- `python scripts/check_workflow_guard.py` with the scoped changed-file list
  passed: no protected workflow files changed.
- Synthetic DEKG failures cover unsafe fields, diagnosis promotion, missing
  anchors, full-document records that declare TPDX extraction, residual mode
  without a partition decision, non-table TPDX extraction, re-emission of an
  excluded table anchor, TPDX overlap, and invalid co-source corroboration.
- Synthetic DEKG success covers both full-document and table-partitioned
  evidence-residual modes.
- Synthetic success covers both legacy-compatible structured case candidates
  and governed field-history case candidates.
- No file under `data/` was opened or read.

### Risks

- The historical Route B v2 pair references deleted Schema 4.0 artifacts and
  treats `DocumentAsset` as publishable. Its four tracked v1/v2 files are now
  deleted in the worktree by a change outside V2-TASK003; this task did not
  restore or modify those paths.
- TPDX Schema 4.1 intentionally contains no `DocumentAsset`.
- Route C currently uses `route_target=rag_case_pool` on producer records while
  mapping that marker to the `case_retrieval` consumer capability.
- Concrete source registration, sensitivity, masking, governed location, and
  release IDs remain source-specific governance work outside this contract
  proposal.
- Runtime code still names the deleted Route B v2 pair, so Route B runtime
  compatibility is currently unresolved. The proposals deliberately do not change
  runtime binding; Route C remains on source boundary v1.
- The DEKG migration from `published_graph/DocumentAsset` to
  `accepted_evidence/DEKGEvidenceRecord` is breaking and requires
  affected-consumer review plus old/new validation before implementation.
- A downstream DEKG graph/index representation needs a separate derivation
  contract that retains `evidence_id`; this task does not freeze graph shapes.
- Residual partitioning depends on stable table anchors and an explicit TPDX
  selection decision; extraction success alone does not imply reviewed or
  published TPDX status.

### Next gate

- Workflow lead reviews the source-agnostic governance boundary.
- Affected Route B/Route C consumers review compatibility and migration.
- Obtain workflow-lead and affected-consumer approval before promoting the
  artifacts to `FROZEN` or binding runtime consumers.

### State

Task implementation and synthetic validation: `validated`.

Contract decision state: `REVIEWED_PROPOSAL`.

## 2026-07-23 — adapter implementation planned

### Plan

- Replace the FHKB envelope-only record definition with a closed, executable
  canonical case schema.
- Derive canonical `case_id` from governed source identity and emit no legacy
  identifier alias.
- Add an executable DEKG evidence schema matching the existing two-mode
  contract.
- Implement offline, side-effect-free FHKB and DEKG legacy adapters. They do
  not read governance state, scan directories, bind runtime consumers, or
  promote records.
- Validate only with synthetic fixtures; do not inspect files under `data/`.

### Boundaries

- The user authorized implementation of the FHKB case contract and both legacy
  adapters.
- Contract decision state is `REVIEWED_PROPOSAL`; the adapter outputs are candidate
  implementation evidence, not a runtime migration or release.
- Runtime retrieval modules and Route B/Route C bindings remain outside the
  write set.

## 2026-07-23 — implemented and validated

### Implemented

- Added a closed Draft 2020-12 FHKB package schema. Canonical `case_id` is
  derived from governed source identity; no legacy identifier alias is emitted.
- Mapped both current legacy producer types:
  `field_case_without_standard_fp` and
  `nomic_semantic_related_candidate`.
- Converted the legacy `SourceRef` record-index shape into deterministic
  `FHS_` record IDs while retaining all original reference fields.
- Preserved `relation_type`, `filter_basis.reason`, and
  `filter_basis.not_for_kg_text2cypher` as typed legacy context.
- Added a closed Draft 2020-12 DEKG package schema.
- Added side-effect-free FHKB and DEKG adapters. The DEKG adapter defaults to
  full-document mode and excludes only explicitly selected table anchors in
  evidence-residual mode.

### Changed files

- `contracts/case/fhkb_case_v1.json`
- `contracts/case/fhkb_case_v1.schema.json`
- `contracts/evidence/dekg_evidence_v2.json`
- `contracts/evidence/dekg_evidence_v2.schema.json`
- `contracts/policy/fhkb_validation_policy_v1.json`
- `contracts/policy/dekg_validation_policy_v2.json`
- `services/ingestion/fhkb_legacy_adapter.py`
- `services/ingestion/dekg_legacy_adapter.py`
- `tests/unit/test_dekg_fhkb_contracts.py`
- `tests/unit/test_dekg_fhkb_legacy_adapters.py`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/brief.md`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/acceptance.md`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/notes.md`

### Validation

- `python -m unittest tests.unit.test_dekg_fhkb_contracts
  tests.unit.test_dekg_fhkb_legacy_adapters`: 16 tests passed.
- All six contract, policy, and schema JSON files parsed successfully.
- Both adapter modules and both test modules passed Python AST syntax parsing.
- `scripts/check_workflow_guard.py` passed for the exact V2-TASK003 write set.
- `git diff --check` passed for tracked V2-TASK003 changes.
- Synthetic failures cover promotion fields, wrong route markers, ambiguous
  source references, conflicting canonical identities, unsafe DEKG content,
  non-table/unknown partitions, partition metadata in full-document mode, and
  residual partitions with no remaining evidence.
- A broader pre-existing Route C test command was attempted once and excluded
  from evidence: two tests tried to open missing `data/eval` fixtures and
  failed with `FileNotFoundError` before file contents could be opened. No
  `data/` content was inspected.

### Risks

- The active Python environment does not provide `jsonschema` or another
  Draft 2020-12 validator. The schemas declare the correct dialect, parse, use
  closed shapes, and are covered by generated-output invariant tests, but an
  independent metaschema check remains open.
- The contracts and adapters remain `REVIEWED_PROPOSAL` and offline. Runtime binding,
  governed source registration, masking execution, approved real-package
  validation, and consumer migration review remain future gates.
- Legacy source-reference IDs depend on the legacy source name and record
  position/value tuple. Reordering legacy records changes identity unless the
  legacy reference tuple remains unchanged.

### State

Adapter implementation and synthetic validation: `validated`.

Contract decision state: `REVIEWED_PROPOSAL`.

## 2026-07-23 — reviewed-proposal cleanup

### Implemented

- Removed the legacy identifier alias from the FHKB canonical schema, contract,
  adapter output, validation policy, and tests.
- Legacy input may still contain its producer identifier, but the adapter
  discards it and derives `case_id` exclusively from governed source identity.
- Set all four V2-TASK003 contract/policy artifacts to
  `REVIEWED_PROPOSAL` version `1.0`.

### Boundaries

- Runtime binding remains unauthorized pending `FROZEN` approval.
- No artifact claims frozen, released, or deployed status.

### Pending review and freeze gate

- Waiting for N's review.
- After N confirms that the corresponding system contracts on her side are
  acceptable and aligned, the DEKG/FHKB contracts, schemas, and validation
  policies can be promoted from `REVIEWED_PROPOSAL` to `FROZEN`.
- Until that confirmation is recorded, the artifacts remain
  `REVIEWED_PROPOSAL` and runtime binding remains unauthorized.

## 2026-07-23 — DEKG v2 and contract freeze

### Implemented

- Renamed the DEKG contract package to `dekg_evidence_v2`, including its
  executable schema and validation policy.
- The v2 contract explicitly supersedes `route_b_evidence_v2`; it is not a v1
  wrapper around that contract.
- Retained and made explicit the `full_document` default and conditional
  `evidence_residual` mode for table content selected for TPDX.
- Updated the offline adapter and synthetic tests to emit and validate the v2
  schema identity.
- N confirmed the corresponding system contracts; DEKG, FHKB, and TPDX Schema
  4.1 contract artifacts are frozen. Runtime activation remains separate.

### State

Contract decision state: `FROZEN`.