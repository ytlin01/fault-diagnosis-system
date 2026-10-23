# V2-TASK005 data docs archive and outputs relocation

## Identity

- Owner: `data_workflow_lead`
- Reviewer: workflow governance owner
- Decision state: `implemented`
- Dependencies: `V2-TASK001`, `V2-TASK003`, and `V2-TASK004`
- Downstream consumers: active task authors and documentation readers

## Goal

Keep only documentation with an explicit active-v2 relationship in
`docs/data/`, archive the remaining historical data documentation, and place
V2-TASK001 review outputs under `docs/outputs/`.

## Scope

- Classify `docs/data/` by explicit references from active V2 task packages and
  current onboarding/workflow material.
- Retain the Route B schema-boundary decision as a direct V2-TASK003 input.
- Move unrelated historical documents to `legacy/data/docs/`.
- Move the V2-TASK001 output subtree to `docs/outputs/` and replace its retired
  `TASK-044` filename with `V2-TASK001`.
- Repair explicit paths without changing historical conclusions.

## Non-goals

- No inspection or modification of file contents under repository `data/`.
- No application, pipeline, KG, schema, contract, or runtime behavior changes.
- No deletion of historical documentation or generated review outputs.
- No promotion of generated review material to released or reviewed truth.

## Write set

- `docs/data/`
- `legacy/data/docs/`
- `docs/outputs/`
- former repository-root `outputs/` as a move source
- explicit repository references to moved artifacts
- this task package

## Deliverables

- [x] bounded keep/archive classification
- [x] historical data-document archive
- [ ] V2-TASK001 output relocation present and recoverable
- [x] reference repair
- [ ] validation passes against the current worktree
