# V2-TASK019 TPDX diagnostic-record producer

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_contract_engineer`, `data_workflow_lead`, independent
  `data_quality_reviewer`, and an authorized diagnostic-domain reviewer
- Decision state: `planned`
- Source/candidate version: governed Error Code, Repair SOP, and reviewed
  table-extraction records; frozen TPDX Schema 4.2 output contract
- Dependencies: frozen `V2-TASK012`; the synthetic migration and import
  boundary from `V2-TASK013`; governed source registration, masking, review,
  and promotion decisions; explicit bounded permission before real-data reads
- Downstream consumers: `V2-TASK020` component packaging, Schema 4.2 shadow
  import, validation queries, and independent TPDX Data RC review

## Goal

Implement the missing governed source-to-Schema-4.2 producer for TPDX
diagnostic knowledge. The producer must preserve source and review authority,
require explicit Cause-to-Action pairing, and send ambiguity to human review
instead of manufacturing diagnostic truth.

## Background

`V2-TASK013` migrates or assembles already-governed diagnostic records and
prepares an import plan. It does not completely transform governed Error Code,
Repair SOP, and reviewed table-extraction records into the canonical Schema
4.2 diagnostic objects.

Source headings and extracted labels are not promotion decisions. In
particular, a field named `Root Cause` is source text only until an authorized
review decision and promotion evidence establish its Route A meaning.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/`
- `docs/tasks/V2-TASK013_tpdx_schema_v4_2_pipeline_kg_candidate/`
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_2.md`
- governed source contracts, registrations, masking evidence, annotations,
  review decisions, and promotion evidence recorded before implementation

Before opening, parsing, sampling, grepping, or indirectly validating any
content under `data/`, obtain explicit permission for the exact bounded paths.

## Scope

- Implement controlled adapters for governed Error Code, Repair SOP, and
  reviewed table-extraction records.
- Emit canonical Schema 4.2 `Phenomenon`, `ErrorCode`, `Cause`, `Action`,
  `ActionStep`, and `MappingRecord` records.
- Preserve source ID and version, source row or table cell, sheet/page/section
  or document anchor, extraction identity, masking state, review decision,
  promotion evidence, and co-source provenance.
- Require a non-empty, reviewed `cause_action_pair_id` for every Cause-to-
  Action assertion. Never infer a Cartesian product from independent cause and
  action lists.
- Generate deterministic canonical IDs, `mapping_record_id` values, and
  `assertion_edge_id` values under the frozen Schema 4.2 rules.
- Keep missing values missing and reject unsupported semantic inference.
- Produce deterministic candidate, exclusion, human-review queue, lineage,
  validation-report, and run-manifest artifacts.
- Route ambiguous mappings, ambiguous Cause-to-Action pairs, conflicting
  source claims, unresolved identities, and insufficient review or promotion
  evidence to reason-coded review records.
- Start with synthetic fixtures and hand a frozen candidate to an independent
  reviewer before it can be accepted for packaging.

## Non-goals

- No change to frozen Schema 4.2 or package-contract semantics.
- No automatic promotion from a source heading, extraction success, masking
  success, semantic similarity, or historical completeness.
- No package-envelope production, Neo4j mutation, runtime query change,
  deployment, or release decision.
- No promotion of Route B evidence or Route C cases to Route A truth.

## Write set

Initial synthetic implementation writes are limited to:

- `docs/tasks/V2-TASK019_tpdx_diagnostic_record_producer/`
- `configs/pipelines/tpdx_diagnostic_records_v1.yaml`
- `services/ingestion/tpdx_diagnostic_records_v1.py`
- `scripts/build_graph/build_tpdx_diagnostic_records_v1.py`
- `tests/unit/test_tpdx_diagnostic_records_v1.py`

No `data/` input or output path is authorized by task creation. Exact governed
paths must be recorded after explicit permission and before real-data access.

## Failure behavior and rollback

- Contract, governance, masking, provenance, review, promotion, identity,
  pairing, or leakage failures stop publication and exit nonzero.
- Structurally safe ambiguity is written only to governed review or exclusion
  artifacts and never to the accepted diagnostic payload.
- Partial output cannot be labeled complete or accepted.
- Rollback removes the separate producer output and leaves Schema 4.1, Schema
  4.2 contracts, governed inputs, and existing graph databases unchanged.

## Deliverables

- [ ] governed source adapters and controlled configuration
- [ ] deterministic Schema 4.2 diagnostic records and assertion projections
- [ ] explicit `cause_action_pair_id` validation
- [ ] review queue, exclusions, lineage, validation report, and run manifest
- [ ] synthetic positive, negative, ambiguity, provenance, security, and
  determinism tests
- [ ] frozen-candidate and independent-review handoff
- [ ] exact changed files, commands, evidence, risks, and state in `notes.md`

## Next gate

First freeze the synthetic producer boundary and source-field authority. Real
execution then requires governed paths and explicit bounded permission. Only
an independently reviewed diagnostic candidate may advance to component
packaging; this task cannot accept or release its own output.
