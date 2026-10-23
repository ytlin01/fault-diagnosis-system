# V2-TASK022 acceptance

## Serialized ownership and contract

- [x] `V2-TASK022` was unused before allocation.
- [x] Contract and implementation ownership are serialized rather than shared.
- [ ] Query IDs, parameters, result statuses, provenance fields, ordering,
  limits, and error behavior are accepted by affected consumers.
- [ ] The contract engineer records a reviewed handoff before implementation
  ownership transfers to `data_pipeline_kg_engineer`.
- [ ] Live graph data permission and the exact Task 021 shadow target are
  recorded before integration tests.

## Registry coverage

- [ ] The registry is explicitly bound to Schema 4.2 and rejects unknown
  versions or query IDs.
- [ ] Registered queries cover the full diagnostic chain and phenomenon-
  centered cause/action lookup.
- [ ] Registered queries cover Module assertions and Component/SubComponent
  ancestor resolution.
- [ ] Registered queries cover missing/ambiguous topology and MappingRecord
  provenance.
- [ ] Registered queries cover replacement parts, action-required parts, and
  candidate/review/promotion/serving-state filtering.
- [ ] Registered audits cover orphan, duplicate, conflicting, contradictory,
  and unbacked assertions.

## Adapter safety and result behavior

- [ ] Only registry-selected parameterized read-only Cypher can execute.
- [ ] Unknown or extra parameters, write clauses, arbitrary Cypher, and
  non-read database modes fail closed.
- [ ] Results validate against the normalized result contract and preserve
  applicable MappingRecord/assertion provenance.
- [ ] `success`, `no_result`, `ambiguous`, `excluded`, `abstain`, and `error`
  are observably distinct.
- [ ] Candidate filtering does not leak excluded content.
- [ ] Deterministic ordering and limits prevent unstable result payloads.

## Validation and boundaries

- [ ] Synthetic tests cover every registry entry, status, invalid parameter,
  write rejection, provenance rule, and audit condition.
- [ ] Live integration tests pass against the isolated Task 021 shadow graph.
- [ ] The CLI accepts named queries and parameters and emits deterministic
  contract-valid JSON.
- [ ] Legacy template incompatibilities are recorded without claiming they are
  migrated or runtime-active.
- [ ] No natural-language parser, generated Cypher, graph mutation, runtime
  route, deployment, or database activation is introduced.

## Data-content permission

- [x] Task creation did not inspect any file contents under `data/`.
- [ ] Exact bounded graph/package-derived scope and permission are recorded
  before live integration validation.
