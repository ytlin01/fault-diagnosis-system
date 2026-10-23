# V2-TASK003 DEKG / FHKB ingestion contracts

## Identity

- Owner: `data_contract_engineer`
- Reviewers: `data_workflow_lead`, affected Route B/Route C consumer owner
- Decision state: `FROZEN`
- Candidate versions: `dekg_evidence_v2`, `dekg_validation_policy_v2`,
  `fhkb_case_v1`, `fhkb_validation_policy_v1`
- Dependencies: TASK-017, TASK-035, TASK-042, Route B evidence/policy v2,
  Route C source boundary v1, TPDX Schema 4.1
- Downstream consumers: governed ingestion producers, Route B DEKG builder,
  Route C FHKB index builder, N/system-line consumer validation

## Goal

Define reviewable ingestion boundaries for the Document Evidence Knowledge
Graph (DEKG) and Field History Knowledge Base (FHKB), plus deterministic
offline legacy adapters, without changing runtime behavior or promoting
evidence/cases into TPDX diagnostic truth.

## Background

The existing Route B contract uses a paired evidence-contract and validation-
policy approach. DEKG must preserve that separation. FHKB needs the analogous
separation between case shape and case-governance policy.

The historical tracked Route B v2 pair assumed `DocumentAsset` could be a
published diagnostic-schema node and referenced deleted Schema 4.0 artifacts.
Those v1/v2 evidence-policy files are deleted in the current worktree and this
task does not restore them. TPDX Schema 4.1 contains no `DocumentAsset`; DEKG
therefore tracks non-node `DEKGEvidenceRecord` handoff objects. Full-document
ingestion is the default. Only documents with anchored tabular content selected
for TPDX use evidence-residual mode, which partitions those table anchors out
and sends the remaining content to DEKG. Any graph/index structure is a
downstream derivative rather than a replacement Schema 4.1 document node.
Existing runtime bindings remain unchanged until consumer review accepts a
migration.

The current Route C boundary maps the producer marker `rag_case_pool` to the
consumer capability `case_retrieval`. The FHKB contract must preserve both meanings
rather than silently renaming either value.

## Inputs

- `AGENTS.md`
- `HANDOFF_README.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_contract_engineer.md`
- `docs/onboarding/dekg_fhkb_onboarding/`
- `docs/onboarding/D_handoff/给D的交接-02-三知识库与摄取边界.md`
- Git-history baseline `contracts/evidence/route_b_evidence_v2.json`
- Git-history baseline `contracts/policy/route_b_validation_policy_v2.json`
- `configs/route_c_source_boundary_v1.json`
- `contracts/schema/tpdx_kg_schema_v4_1.schema.json`
- `services/retrieval/route_b_graphrag.py`
- `services/retrieval/route_c_case_index.py`

No file under `data/` is an input to this contract-only task.

## Scope

- Define the stable DEKG `DEKGEvidenceRecord` envelope with `full_document` and
  conditional `evidence_residual` modes, evidence identity, provenance anchors,
  table-only TPDX partition evidence, output semantics, co-source rules, and
  support-artifact derivation boundary.
- Define a separate DEKG validation policy for acceptance, review, rejection,
  blocked content, and forbidden diagnosis promotion.
- Define the stable FHKB case ingestion envelope, source references, candidate
  semantics, and the producer-marker/consumer-target mapping.
- Define an executable FHKB canonical case schema with canonical `case_id`,
  governed source-derived identity, typed case content, field authority,
  missingness, collision, and migration rules. No legacy identifier alias is
  emitted.
- Define a separate FHKB validation policy for acceptance, review, rejection,
  allowlisted fields, and forbidden in-place promotion.
- Implement deterministic offline adapters from the approved legacy FHKB
  candidate and Route B serving-document shapes into the contracts.
- Record compatibility, migration, rollback, and affected-consumer decisions.
- Validate contract structure with synthetic, non-data fixtures.

## Non-goals

- No inspection or mutation of files under `data/`.
- No source registration, masking execution, index build, GraphRAG adoption,
  runtime binding, API/UI change, or release decision.
- No modification of TPDX Schema 4.1.
- No modification of the active Route B v2 pair or Route C source boundary v1.
- No runtime activation or release decision is implied by the frozen contract state.

## Write set

- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/`
- `contracts/evidence/dekg_evidence_v2.json`
- `contracts/evidence/dekg_evidence_v2.schema.json`
- `contracts/case/fhkb_case_v1.json`
- `contracts/case/fhkb_case_v1.schema.json`
- `contracts/policy/dekg_validation_policy_v2.json`
- `contracts/policy/fhkb_validation_policy_v1.json`
- `services/ingestion/dekg_legacy_adapter.py`
- `services/ingestion/fhkb_legacy_adapter.py`
- `tests/unit/test_dekg_fhkb_contracts.py`
- `tests/unit/test_dekg_fhkb_legacy_adapters.py`

## Constraints

- Preserve existing user changes and the mixed worktree.
- Preserve Route B `document_evidence + evidence_only`.
- Preserve Route C `case_reference + candidate`.
- Preserve missingness and record-level provenance.
- A `DEKGEvidenceRecord` is neither a TPDX node nor automatically a DEKG graph
  node. Downstream graph/index artifacts must reference `evidence_id`.
- Full documents enter DEKG unless anchored table content is selected for TPDX.
  Residual mode must exclude those selected table anchors from DEKG records.
- An FHKB case must not create or promote a reviewed `MappingRecord`.
- Co-source TPDX/DEKG material is not independent corroboration.
- `FROZEN` requires workflow-lead and affected-consumer approval.

## Deliverables

- [x] DEKG full-document/evidence-residual contract
- [x] DEKG validation policy
- [x] FHKB case contract
- [x] FHKB validation policy
- [x] compatibility and migration decision
- [x] synthetic validation tests
- [x] notes with exact validation and unresolved review decisions
- [x] executable FHKB canonical case schema
- [x] executable DEKG evidence schema
- [x] deterministic offline FHKB legacy adapter
- [x] deterministic offline DEKG legacy adapter
- [x] synthetic adapter validation and negative cases
