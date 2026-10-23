# Data Engineering Workflow

## Purpose

This is the durable branch workflow for governed v2 data engineering and KG
delivery. `AGENTS.md` is higher authority. Operational scope, status, blockers,
and evidence live in the owning task package, not in workflow documents.

## Role roster

| Role | Owns | Default model / effort |
|---|---|---|
| `data_workflow_lead` | scope, inventory, governance, dependency order, handoffs, Data RC preparation | Terra / medium; high for RC synthesis or conflict arbitration |
| `data_contract_engineer` | contracts, compatibility, identifiers, aliases, joins, conflicts, migrations | Terra / medium; high for redesign or migration decisions |
| `data_pipeline_kg_engineer` | ingestion, transforms, manifests, triples, graph validation, import boundary | Luna / medium; low only for read-only inventory; escalate for risky debugging |
| `data_quality_reviewer` | independent gold governance, evaluation, regressions, release recommendation | Terra / medium; high for release review, paired evaluation, or disputed regressions |
| `code_review_agent` | independent code review for correctness, security, contract adherence, tests, and regression risk | Terra / medium; high for security-sensitive or cross-boundary review |

Model settings are defaults, not authority. Preserve the role boundary if a
named model is unavailable.

## Lifecycle

| Gate | Owner | Required result |
|---|---|---|
| inventory and governance | workflow lead | source, sensitivity, lineage, route eligibility, review/promotion decision, next owner |
| schema and canonicalization | contract engineer | reviewed contract, IDs/aliases/joins, conflict and migration rules |
| deterministic pipeline and KG candidate | pipeline/KG engineer | rerunnable config-driven output, manifest, validation, exclusions |
| independent evaluation and Data RC review | quality reviewer | coverage, failures, paired differences when relevant, `READY` / `READY_WITH_EXCLUSIONS` / `NOT_READY` |

A contract is `DRAFT`, `REVIEWED_PROPOSAL`, or `FROZEN`; JSON validity alone
does not freeze it. Do not skip a gate because downstream code can run.

## Data-content permission gate

Before any role opens, parses, previews, samples, greps, or otherwise inspects
the contents of a file under `data/`, it must ask the user for explicit
permission for the intended path or bounded scope. The same rule applies when a
script, test, validator, comparison, or packaging command would read the file
indirectly. File names and filesystem/Git metadata may be inspected only to
scope the request safely.

This permission gate precedes inventory, validation, and implementation. A task
approval or role assignment does not imply permission to read `data/` contents.

## Route and promotion boundaries

- `Phenomenon` and `MappingRecord` remain the cross-pipeline contract objects.
- Route A carries reviewed structured facts and diagnostic chains.
- Route B is `document_evidence + evidence_only`; Route C is
  `case_reference + candidate`.
- Co-source Route A/B output is not independent corroboration.
- Masking, extraction, similarity, or historical completeness never promotes a
  candidate to reviewed truth.
- GraphRAG is optional and requires evaluation evidence.

## Write ownership and handoff

Read-only inventory, audit, and validation may run in parallel after any
required data-content permission is granted. Governance logs, contracts,
canonical IDs, pipeline/KG outputs, task status, and release recommendations are
serialized.

Every handoff records: task, candidate/source version, owner and reviewer,
decision state, inputs, outputs, contract version, governance/masking state,
validation, exclusions, risks, next owner, and required decision.

## Code review and Git permission gate

The code review agent is independent of the implementation it reviews and is
read-only by default. It reports actionable findings with file and line
evidence, separates blocking findings from suggestions, and records validation
limits. It does not silently fix reviewed code or claim data/domain/release
approval.

If a task separately authorizes the code review agent to make changes, normal
write ownership still applies. The agent must ask the user for explicit
permission immediately before every `git commit` and must ask again immediately
before every `git push`. Task approval, plan approval, prior standing approval,
or approval of one Git action does not authorize a later commit or push. Commit
and push approval must never be bundled into one request.

## Task routing

| Work | Owner | Required review |
|---|---|---|
| intake / inventory | workflow lead | contract engineer when shared concepts change |
| contract, IDs, aliases, joins | contract engineer | lead and affected consumer |
| ingestion, masking, manifests, triples | pipeline/KG engineer | lead; contract engineer and quality reviewer for graph/import boundary |
| gold sets, regressions, paired KG evaluation | quality reviewer | lead for provenance; domain review for labels |
| Data RC and integration manifest | lead prepares | quality reviewer recommends independently |
| implementation code review | code review agent | owning implementation role responds; quality reviewer remains independent for data/KG readiness |

## Operational record

Each task package is the only workflow-level source for its operational state:

- `brief.md` defines the approved scope and write boundary;
- `acceptance.md` defines executable gates;
- `notes.md` records `planned`, `implemented`, `validated`, `reviewed`, and
  `released` separately.

Contract decisions also live with the governed contract artifact. Data RC
delivery state lives in the reviewed integration manifest. Do not duplicate
priority lists, blockers, dates, or completion claims in workflow documents.
