# V2-TASK022 Schema 4.2 validation-query adapter

## Identity

- Current owner: `data_contract_engineer` for the query-registry and normalized
  result-contract phase
- Next owner: `data_pipeline_kg_engineer` after reviewed contract handoff
- Reviewers: `data_workflow_lead`, independent `data_quality_reviewer`, and the
  affected validation consumer owner
- Decision state: `planned`
- Source/candidate version: frozen Schema 4.2 and the isolated shadow graph
  produced by `V2-TASK021`
- Dependencies: frozen Schema 4.2 query/provenance rules; `V2-TASK021` shadow
  graph and import manifest; serialized contract then implementation ownership
- Downstream consumers: `V2-TASK023` independent TPDX Data RC review and a
  later system-owned natural-language-to-intent selector

## Goal

Replace legacy validation dependence on unrestricted or outdated Text2Cypher
templates with a schema-versioned registry of deterministic parameterized
read-only queries, a read-only Neo4j adapter, a normalized result contract, and
explicit abstention behavior.

## Background

The existing templates use legacy `Fault`, `INDICATES`, `RESOLVED_BY`, and
`HAS_STEP` vocabulary. Schema 4.2 validation needs governed deterministic
queries before any natural-language interface is considered.

This task has two serialized ownership phases. The contract engineer first
defines and obtains review for query identities, parameters, result shape,
status semantics, and compatibility. Only after that handoff may the
pipeline/KG engineer implement the adapter, registry execution, CLI, and tests.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_contract_engineer.md` during the contract phase
- `docs/agents/data_pipeline_kg_engineer.md` during implementation
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_2.md`
- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/`
- current legacy templates as compatibility evidence, not an active Schema 4.2
  authority

Any live test that reads package-derived graph content requires the applicable
bounded data-content permission to be recorded before execution.

## Scope

- Define a versioned query-registry contract with stable query IDs, Schema 4.2
  binding, allowed parameters, validation rules, result schema, review-state
  policy, ordering, limits, and abstention behavior.
- Define a normalized result contract distinguishing `success`, `no_result`,
  `ambiguous`, `excluded`, `abstain`, and `error` without conflating absence
  with failure.
- Implement only parameterized read-only Cypher selected from the registry.
- Cover:
  - `ErrorCode -> Phenomenon -> Cause -> Action -> ActionStep`;
  - phenomenon-to-causes/actions lookup;
  - Module-to-governed-`MappingRecord` assertions;
  - Component/SubComponent-to-ancestor-Module-to-assertions traversal;
  - missing and ambiguous topology resolution;
  - `MappingRecord` provenance lookup;
  - replacement parts and action-required parts;
  - candidate, review, promotion, and serving-state filtering;
  - orphan, duplicate, conflicting, and unbacked assertion audits.
- Implement a read-only Neo4j adapter that rejects writes, unknown registry
  IDs, extra parameters, unsafe values, and arbitrary Cypher.
- Add a CLI for named validation queries with deterministic JSON output and
  nonzero behavior for execution or contract failures.
- Add synthetic tests and live integration tests against only the Task 021
  shadow graph.

## Non-goals

- No natural-language parsing, prompt design, LLM call, generated Cypher, or
  unrestricted query endpoint.
- No mutation of the shadow graph or runtime database.
- No runtime routing, answer assembly, provider, UI, deployment, or database
  activation change.
- No in-place reinterpretation of legacy Text2Cypher templates as Schema 4.2.

## Write ownership and proposed write set

Contract-phase writes, owned exclusively by `data_contract_engineer`:

- `docs/tasks/V2-TASK022_schema_v4_2_validation_query_adapter/`
- `contracts/query/tpdx_validation_query_registry_v4_2.json`
- `contracts/query/tpdx_validation_result_v1.schema.json`
- `tests/unit/test_tpdx_validation_query_contract.py`

Implementation-phase writes, transferred explicitly to
`data_pipeline_kg_engineer` only after reviewed contract handoff:

- `services/graph/query_registry/tpdx_v4_2.py`
- `services/graph/tpdx_v4_2_read_adapter.py`
- `scripts/validate_graph/run_tpdx_v4_2_query.py`
- `tests/services/graph/test_tpdx_v4_2_read_adapter.py`
- `tests/integration/test_tpdx_v4_2_validation_queries.py`

No simultaneous contract and implementation write ownership is permitted.

## Failure and abstention behavior

- Unknown query IDs, contract versions, parameters, result fields, write
  clauses, or non-read database access fail closed.
- Empty valid results return `no_result`; unresolved identity returns
  `ambiguous` or `abstain` with reason codes; filtered candidates return
  `excluded` without leaking their content.
- Query timeouts, database errors, and contract violations return `error` and
  cannot masquerade as `no_result`.
- All result records preserve relevant `MappingRecord` and assertion
  provenance.

## Deliverables

- [ ] reviewed schema-versioned query registry and normalized result contract
- [ ] deterministic parameterized read-only query set
- [ ] allowlisted read-only Neo4j adapter
- [ ] normalized CLI output and explicit abstention behavior
- [ ] synthetic contract/adapter tests
- [ ] live Task 021 shadow-graph integration tests
- [ ] legacy compatibility findings and later intent-selector handoff

## Next gate

The validated registry, adapter, normalized results, and live shadow-query
evidence advance to independent Data RC review. Natural-language-to-intent
parsing remains a later system-owned task that may select only from this
validated registry.
