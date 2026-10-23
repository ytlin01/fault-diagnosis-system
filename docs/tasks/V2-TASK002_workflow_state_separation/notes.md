# V2-TASK002_workflow_state_separation - Notes

## Plan

Separate durable workflow rules from volatile work state, add the mandatory
`data/` content-read permission gate, and synchronize every active workflow
entry point without modifying implementation or data artifacts.

## Changed files

- `AGENTS.md`
- `HANDOFF_README.md`
- `HANDOFF_INTEGRATION.md`
- `.codex/agents/data_workflow_lead.toml`
- `.codex/agents/data_contract_engineer.toml`
- `.codex/agents/data_pipeline_kg_engineer.toml`
- `.codex/agents/data_quality_reviewer.toml`
- `docs/agents/README.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_workflow_lead.md`
- `docs/agents/data_contract_engineer.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- `docs/agents/data_quality_reviewer.md`
- `docs/tasks/TASK_TEMPLATE.md`
- `docs/tasks/V2-TASK002_workflow_state_separation/brief.md`
- `docs/tasks/V2-TASK002_workflow_state_separation/acceptance.md`
- `docs/tasks/V2-TASK002_workflow_state_separation/notes.md`
- `scripts/check_workflow_guard.py`

## Validation

- `git diff --check` on all tracked files changed by this task: passed; Git
  emitted only existing working-tree line-ending normalization warnings.
- Trailing-whitespace scan on the untracked V2-TASK002 package: passed.
- Active-workflow scan for numeric task IDs, dates, snapshots, current
  priorities, and pending/deferred status claims: no matches.
- Role/wrapper scan for `HANDOFF_README.md` authority dependencies: no matches.
- Permission-coverage scan: the rule is present in AGENTS, both handoff entry
  documents, the workflow, role index, all four role guides, all four executable
  wrappers, and the task template.
- Python `tomllib` parse of all four wrappers: passed.
- `scripts/check_workflow_guard.py` with acknowledged `V2-TASK002` PR metadata:
  passed and recognized `.codex/agents/` as protected.
- Final scoped status and diff-stat review: only the intended paths above were
  added or modified by this task.

No application tests were run because this task changes workflow documentation,
agent instructions, and guard coverage only.

## Risks

- The worktree contained substantial pre-existing user changes before this task.
- `HANDOFF_INTEGRATION.md` had user edits; their Schema 4.0 decision content was
  verified in the owning task and contract documents before the policy rewrite.
- No file contents under `data/` were inspected.
- This task is validated, but not independently reviewed or released.

## State

`validated`