# V2-TASK###_<name>

> Copy this template to `docs/tasks/V2-TASK###_<name>/brief.md`, replacing
> `###` with the next unused zero-padded sequence. Keep operational state in
> this task package; do not copy it into workflow or handoff documents.

## Identity

- Owner:
- Reviewer:
- Decision state: `planned`
- Source/candidate version:
- Dependencies:
- Downstream consumers:

Allowed decision states are `planned`, `implemented`, `validated`, `reviewed`,
and `released`. Record each transition with evidence; do not infer later states.

## Goal

State the problem and intended result in one or two sentences.

## Background

Describe why the task exists, its upstream dependencies, and the evidence that
defines the starting point. Do not use this section as a branch-wide status page.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- the owning role guide
- governed contracts, configs, schemas, or runbooks required by this task

Before inspecting the contents of any file under `data/`, ask the user for
explicit permission for the intended path or bounded scope. This includes
indirect reads through scripts, tests, validators, or other tools.

## Scope

List the exact responsibilities included in this task.

## Non-goals

List adjacent work and authority that this task does not own.

## Write set

List the exact files or bounded paths this task may change. Governance-state,
contract, pipeline/KG, task-status, and release writes require one explicit
owner.

## Constraints

- Preserve existing user changes and mixed-worktree safety.
- Do not inspect `data/` file contents without explicit user permission.
- Do not modify `Faultdx_ref/`.
- Do not send unapproved data to external services.
- Preserve Route A/B/C meaning and `Phenomenon`/`MappingRecord` provenance.
- Do not turn a proposal, candidate, or future milestone into a completion claim.

## Deliverables

- [ ] intended artifacts
- [ ] exact changed files
- [ ] validation commands and observed results
- [ ] exclusions, risks, and open decisions
- [ ] `notes.md` updated

## Acceptance

Place executable acceptance criteria in `acceptance.md`:

- [ ] each result is evidence-backed
- [ ] failure and exclusion behavior is explicit
- [ ] ownership and next gate are named
- [ ] data-content permission was obtained before any applicable read

## Notes contract

`notes.md` must record:

1. `plan` — intended outcome and boundaries
2. `changed files` — exact files changed or added
3. `validation` — commands/checks and observed results
4. `risks` — unresolved assumptions, blockers, exclusions, and decisions
5. `state` — `planned`, `implemented`, `validated`, `reviewed`, or `released`

Task notes are the authority for operational progress. Workflow documents,
role guides, and handoff pages must not carry task priorities or status.
