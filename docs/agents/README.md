# Agent Guides

This directory contains durable role instructions for
`feature/v2-data-pipeline`. A role guide defines who owns a class of work; a task
package defines what that role must do for one delivery.

## Authority

```text
AGENTS.md
  -> data_engineering_workflow.md
      -> one role guide
          -> V2-TASK###_<name>/{brief,acceptance,notes}.md
```

`AGENTS.md` sets branch safety and scope.
`docs/agents/data_engineering_workflow.md` defines gates and handoffs.
A role guide defines ownership and boundaries.
A task package is authoritative for operational scope, status, blockers, and
acceptance evidence.

`HANDOFF_README.md` is a stable navigation page and is not part of the authority
chain.

## Durable roles

| Role | Guide | Owns |
|---|---|---|
| `data_workflow_lead` | `data_workflow_lead.md` | scope, inventory, governance, dependencies, handoffs, Data RC preparation |
| `data_contract_engineer` | `data_contract_engineer.md` | contracts, canonical IDs, aliases, joins, conflicts, migrations |
| `data_pipeline_kg_engineer` | `data_pipeline_kg_engineer.md` | ingestion, masking integration, deterministic pipeline/KG artifacts |
| `data_quality_reviewer` | `data_quality_reviewer.md` | independent quality, evaluation, regressions, readiness recommendation |
| `code_review_agent` | `code_review_agent.md` | independent implementation review, actionable findings, and regression-risk assessment |

There are no other durable roles on this branch.

## Startup procedure

1. Read the authority chain and the task package.
2. State role, scope, non-goals, exact write set, validation, and risks.
3. Ask the user for explicit permission before any direct or indirect read of
   file contents under `data/`.
4. Wait for plan confirmation when the task is not already approved.
5. Write durable results to `notes.md` using `plan`, `changed files`,
   `validation`, and `risks`.

Read-only investigations may run in parallel. Governance, contract, pipeline/KG,
task-status, and release writes require one explicit owner.

## Executable agents

`.codex/agents/` contains repository-local Codex wrappers for the five roles.
They select defaults only; these Markdown guides remain authoritative for scope,
gates, handoffs, and effort escalation. Changes to this directory and
`HANDOFF_INTEGRATION.md` are protected workflow changes.

The code review wrapper is read-only by default. Even when a separate task
authorizes edits, it must obtain fresh, separate user permission immediately
before every commit and every push.

## Operational state

Current work never belongs in this directory. Record task scope and status only
in the owning `docs/tasks/V2-TASK###_<name>/` package. Record
release-candidate delivery
state only in its reviewed manifest.

## Legacy

Retired role definitions live under `legacy/agents/`. Historical task
packages live under `legacy/tasks/`. They may be used as evidence, but they do
not override durable branch guidance. CAD
extraction remains an operational runbook at
`docs/runbooks/pipelines/cad_extract.md`.
