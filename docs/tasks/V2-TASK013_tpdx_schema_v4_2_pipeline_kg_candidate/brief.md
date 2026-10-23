# V2-TASK013 TPDX Schema 4.2 pipeline and KG candidate

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_workflow_lead`, `data_contract_engineer`, affected
  Text2Cypher/evaluation consumer owner, independent `data_quality_reviewer`
- Decision state: `implemented`
- Source/candidate version: frozen `tpdx_kg_schema_v4_1` rollback baseline;
  frozen `tpdx_kg_schema_v4_2` implementation target
- Dependencies: `V2-TASK012` frozen contract pair and affected-consumer
  compatibility approval; explicit bounded data-content permission before any
  real-data read
- Downstream consumers: Route A diagnostic ingestion, Neo4j graph-import
  boundary, Text2Cypher compatibility tests, Route A old/new evaluation, and
  independent Data RC review

## Goal

Implement a deterministic, rerunnable Schema 4.2 migration and graph-candidate
path that preserves `MappingRecord` authority, emits only explicitly backed
diagnostic-chain assertions, and produces validation, exclusion, manifest, and
rollback evidence for independent review.

## Background

`V2-TASK012` produced the frozen Schema 4.2 contract and semantic validator.
The branch-owned migration/import implementation is separate from current graph
loaders, Text2Cypher templates, and Route A evaluation, which still contain
legacy `Fault`, `INDICATES`, `RESOLVED_BY`, and `HAS_STEP` vocabulary. Schema
4.2 is frozen but not runtime-active.

The initial implementation and validation phase uses synthetic fixtures only.
Real TPDX data is not an input until the user grants explicit permission for a
bounded path and the workflow lead confirms the governed input/output zones.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/brief.md`
- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/acceptance.md`
- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/notes.md`
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_2.md`
- `contracts/schema/tpdx_kg_schema_v4_1.schema.json` as the unchanged rollback
  baseline and old/new comparison input; it is not a Schema 4.2 `$ref` or
  packaging dependency
- `services/governance/tpdx_schema_v4_2.py`
- affected non-data loaders, import boundaries, tests, and evaluation/query
  consumers identified by repository search

Before inspecting the contents of any file under `data/`, ask the user for
explicit permission for the intended path or bounded scope. This includes
indirect reads through scripts, tests, validators, or other tools.

## Scope

- Implement a deterministic Schema 4.1-to-4.2 migration adapter for valid,
  governed diagnostic records.
- Generate `HAS_CODE`, `HAS_CAUSE`, `HAS_ACTION`, and `HAS_STEPS` assertion
  projections with deterministic `assertion_edge_id` values and one backing
  `mapping_record_id` each.
- Require explicit reviewed Cause-to-Action pairs with a non-empty
  `cause_action_pair_id`; never infer a Cartesian product from independent
  cause and action memberships.
- Convert valid `HAS_STEP` membership to `HAS_STEPS` only when a unique valid
  MappingRecord backing can be established.
- Fail closed or emit governed exclusions for ambiguous, contradictory,
  duplicate, unbacked, unreviewed, or non-serving-safe records.
- Produce deterministic candidate, exclusion, lineage, and run-manifest
  outputs with input/config/schema fingerprints.
- Preserve the Schema 4.1 graph and provide an explicit rollback path.
- Add synthetic contract, migration, graph-shape, rerun-determinism, negative
  provenance, and consumer-compatibility tests.
- Prepare the candidate and evidence handoff for independent old/new KG review.

## Non-goals

- No change to the Schema 4.2 contract, identifiers, relationship authority,
  or frozen Schema 4.1 artifacts.
- No real-data read or graph build before explicit bounded permission and
  governed-zone confirmation.
- No inference of missing causes, actions, Cause-to-Action pairs, steps, or
  review state.
- No modification of Text2Cypher runtime behavior, prompts, routing, providers,
  UI, deployment, or release packaging on this branch.
- No incidental update of the frozen DEKG contract's Schema 4.1 reference.
- No contract freeze, runtime activation, release, or Data RC readiness claim.
- No modification of the legacy loader until compatibility and rollback tests
  prove the replacement boundary; prefer a separate Schema 4.2 path.

## Write set

Initial synthetic implementation writes are limited to:

- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/`
- `services/ingestion/tpdx_schema_v4_2_migration.py`
- `services/graph/tpdx_schema_v4_2_import.py`
- `scripts/build_graph/build_tpdx_schema_v4_2_candidate.py`
- `tests/unit/test_tpdx_schema_v4_2_migration.py`
- `tests/services/graph/test_tpdx_schema_v4_2_import.py`

No `data/` output path is authorized by this planned task. After bounded
data-content permission and governance-zone confirmation, the workflow lead
must record the exact governed input and output paths in this package before
the owner reads or writes real payloads.

## Commands and failure behavior

The implementation must expose exact non-interactive commands for candidate
construction and validation. Commands must accept explicit input, output,
schema, and manifest paths; they must not rely on private absolute paths or
implicit environment state.

Any schema, semantic, review-state, serving-safety, provenance, pairing,
identity, step-order, or rerun-determinism failure must produce a nonzero exit
or an explicit governed exclusion. Partial success must never be presented as a
complete graph candidate.

## Rollback

- Keep frozen Schema 4.1 and the existing graph unchanged.
- Build Schema 4.2 into a separate candidate/import boundary.
- Do not publish `HAS_STEP` and `HAS_STEPS` as parallel truth relationships.
- Activation, when separately authorized, must have a recorded switch-back to
  the validated Schema 4.1 graph and consumer configuration.

## Constraints

- Preserve existing user changes and mixed-worktree safety.
- Do not inspect `data/` file contents without explicit user permission.
- Do not modify `Faultdx_ref/`.
- Do not send unapproved data to external services.
- Preserve Route A/B/C meaning and `Phenomenon`/`MappingRecord` provenance.
- Validate and package the self-contained Schema 4.2 JSON contract directly.
  Retain Schema 4.1 only as the immutable rollback and old/new comparison
  baseline.
- Do not turn a proposal, candidate, or future milestone into a completion
  claim.

## Deliverables

- [ ] deterministic Schema 4.2 migration and candidate builder
- [ ] contract-valid graph-import boundary
- [ ] candidate, exclusion, lineage, and run-manifest formats
- [ ] exact commands and rollback procedure
- [ ] synthetic positive, negative, rerun, and compatibility tests
- [ ] exact changed files and validation evidence
- [ ] risks, exclusions, open decisions, and independent-review handoff
- [ ] `notes.md` updated through each actual state transition

## Next gate

The synthetic-only implementation is validated. Real data work waits for
explicit bounded permission and governed input/output zones. The candidate and
evidence package now go to the independent `data_quality_reviewer` for old/new
KG evaluation and a release recommendation; runtime activation and Data RC
remain separate decisions.
