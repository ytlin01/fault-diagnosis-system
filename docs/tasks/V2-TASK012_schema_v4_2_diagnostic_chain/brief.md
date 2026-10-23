# V2-TASK012 Schema 4.2 diagnostic chain

## Identity

- Owner: `data_contract_engineer`
- Reviewers: `data_workflow_lead`, `data_pipeline_kg_engineer`, affected
  Text2Cypher/evaluation consumer owner, independent `data_quality_reviewer`
- Decision state: `frozen`
- Source/candidate version: frozen `tpdx_kg_schema_v4_1`; candidate Schema 4.2
  relationship proposal
- Dependencies: frozen TPDX Schema 4.1 and its recorded consumer confirmation
- Downstream consumers: Route A diagnostic ingestion, graph import, Text2Cypher,
  Route A evaluation, onboarding/handoff documentation, and DEKG references to
  the TPDX schema identifier

## Goal

Define a reviewable Schema 4.2 change that adds the explicit diagnostic chain
`Phenomenon -> ErrorCode`, `Phenomenon -> Cause`, `Cause -> Action`, and
`Action -> ActionStep` while preserving `MappingRecord` as the governed source,
scope, review, and promotion assertion.

## Background

Schema 4.1 is frozen and must not be edited in place. It currently relates a
`MappingRecord` independently to one `Phenomenon`, an optional `ErrorCode`, zero
or more `Cause` nodes, and zero or more `Action` nodes. That shape preserves
record provenance but does not identify a particular Cause-to-Action pairing
when one source record contains several causes and actions.

The requested chain adds useful pair semantics. Direct chain edges must not
become untracked truth, so every proposed chain edge is an assertion projection
backed by exactly one governed `MappingRecord`.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_contract_engineer.md`
- `contracts/schema/tpdx_kg_schema_v4_1.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_1.md`
- affected non-data consumers found by repository search

No file under `data/` is an input to this contract-only proposal.

## Scope

- Define the proposed direct relationship names, endpoints, cardinalities, and
  `MappingRecord` backing invariants.
- Keep the existing canonical node labels. Treat FP, EC, RC, RA, and RS as
  shorthand for `Phenomenon`, `ErrorCode`, `Cause`, `Action`, and `ActionStep`.
- Preserve all frozen Schema 4.1 artifacts unchanged.
- Record compatibility, migration, rollback, validation, consumer-review, and
  freeze gates before producing an executable Schema 4.2 contract.

## Non-goals

- No edit to frozen Schema 4.1.
- No pipeline, graph, runtime, prompt, provider, UI, or deployment change.
- No inspection or mutation of files under `data/`.
- No claim that the frozen contract is runtime-active or released.
- No promotion of Route B evidence or Route C cases to Route A truth.

## Write set

- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/`
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_2.md`
- `services/governance/tpdx_schema_v4_2.py`
- `tests/unit/test_tpdx_schema_v4_2_contract.py`

The user approved proceeding from the DRAFT proposal on 2026-07-31. Pipeline,
graph import, runtime consumers, and evaluation implementation remain outside
this contract-validation write set.

## Constraints

- Preserve `Phenomenon` and `MappingRecord` meaning and provenance.
- A direct diagnostic-chain edge is invalid unless it names one backing
  `MappingRecord` and that record contains the corresponding endpoint
  memberships.
- Do not merge assertion edges from independent records in a way that loses
  record-level provenance.
- `FROZEN` requires workflow-lead and affected-consumer approval; independent
  quality review remains separate from implementation.

## Deliverables

- [x] Schema 4.2 relationship change decision absorbed into the governed
  ontology and task notes; no standalone proposal artifact is required
- [x] compatibility and migration analysis
- [x] exact affected-consumer inventory at proposal level
- [x] explicit validation, review, freeze, and rollback gates
- [x] task notes with boundaries, validation, and risks
- [x] executable `FROZEN` Schema 4.2 JSON Schema and complete
  standalone ontology
- [x] deterministic semantic validator and synthetic tests
- [x] self-contained Schema 4.2 JSON and ontology artifacts with no runtime,
  packaging, or human-readable-contract dependency on Schema 4.1

## Next gate

The executable contract pair is now `FROZEN` following independent review and
the workflow-lead freeze decision recorded on 2026-08-10. It is not runtime-
active or released.

Pipeline implementation remains a later, separately owned handoff under
`V2-TASK013` and does not complete these contract gates by itself.
