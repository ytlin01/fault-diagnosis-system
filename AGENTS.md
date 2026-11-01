# FaultDx v2 Data Pipeline Agent Guide

## Repository and branch identity

On `r1-data`, this repository is the A-owned v2 data source line. It is responsible for governed data engineering and knowledge-graph delivery.

This branch is not the v2 system or release authority. It must not become a second source of truth for system architecture, UI, runtime, providers, deployment, or the global release handoff. Its intended destination is a temporary `r1-integration` branch after Data Contract Freeze and Data Release Candidate review.

`Faultdx_ref/` is reference-only. Never copy its code or data into this repository without explicit design review and manual reimplementation.

## Authority and reading order

For work on this branch, read in this order:

1. `AGENTS.md` — safety, branch scope, and mandatory workflow.
2. `docs/agents/data_engineering_workflow.md` — durable role ownership and stage gates.
3. One of the five durable role guides under `docs/agents/`.
4. The task's `brief.md`, `acceptance.md`, and `notes.md`.
5. The schema, contract, config, or runbook named by that task.

`HANDOFF_README.md` is a stable branch entry map, not workflow authority or a
source of task status. Older Phase 1 tasks, Arc documents, and guides under
`legacy/agents/` are reference material unless a task or durable workflow
document names them. Historical references now point directly to the retired
definitions under `legacy/`; the old root agent filenames have been removed.
Check the live branch and worktree before trusting an old progress statement or
version claim.
## Branch scope

Allowed responsibilities:

- source inventory, registration, sensitivity classification, and lineage;
- structured and unstructured ingestion, local conversion, masking, and serving gates;
- schema and contract proposals, compatibility analysis, and validation;
- canonicalization, aliases, joins, deduplication, and human-review queues;
- deterministic, rerunnable pipelines with manifests;
- Route A asset, diagnostic, and material KG construction and import boundaries;
- Route B serving-safe evidence preparation, without owning system retrieval/runtime policy;
- Route C governed case preparation, without promoting cases to diagnostic truth;
- data/KG quality checks, independent gold sets, old-KG/new-KG comparison, and release evidence;
- a reviewed Data RC integration manifest.

Out of scope unless separately authorized:

- v2 system architecture or technology-stack ownership;
- global API/result design, routing, answer assembly, prompt, or runtime redesign;
- UI, provider, deployment, machine migration, or release packaging;
- repository-wide cleanup of inherited v1 application files;
- application development on `main` or data activation in `r1-integration` before Data RC; release documentation and integration scaffolding are permitted;
- complete merge of this branch without Git-history and data-security review.

Inherited out-of-scope files are `carried / non-authoritative / do not modify`, not cleanup targets.

## Core domain and route boundaries

`Phenomenon` and `MappingRecord` are the core cross-pipeline contract objects. Schema, canonicalization, KG, evaluation, and promotion work must preserve their meaning and provenance.

- Route A may carry reviewed structured facts and diagnostic chains.
- Route B remains `document_evidence + evidence_only`.
- Route C remains `case_reference + candidate`.
- Masking, ingestion success, semantic similarity, or a complete historical chain does not by itself promote a record to reviewed Route A truth.
- A source document may contribute different content to multiple routes, but the same extracted fact must not be counted again as independent Route B corroboration. Preserve co-source provenance.
- GraphRAG is optional and must not become the default path without evaluation evidence.

## Mandatory data workflow

Default lifecycle:

`inventory -> governance -> schema/canonicalization -> pipeline/KG -> evaluation/release review`

Do not skip a gate merely because downstream code can run.

1. Inventory identifies source, owner, version, sensitivity, expected scope, and governed location.
2. Governance decides masking, zone, lineage, serving eligibility, review state, and promotion rules.
3. Schema/canonicalization defines compatibility, identifiers, aliases, joins, conflicts, and migrations before implementation writes.
4. Pipeline/KG work is deterministic, rerunnable, config-driven, manifested, and contract-validated.
5. Evaluation separates pipeline correctness, domain correctness, and answer faithfulness/safety; release review produces an evidence-backed decision and integration manifest.

The branch uses five durable roles, not one agent per small activity:

- `data_workflow_lead`
- `data_contract_engineer`
- `data_pipeline_kg_engineer`
- `data_quality_reviewer`
- `code_review_agent`

Source inventory is normally a read-only mode owned by the lead, not a permanent sixth role. Add a temporary specialist only when a task cannot be handled safely within these boundaries.

Read-only inventory and validation may run in parallel. Governance-state, schema, canonicalization, pipeline, and KG writes require one explicit owner at a time. The quality reviewer must remain independent of the implementation being released.

The code review agent independently reviews implementation changes and is
read-only by default. It must ask the user for explicit permission immediately
before every commit and again before every push. Task approval, plan approval,
or permission for one Git action does not authorize another commit or push.

Reusable agent instructions, role guides, and sanitized handoff documents are
versioned public project documentation. Review their exact contents before
publication. Local task packages, session transcripts, private source details,
credentials, machine-specific settings, and runtime artifacts remain excluded.
Publishing workflow instructions does not prove that an agent executed them or
that independent review or release approval occurred.

## Canonical governance storage

The canonical governance store is:

- `data/governance/source_inventory.csv`
- `data/governance/masking_log.jsonl`
- `data/governance/annotation_log.jsonl`
- `data/governance/index_registry.jsonl`
- `data/governance/eval_run_log.jsonl`

`data/data_governance.xlsx` is retired and absent. If a review export is needed, regenerate it from the canonical CSV/JSONL records; never restore it as the primary mutation target.

## Data security

- Before opening, parsing, previewing, sampling, grepping, or otherwise
  inspecting the contents of any file under `data/`, ask the user for explicit
  permission. This includes indirect reads by scripts, tests, validators, or
  other tools. Permission must identify the intended path or bounded scope and
  must not be inferred from general task authorization. Listing file names or
  reading filesystem/Git metadata without opening file contents is allowed when
  needed to request that permission safely.- Never commit raw sensitive data, customer data, device-log originals, unmasked work orders, private knowledge exports, or unapproved generated payloads.
- Never send raw or unmasked data to external APIs, public model endpoints, or unapproved SaaS.
- External model calls may use only approved, masked, cropped, or structured inputs.
- Samples and evaluation fixtures must state source, masking status, review maturity, and allowed use.
- Do not hardcode secrets, absolute local paths, private service addresses, or credentials.
- Raw inputs are immutable. Transformations create new artifacts in controlled zones.

## Git and dirty-worktree safety

- Start with `git status --short --branch`.
- Preserve existing user changes and untracked work. Never use `git add .` in a mixed worktree.
- Do not rewrite history, force-push, delete branches, or create integration branches without explicit authorization.
- Keep governance changes separate from schema, pipeline, KG, and evaluation implementation commits.
- Do not treat a local brief, ignored file, or IDE tab as a tracked source of truth without verifying it exists on disk.
- Do not allocate a task number when a possibly unsaved or missing task with that number has been reported.
- New task identifiers use the zero-padded `R1-TASK##` convention. Allocate
  them sequentially from R1-TASK01 within release 1. Historical V2-TASK IDs remain reserved; never reuse an identifier within its namespace.

## Task and handoff contract

Substantive work should use `docs/tasks/R1-TASK##_<name>/` after task identity
and overlap are confirmed. Historical `TASK-*` packages are read-only records
under `legacy/tasks/`; do not create new work there. Read active tasks in this
order:

1. `brief.md`
2. `acceptance.md`
3. `notes.md`

Every completed delivery must report:

1. `plan` — intended outcome and explicit boundaries;
2. `changed files` — exact files changed or added;
3. `validation` — commands/checks and results, or why validation was not run;
4. `risks` — unresolved assumptions, blockers, exclusions, and follow-up decisions.

Task notes must distinguish `planned`, `implemented`, `validated`, `reviewed`, and `released`. Never turn a future milestone or locally generated artifact into a completion claim.

## Workflow-system governance

Workflow system files include:

- `AGENTS.md`
- `HANDOFF_README.md`
- `HANDOFF_INTEGRATION.md`
- `.codex/agents/`
- `docs/agents/`
- `docs/tasks/TASK_TEMPLATE.md`
- `.github/CODEOWNERS`
- `.github/pull_request_template.md`
- `.github/workflows/workflow-guard.yml`
- `scripts/check_workflow_guard.py`

Do not modify them as incidental implementation work. A governance change must state why it is needed, which behaviors change, which entry documents must stay synchronized, and how it was validated.

## Durable role guidance

- Branch workflow: `docs/agents/data_engineering_workflow.md`
- Workflow/governance lead: `docs/agents/data_workflow_lead.md`
- Contracts and canonicalization: `docs/agents/data_contract_engineer.md`
- Pipelines and KG: `docs/agents/data_pipeline_kg_engineer.md`
- Independent quality review: `docs/agents/data_quality_reviewer.md`
- Independent code review: `docs/agents/code_review_agent.md`
- CAD extraction runbook: `docs/runbooks/pipelines/cad_extract.md`

Full retired role definitions live under `legacy/agents/`. Pipeline runbooks may describe the version they last validated; treat version claims as historical until checked against the current task, config, schema, tests, and worktree.

## Prohibitions

- Do not modify `Faultdx_ref/`.
- Do not copy reference-repository code into the main project.
- Do not commit notebooks, temporary experiments, one-off scraping scripts, raw data, or local runtime output.
- Do not introduce complex system behavior under the label of data-pipeline initialization.
- Do not make GraphRAG, autonomous tool use, or opaque chained reasoning a default business path before governance and evaluation are defined.
