# V2-TASK013 notes

## 2026-07-31 - planned

### Plan

- Use Schema 4.2 `REVIEWED_PROPOSAL` as the implementation target while
  preserving frozen Schema 4.1 as the rollback baseline.
- Implement a separate deterministic migration and graph-candidate boundary
  before considering changes to the legacy loader.
- Preserve `MappingRecord` authority and require explicit reviewed
  Cause-to-Action pairs.
- Start with synthetic fixtures only and stop before all real-data reads until
  the user grants bounded permission and governed zones are recorded.
- Hand a validated candidate, manifest, exclusions, and rollback evidence to an
  independent quality reviewer; do not claim freeze or runtime activation.

### Approval and ownership

- The user approved Schema 4.2 relationship naming and migration compatibility
  on 2026-07-31.
- The user approved assignment of branch-owned pipeline and KG implementation
  to `data_pipeline_kg_engineer`.
- Runtime/Text2Cypher implementation remains outside this branch task, but its
  compatibility tests are a required gate.

### Changed files

- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/acceptance.md`
- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/notes.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/brief.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/acceptance.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/notes.md`

### Validation

- Confirmed the active branch is `feature/v2-data-pipeline` and preserved the
  existing mixed worktree.
- Confirmed task directories `V2-TASK001` through `V2-TASK012` exist and
  `V2-TASK013` was unused on disk before allocation.
- Read the durable workflow, `data_pipeline_kg_engineer` role guide, and active
  task template before creating the package.
- Recorded a synthetic-only initial write set, explicit failure behavior,
  rollback, reviewers, and next gate.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.

### Risks

- Schema 4.2 is not frozen. Implementation must continue to identify its
  artifacts as candidates and retain the Schema 4.1 rollback boundary.
- Schema 4.2 is self-contained for validation and packaging. Schema 4.1 remains
  the immutable rollback and old/new comparison baseline, not a runtime
  dependency.
- Multiple causes and actions cannot be migrated safely without explicit
  reviewed pairing input.
- Legacy loader, Text2Cypher, and evaluation vocabulary remains incompatible
  until separately migrated and validated.
- Real-data paths and governance zones remain intentionally unspecified until
  explicit bounded data-content permission is received.
- The Task 012 notes reference
  `contracts/schema/tpdx_kg_schema_v4_2_change_proposal.md`, but that file was
  not present on disk during Task 013 creation and remains a handoff integrity
  issue outside this task's write set.

### State

Task decision state: `planned`.

## 2026-08-01 - Schema 4.2 contract handoff correction

### Planned

- Treat Schema 4.2 as self-contained for validation and packaging.
- Retain frozen Schema 4.1 solely as rollback and old/new comparison evidence.
- Require `cause_action_pair_id` in addition to MappingRecord-backed
  projections, and report the paired-KG comparison outcome categories.

### Changed files

- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/brief.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/acceptance.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/notes.md`

### Boundaries

- This is contract-handoff planning only. No pipeline, graph, runtime, data, or
  candidate artifact was implemented or validated.

### State

Task decision state: `planned`.

## 2026-08-10 - synthetic migration and import boundary implemented

### Plan

- Consume the now-frozen Schema 4.2 contract directly while preserving Schema
  4.1 as the rollback/comparison baseline.
- Implement a deterministic synthetic-only migration, candidate builder, and
  graph-import plan with explicit reviewed pairing input.
- Fail closed or emit governed exclusions for ambiguous, unsafe, duplicate, or
  unbacked records; never infer Cause-to-Action Cartesian products.

### Implemented

- Added `services/ingestion/tpdx_schema_v4_2_migration.py` with deterministic
  Schema 4.1-to-4.2 projection generation, explicit pairing validation,
  `HAS_STEP` to `HAS_STEPS` conversion only with unique MappingRecord backing,
  exclusions, lineage, and stable JSON fingerprints.
- Added `scripts/build_graph/build_tpdx_schema_v4_2_candidate.py` with explicit
  input, pairing, config, schema, rollback, candidate, exclusion, lineage, and
  manifest paths. The default is fail-closed; `--allow-exclusions` produces a
  non-complete review candidate only.
- Added `services/graph/tpdx_schema_v4_2_import.py` with frozen-contract
  validation, idempotent import planning, in-memory application for tests, and
  conflict rejection for independent MappingRecord-backed assertions.
- Added synthetic migration and import tests covering positive chains,
  explicit pairing, no-Cartesian behavior, unsafe/ambiguous exclusions,
  determinism, schema validation, idempotency, legacy `HAS_STEP` rejection, and
  contract-status enforcement.

### Changed files

- `services/ingestion/tpdx_schema_v4_2_migration.py`
- `services/graph/tpdx_schema_v4_2_import.py`
- `scripts/build_graph/build_tpdx_schema_v4_2_candidate.py`
- `tests/unit/test_tpdx_schema_v4_2_migration.py`
- `tests/services/graph/test_tpdx_schema_v4_2_import.py`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/brief.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/acceptance.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/notes.md`

### Validation

- `python -m py_compile services/ingestion/tpdx_schema_v4_2_migration.py services/graph/tpdx_schema_v4_2_import.py scripts/build_graph/build_tpdx_schema_v4_2_candidate.py tests/unit/test_tpdx_schema_v4_2_migration.py tests/services/graph/test_tpdx_schema_v4_2_import.py` passed.
- `python -m unittest tests.unit.test_tpdx_schema_v4_2_migration tests.services.graph.test_tpdx_schema_v4_2_import` passed: 13 tests, zero skips.
- `python -m unittest tests.services.graph.test_text2cypher tests.services.graph.test_text2cypher_diagnostic tests.services.graph.test_text2cypher_templates tests.unit.test_route_a_static_coverage` passed: 14 synthetic tests, zero skips. Repository inspection confirms the current Text2Cypher templates, legacy diagnostic loader, and Route A static-coverage fixtures still use legacy `Fault`/`INDICATES`/`RESOLVED_BY`/`HAS_STEP` vocabulary; this is a migration-gap finding, not compatibility approval.
- The candidate builder was exercised through the synthetic test with frozen
  Schema 4.2 and Schema 4.1 rollback schemas; repeated output was byte-stable.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.

### Risks and next gate

- No real TPDX input/output paths are authorized or recorded; the candidate is
  synthetic-only and not serving-safe or release-eligible evidence.
- Legacy loader, Text2Cypher, Route A evaluation, and old/new KG comparison
  migrations remain open and require affected-consumer and quality review.
- The synthetic candidate is implemented and validated, but has not been
  independently reviewed, frozen as a data candidate, imported, released, or
  promoted.

### State

Task decision state: `implemented`.

Synthetic implementation: `validated`.

Data candidate and independent review: `planned`.
