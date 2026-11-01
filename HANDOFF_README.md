# FaultDx v2 Data Pipeline Branch Guide

## Purpose

This is the stable entry map for `r1-data`. It explains the
branch boundary and points to the durable workflow. It does not record current
priorities, task status, blockers, worktree state, release readiness, or dated
progress.

It is not the v2 system or release handoff.

## Branch identity

This branch owns governed data engineering and KG delivery:

- source inventory, masking, lineage, review state, and promotion evidence;
- schema and contracts, canonical IDs, aliases, joins, and review queues;
- deterministic ingestion and transforms, plus Route A KG candidates;
- Route B evidence preparation and Route C case preparation;
- independent data/KG evaluation, Data RC evidence, and integration-manifest
  preparation.

It does not own system architecture, UI, runtime, providers, deployment,
release packaging, or full branch integration.

## Authority and reading order

Read in this order:

1. `AGENTS.md`
2. `docs/agents/data_engineering_workflow.md`
3. one durable role guide under `docs/agents/`
4. the task's `brief.md`, `acceptance.md`, and `notes.md`
5. the contract, config, schema, or runbook named by the task

This file is navigation only. Task packages are the authority for operational
scope, status, blockers, and evidence.

## Role selection

- Use the owner named by the task when one exists.
- Otherwise use the workflow's `Task routing` table.
- If ownership is unclear or spans roles, the `data_workflow_lead` performs
  read-only triage before any write owner is assigned.
- The `data_quality_reviewer` remains independent of the candidate
  implementation being reviewed.
- Use `code_review_agent` for independent implementation review. It is
  read-only by default and must ask the user separately before every commit and
  every push, even when the task or plan is already approved.
- Reusable agent guides and sanitized handoffs may be committed. Local task
  packages and private session artifacts remain excluded. See `HANDOFF.md`.

## Durable boundaries

- Preserve `Phenomenon` and `MappingRecord` as the core cross-pipeline objects.
- Route A carries reviewed structured facts and diagnostic chains.
- Route B remains `document_evidence + evidence_only`.
- Route C remains `case_reference + candidate`.
- Co-source Route A/B output is not independent corroboration.
- Masking, extraction, similarity, or historical completeness does not promote
  a candidate to reviewed truth.
- Preserve missingness; do not invent causes, actions, or history.
- Retired role definitions under `legacy/agents/` are historical only.

## Data-content permission

Before inspecting the contents of any file under `data/`, ask the user for
explicit permission for the intended path or bounded scope. This applies to
direct reads and to scripts, tests, validators, or tools that would read those
files indirectly. File-name and metadata inspection may be used only to scope
the permission request safely.

## Task and integration routing

- Work scope, progress, blockers, decisions, and validation live in the owning
  `docs/tasks/R1-TASK##_<name>/` package.
- Historical `TASK-*` packages live under `legacy/tasks/` and are reference-only.
- Contract and schema decisions live with their governed contract artifacts and
  task evidence.
- `HANDOFF_INTEGRATION.md` defines stable integration policy and the required
  Data RC manifest fields; it is not a live delivery ledger.

## Startup

Run `git status --short --branch`, identify the task, choose the owner, state
the plan, boundary, write set, validation, and risks, then work through the
workflow and role guide. Do not read `data/` file contents without the explicit
permission required above.
