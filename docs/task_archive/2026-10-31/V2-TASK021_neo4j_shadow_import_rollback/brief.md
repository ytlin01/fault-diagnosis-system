# V2-TASK021 Neo4j shadow import and rollback

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_contract_engineer`, `data_workflow_lead`, independent
  `data_quality_reviewer`, and the authorized Neo4j operations owner
- Decision state: `planned`
- Source/candidate version: accepted Schema 4.2 `tpdx_release` package from
  `V2-TASK020`; existing Schema 4.1 database retained as rollback baseline
- Dependencies: frozen Schema 4.2; accepted package and validation report from
  `V2-TASK020`; current non-mutating import-plan boundary from `V2-TASK013`;
  approved shadow database identity and credentials; explicit bounded
  permission before package contents are read
- Downstream consumers: `V2-TASK022` query integration tests and
  `V2-TASK023` independent TPDX Data RC review

## Goal

Load one accepted Schema 4.2 TPDX package into a separate Neo4j shadow or
candidate database, verify structural integrity and idempotent reloads, and
provide tested rollback and database-switch instructions without activating
the runtime database.

## Background

`services/graph/tpdx_schema_v4_2_import.py` validates candidates and creates an
in-memory import plan. It deliberately does not connect to Neo4j. This task
adds the separately reviewed database-mutation boundary while retaining the
existing planner and preserving the Schema 4.1 database.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/`
- `docs/tasks/V2-TASK020_tpdx_component_package_producer_validator/`
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_2.md`
- accepted `tpdx_release`, component manifests, validation reports, and exact
  shadow-database configuration

Package data under `data/` may be read only after explicit permission for the
exact bounded package paths. Database authority does not imply that permission.

## Scope

- Preserve the existing non-mutating import planner as a validation boundary.
- Require an allowlisted shadow/candidate database name and refuse the active
  runtime or Schema 4.1 database identity.
- Create Schema 4.2 uniqueness constraints and query-supporting indexes.
- Load only accepted, digest-verified package components.
- Use canonical node IDs and relationship identity that includes
  `mapping_record_id` and `assertion_edge_id` for governed assertion edges.
- Reject orphan nodes, dangling edges, duplicate assertions, identity
  conflicts, contradictory assertions, unbacked projections, invalid endpoint
  labels, and legacy `HAS_STEP`.
- Execute preflight validation before mutation and use a transactional or
  recoverable staged import boundary.
- Verify exact idempotent reloads and reject conflicting reloads.
- Record database identity, package/component digests, importer version,
  constraints/indexes, pre/post counts, label and relationship counts,
  validation results, exclusions, and deterministic graph digests.
- Provide tested create, import, verify, teardown, rollback, and future switch
  instructions. The switch procedure remains documentation only in this task.

## Non-goals

- No modification, deletion, migration in place, or deactivation of the
  existing Schema 4.1 database.
- No runtime database switch, routing change, deployment, or release.
- No unrestricted Cypher endpoint or query adapter implementation.
- No repair or acceptance of invalid source packages during import.

## Write set

Initial synthetic and local-container implementation writes are limited to:

- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/`
- `services/graph/neo4j_tpdx_v4_2_shadow_import.py`
- `scripts/build_graph/import_tpdx_v4_2_shadow.py`
- `docs/runbooks/pipelines/tpdx_v4_2_shadow_import.md`
- `tests/services/graph/test_neo4j_tpdx_v4_2_shadow_import.py`
- `tests/integration/test_tpdx_v4_2_shadow_import.py`

No `data/` output path, database endpoint, credential, or runtime configuration
is authorized by task creation. Exact approved values must be recorded later
without hardcoding secrets or private addresses.

## Failure behavior and rollback

- Package, digest, schema, acceptance, preflight, constraint, transaction, or
  post-import audit failure exits nonzero and cannot mark the import complete.
- The importer refuses an unresolved, active, Schema 4.1, or non-allowlisted
  database target.
- A conflicting reload fails rather than overwriting an assertion.
- Rollback operates only on the explicitly named shadow database and is tested
  without changing the preserved Schema 4.1 database.
- Runtime database switching requires a later system-owned authorization.

## Deliverables

- [ ] Schema 4.2 constraints and indexes
- [ ] accepted-package shadow importer and import manifest
- [ ] orphan, dangling, duplicate, contradiction, backing, and legacy-edge
  audits
- [ ] pre/post counts, deterministic digests, and idempotent reload evidence
- [ ] tested shadow teardown and rollback instructions
- [ ] documented but unexecuted future database-switch procedure
- [ ] synthetic and live shadow-database integration tests

## Next gate

An independently auditable shadow graph and rollback record advance to the
Schema 4.2 validation-query task. Successful import is not runtime activation
and does not itself establish Data RC readiness.
