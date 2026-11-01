# V2-TASK012 acceptance

## Proposal and ownership

- [x] Frozen Schema 4.1 remains unchanged.
- [x] The task has one contract owner and names required reviewers and affected
  consumers.
- [x] The contract is explicitly `FROZEN`; it makes no runtime-active, released,
  or deployment claim.
- [x] The change rationale, alternatives, compatibility result, affected
  consumers, migration, rollback, and version-lifecycle decision are governed
  by the Schema 4.2 ontology and these task records; no standalone change-
  proposal artifact is required.
- [x] No file under `data/` was read directly or indirectly.

## Diagnostic-chain semantics

- [x] FP/EC/RC/RA/RS are documented as shorthand, not new canonical labels.
- [x] Proposed stored edges are `HAS_CODE` from `Phenomenon` to `ErrorCode`,
  `HAS_CAUSE` from `Phenomenon` to `Cause`, `HAS_ACTION` from `Cause` to
  `Action`, and `HAS_STEPS` from `Action` to `ActionStep`.
- [x] Existing `MappingRecord` scope, observation, code, cause, and action
  membership edges remain part of the proposed model.
- [x] Every direct chain edge requires a deterministic assertion-edge ID and a
  backing `mapping_record_id`.
- [x] Backing invariants prevent direct edges from becoming unreviewed truth or
  losing source-record provenance.
- [x] The Cause-to-Action edge removes the cross-product ambiguity present when
  a record contains several causes and actions.
- [x] Every `HAS_ACTION` assertion carries a non-empty `cause_action_pair_id`
  identifying the reviewed source pairing; missing pair evidence is rejected.

## Compatibility and next gates

- [x] `HAS_STEP` to `HAS_STEPS` is identified as a breaking relationship-name
  migration, not described as additive compatibility.
- [x] Existing legacy `Fault`/`INDICATES`/`RESOLVED_BY` consumers are identified
  as pre-existing contract drift requiring explicit migration review.
- [x] Executable-schema, pipeline, graph, and consumer changes are deferred
  until proposal acceptance and write ownership are assigned.
- [x] Validation expectations include JSON Schema tests, semantic graph
  invariants, negative provenance cases, consumer query tests, old/new KG
  comparison, and rollback evidence.
- [x] Workflow-lead review accepts the proposed semantics and gate order.
- [x] Affected consumer owner accepts naming and migration compatibility.
- [x] Executable `FROZEN` Schema 4.2 contract and semantic validator are
  implemented and validated with dependency-independent synthetic checks.
- [x] The direct-use requirement is implemented: Schema 4.2 contains all node,
  edge, property, and exclusion definitions it needs, and every `$ref` is local.
- [x] The Schema 4.2 ontology is a complete standalone human-readable contract
  covering every JSON-schema node and stored relationship plus topology,
  identity, query, provenance, migration, exclusion, validation, and lifecycle
  rules.
- [x] Schema 4.2 reaches `FROZEN` through the governed review and freeze process
  process.

## Independent contract-review TODOs

- [x] The independent contract reviewer compares the JSON Schema, ontology, semantic validator, and
  synthetic tests with every diagnostic-chain and `MappingRecord` provenance
  invariant in this acceptance contract.
- [x] The independent reviewer records coverage, failures, exclusions, leakage or self-validation risks,
  and required remediation without modifying the candidate during review.
- [x] The independent reviewer verifies the contract-owner remediation for the direct-use
  finding: Schema 4.2 validates as one file with Schema 4.1 absent from the
  validation package.
- [x] The independent reviewer verifies that Ontology 4.2 is complete and consistent with the
  self-contained JSON contract rather than requiring Ontology 4.1 for meaning.
- [x] The independent reviewer confirms the evaluation plan covers consumer query compatibility,
  old/new KG comparison, and rollback evidence under the separately owned
  pipeline/KG candidate gate.
- [x] The independent reviewer records a `READY` recommendation for the
  contract-review gate.

## Contract-validation TODOs

- [x] Run Draft 2020-12 metaschema and synthetic payload validation in an
  approved environment providing `jsonschema`.
- [x] Rerun the complete Schema 4.2 unit suite with no dependency-related
  skips and record the Python and `jsonschema` versions, commands, and results.
- [x] Keep validation contract-only and confirm that no file under `data/` is
  read directly or indirectly.

## Post-review governance TODOs

- [x] Contract owner resolves accepted findings in a separate implementation
  step and reruns the affected contract-only checks.
- [x] The independent quality reviewer verifies remediation and records final
  acceptance with no exclusions.
- [x] Workflow lead records the explicit freeze decision after the affected-
  consumer and independent-review gates are satisfied.
- [x] After that decision, the JSON Schema, ontology, tests, and task state are
  updated from `REVIEWED_PROPOSAL` to `FROZEN` in one governed change.
