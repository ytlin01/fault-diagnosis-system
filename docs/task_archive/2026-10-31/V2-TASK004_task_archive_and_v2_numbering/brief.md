# V2-TASK004 task archive and v2 numbering

## Identity

- Owner: `data_workflow_lead`
- Reviewer: workflow governance owner
- Decision state: `implemented`
- Dependencies: repository task inventory and protected workflow system
- Downstream consumers: all task authors and branch roles

## Goal

Move retired task packages into a dedicated legacy archive and make
`V2-TASK###` the only active task identifier convention.

## Scope

- Preserve historical task packages under `legacy/tasks/`.
- Centralize retired role guides and runbooks under `legacy/agents/` and
  `legacy/runbooks/`.
- Centralize retired root-level and onboarding material under `legacy/root/`
  and `legacy/onboarding/`.
- Keep local legacy data payloads ignored rather than turning an archive move
  into data publication.
- Rename the three continuing v2 packages to `V2-TASK001` through
  `V2-TASK003`.
- Record this migration as `V2-TASK004`.
- Repair explicit task paths and current identifiers.
- Synchronize workflow entry points, the task template, PR metadata, ownership,
  and automated workflow validation.

## Non-goals

- No application, pipeline, KG, schema, runtime, provider, or data-content
  changes.
- No rewriting of historical task conclusions or statuses.
- No deletion of historical task evidence.
- No inspection of file contents under `data/`.

## Write set

- `legacy/`
- `.gitignore`, limited to local legacy-data exclusion rules
- `docs/tasks/`
- `docs/agents/legacy/` and `docs/runbooks/legacy/` as move sources
- explicit task references outside those directories
- protected workflow entry points and checks required for the convention

## Deliverables

- [x] legacy task archive
- [x] centralized legacy role-guide and runbook archives
- [x] centralized root-level and onboarding archives
- [x] local legacy data payload exclusions
- [x] current v2 task renames
- [x] active naming rule and template
- [x] reference migration
- [ ] validation recorded in `notes.md`
