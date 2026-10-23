# V2-TASK020 TPDX component-package producer and validator

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_contract_engineer`, `data_workflow_lead`, affected component
  owners, and independent `data_quality_reviewer`
- Decision state: `planned`
- Source/candidate version: frozen `faultdx_data_package_v1` version `1.0.0`;
  frozen or accepted topology, diagnostic, and replacement/material candidates
- Dependencies: frozen `V2-TASK014`; topology output from `V2-TASK015`;
  material output and review from `V2-TASK017`/`V2-TASK016`; independently
  reviewed diagnostic output from `V2-TASK019`; explicit bounded permission
  before real package or masking-manifest reads
- Downstream consumers: `V2-TASK021` shadow import and `V2-TASK023` independent
  TPDX Data RC review

## Goal

Implement the frozen package contract by producing and validating independent
TPDX component packages and deterministically assembling a `tpdx_release` that
references at most one accepted component of each type.

## Background

`V2-TASK014` froze the shared envelope and TPDX composition rules but did not
implement a production validator, filesystem loader, component producer, or
release assembler. Its four continuing implementation conditions remain
binding, including conforming RFC 8785 canonicalization before real package
identities are issued.

This task produces governed data packages. It does not import them into Neo4j
and does not own global release packaging or runtime activation.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/`
- `contracts/package/faultdx_data_package_v1.json`
- `contracts/package/faultdx_data_package_v1.schema.json`
- frozen Schema 4.2 and accepted component payload contracts
- frozen candidate manifests, masking evidence, review decisions, promotion
  evidence, validation reports, and dependency manifests

Before opening or indirectly validating package or masking-manifest contents
under `data/`, obtain explicit permission for the exact bounded paths.

## Scope

- Implement a conforming RFC 8785 canonicalizer and pass broad Unicode and
  number conformance vectors before issuing real package identities.
- Build separate `tpdx_topology_component`, `tpdx_diagnostic_component`, and
  `tpdx_replacement_material_component` packages.
- Validate contract/schema version, envelope/payload binding, artifact paths,
  byte sizes, hashes, record counts, source lineage, masking evidence, review
  and promotion state, dependency references, and producer identity.
- Derive deterministic package identities and content digests without self-
  referential hashing.
- Detect same-identity/different-content collisions and fail closed.
- Assemble `tpdx_release` with zero or one accepted component of each allowed
  type and without copying component record payloads.
- Require same-release compatibility, accepted component status, matching
  manifest identity and digest, compatible Schema 4.2 binding, portable paths,
  and an acyclic dependency graph.
- Produce deterministic package manifests, validation reports, component
  index, collision evidence, and assembly manifest.

## Non-goals

- No creation of component review or acceptance decisions by the producer.
- No Neo4j connection, graph mutation, database switch, runtime binding,
  deployment, global release collection, or Data RC decision.
- No rewriting of frozen route contracts or source component payloads.
- No silent downgrade, repair, or promotion of invalid components.

## Write set

Initial synthetic implementation writes are limited to:

- `docs/tasks/V2-TASK020_tpdx_component_package_producer_validator/`
- `services/ingestion/faultdx_data_package_v1.py`
- `scripts/build_packages/build_tpdx_component_package_v1.py`
- `scripts/build_packages/build_tpdx_release_package_v1.py`
- `tests/unit/test_faultdx_data_package_v1_producer.py`

No `data/` package path is authorized by task creation. Governed package input
and output roots must be recorded after explicit permission.

## Failure behavior and rollback

- Unknown versions, incomplete evidence, path escape, missing files, hash or
  count mismatch, incompatible contracts, invalid masking coverage, unaccepted
  components, duplicate component types, cycles, and identity collisions exit
  nonzero without publishing a release package.
- Validation never changes component decision state.
- Publication uses a staged output and exposes no partial package as accepted.
- Rollback removes the optional envelope/package output while preserving the
  frozen payload contracts, component artifacts, and prior consumers.

## Deliverables

- [ ] RFC 8785 conformance evidence and deterministic identity implementation
- [ ] component-package producer and filesystem validator
- [ ] deterministic `tpdx_release` assembler
- [ ] hashes, lineage, masking, promotion, decision, and dependency validation
- [ ] collision, incompatibility, incomplete-package, and cycle rejection
- [ ] synthetic positive, negative, conformance, and determinism tests
- [ ] exact commands, changed files, rollback, exclusions, and risks

## Next gate

Synthetic conformance and producer behavior must be reviewed before any real
package ID is issued. A validated assembled package may advance to the separate
shadow-import task only when all referenced components carry independently
recorded acceptance evidence.
