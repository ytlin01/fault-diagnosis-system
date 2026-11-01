# V2-TASK002_workflow_state_separation

## Identity

- Owner: `data_workflow_lead`
- Reviewer: workflow governance owner
- Decision state: `implemented`
- Dependencies: `AGENTS.md` and protected workflow system
- Downstream consumers: all data-branch roles and task authors

## Goal

Separate durable workflow authority from operational task state and require
explicit user permission before any direct or indirect inspection of file
contents under `data/`.

## Background

The branch entry documents placed current priorities, blockers, dates, and
delivery status inside protected workflow files. That structure duplicated task
state and made volatile information part of the authority chain.

## Scope

- Make `AGENTS -> workflow -> role -> task` the authority chain.
- Convert both handoff documents to durable navigation and integration policy.
- Remove live task state from active workflow documents.
- Make task packages authoritative for operational state.
- Add the `data/` content-read permission gate across workflow entry points.
- Align executable-agent wrappers and workflow-guard coverage.

## Non-goals

- No application, pipeline, KG, schema, runtime, provider, UI, or deployment
  changes.
- No inspection or modification of file contents under `data/`.
- No rewriting of legacy role documents or historical task evidence.
- No release or Data RC readiness claim.

## Write set

- `AGENTS.md`
- `HANDOFF_README.md`
- `HANDOFF_INTEGRATION.md`
- `docs/agents/README.md`
- four active role guides and `data_engineering_workflow.md`
- four `.codex/agents/*.toml` wrappers
- `docs/tasks/TASK_TEMPLATE.md`
- `scripts/check_workflow_guard.py`
- this task package

## Validation

See `acceptance.md` and `notes.md`.

## Risks

- Existing dirty-worktree changes remain user-owned.
