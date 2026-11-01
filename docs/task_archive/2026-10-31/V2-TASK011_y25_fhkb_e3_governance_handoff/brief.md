# V2-TASK011 Y25 FHKB E3 governance handoff

## Identity

- Owner: `data_workflow_lead`
- Reviewers: `data_contract_engineer`, `data_quality_reviewer`
- Downstream owner: `data_pipeline_kg_engineer`
- Decision state: `implemented`
- Source/candidate version: Phase 1 Y25 downtime source version unresolved;
  proposed derivative `y25_downtime_case_candidates_v1`
- Dependencies: frozen `fhkb_case_v1`, frozen
  `fhkb_validation_policy_v1`, historical Phase 1 `TASK-033` handoff,
  `V2-TASK007`, and `V2-TASK008`
- Downstream consumers: offline FHKB producer, independent quality review,
  N/system-line consumer validation

## Goal

Define the bounded governance evidence to collect on E3 for the ignored Phase 1
Y25 downtime and Route C artifacts in a standalone, read-only governance
session. Do not combine this work with VLM or DEKG production, and do not
register, accept, or publish an FHKB source until that evidence passes the
normal governance gates.

## Background

N's handoff assigns Y25 field downtime to FHKB/Route C and proposes a named
derivative such as `y25_downtime_case_candidates_v1`. The frozen Phase 1 branch
tracks only placeholder directories because `data/raw/**` and
`data/processed/**` were intentionally ignored. Historical documentation names
the following local artifacts:

- a raw workbook matching `C1STN DT*.xlsx` (older notes also say
  `Val CG DT*.xlsx`);
- `data/processed/y25_downtime_canonical.json`;
- `data/processed/_governance/y25_downtime_governance.json`;
- `data/processed/aggregates/rag_fp_case_candidates_v1.json`;
- `data/processed/aggregates/structured_fp_join_v1_baseline.json`.

The current canonical governance store contains 161 inventory rows but no Y25
downtime, FHKB, `rag_fp_case_candidates_v1`, or case-candidate registration.
It contains no corresponding masking, annotation, index, or evaluation record.
The artifacts are also absent from the current worktree. Their presence,
identity, version, masking state, and lineage on E3 therefore remain
unverified.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_workflow_lead.md`
- `docs/onboarding/D_handoff/给D的交接-02-三知识库与摄取边界.md`
- `docs/onboarding/D_handoff/给D的交接-04-面向N系统升级的任务路线与D角色.md`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/`
- `docs/tasks/V2-TASK008_vision_sop_dekg_producer/`
- `contracts/case/fhkb_case_v1.json`
- `contracts/policy/fhkb_validation_policy_v1.json`
- the canonical files under `data/governance/`, read with explicit user
  authorization on 2026-07-28

No E3 data-content permission is implied by the current authorization. The E3
operator may list filenames and metadata to scope a later permission request,
but must obtain explicit bounded permission before opening source or derivative
contents.

## Scope

- Record the exact E3 discovery paths and required metadata for the Phase 1
  Y25 downtime source and derivatives.
- Define the source-registration, masking, lineage, serving, validation,
  indexing, evaluation, and consumer-review evidence still missing.
- Define the failure states and the serialized owner/reviewer sequence.
- Keep the read-only FHKB discovery session operationally separate from every
  VLM, DEKG production, or graph-migration session.

## Non-goals

- No E3 access, raw workbook read, artifact copy, checksum claim, or data
  transformation is performed by this task.
- No mutation of `data/governance/`; the existing inventory change belongs to
  `V2-TASK007` and is preserved.
- No creation of the proposed FHKB package, case index, benchmark, runtime
  binding, or Data RC release claim.
- No use of `structured_fp_join_v1_baseline.json` as the Route C serving source.
- No promotion of historical causes/actions to reviewed Route A truth or a
  `MappingRecord`.
- No VLM execution, DEKG production, or graph migration in this governance
  session.

## Write set

- `docs/tasks/V2-TASK011_y25_fhkb_e3_governance_handoff/`

Any future governance mutation requires a reviewed dry run naming the exact
rows/events, rollback evidence, one governance write owner, and read-back
validation.

## Constraints

- Preserve Route C as `route_c_case + case_reference + candidate`.
- Preserve the producer marker `rag_case_pool` separately from the consumer
  target `case_retrieval`.
- Register named artifacts only; never scan or register an aggregate directory.
- Preserve source-derived missingness and record-level `source_refs`.
- Do not infer that a Phase 1 artifact is serving-safe from its filename,
  successful ingestion, or historical runtime use.
- Keep E3 FHKB discovery read-only until path-bounded data-content permission
  is granted there.

## Deliverables

- [x] E3 FHKB governance evidence checklist
- [x] exact current governance gaps
- [x] serialized ownership and next-gate sequence
- [x] failure, exclusion, and no-promotion rules
- [x] validation and risk evidence in `notes.md`
- [ ] E3 discovery evidence captured
- [ ] source-specific governance decision reviewed
- [ ] approved governance mutation executed and read back
- [ ] independent FHKB package quality review completed
