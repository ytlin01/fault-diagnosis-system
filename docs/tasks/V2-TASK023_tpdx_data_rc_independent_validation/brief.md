# V2-TASK023 TPDX independent validation and Data RC

## Identity

- Owner: independent `data_quality_reviewer`
- Reviewers: `data_workflow_lead` and authorized diagnostic, topology,
  material, graph, and validation-query domain reviewers
- Candidate suppliers: `data_pipeline_kg_engineer` owners of Tasks 019-022
- Decision state: `planned`
- Source/candidate version: frozen topology, diagnostic, and material component
  packages; assembled TPDX release; Schema 4.2 shadow graph and query evidence
- Dependencies: `V2-TASK001`, `V2-TASK016`, and completed candidate handoffs
  from `V2-TASK019` through `V2-TASK022`; explicit bounded permission before
  candidate, graph-derived, evaluation, or rollback evidence is read
- Downstream consumer: workflow-lead Data RC integration decision and later
  separately authorized system/runtime activation work

## Goal

Independently evaluate the assembled TPDX release, shadow import, validation
queries, provenance, review-state behavior, safety, regressions, exclusions,
and rollback evidence and issue exactly `READY`, `READY_WITH_EXCLUSIONS`, or
`NOT_READY` without activating the runtime.

## Background

`V2-TASK016` reviews CAD and material candidates but does not independently
validate the complete TPDX release. Package production, database mutation, and
query implementation are intentionally separated to create auditable review
points. This task brings their frozen evidence together for the final
branch-owned Data RC recommendation.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_quality_reviewer.md`
- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/`
- `docs/tasks/V2-TASK019_tpdx_diagnostic_record_producer/`
- `docs/tasks/V2-TASK020_tpdx_component_package_producer_validator/`
- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/`
- `docs/tasks/V2-TASK022_schema_v4_2_validation_query_adapter/`
- frozen component and release packages, import manifest, query results,
  exclusions, review queues, rollback evidence, and independent labels

Before any direct or indirect content read under `data/`, obtain explicit
permission for the exact bounded candidate and evaluation paths. Earlier task
permissions do not transfer to this independent review.

## Scope

- Freeze and fingerprint every candidate, contract, configuration, manifest,
  database digest, query registry, test result, exclusion, and rollback input
  before scoring.
- Preregister applicability, sampling, label maturity and independence,
  leakage controls, exclusions, thresholds, safety gates, and decision rules.
- Verify package and pipeline reproducibility without changing candidate code,
  configuration, mappings, thresholds, aliases, or review decisions.
- Report separate scorecards for:
  - pipeline correctness;
  - graph structural correctness;
  - diagnostic domain correctness;
  - validation-query correctness;
  - provenance and review/promotion-state correctness;
  - safety, missingness, ambiguity, and abstention behavior.
- Consume Task 001 old/new comparison evidence and report old-pass/new-fail,
  old-fail/new-pass, both-pass, both-fail, excluded, and non-applicable cases.
- Audit co-source provenance so one extracted fact is not counted as
  independent Route B corroboration.
- Audit all review queues and exclusions for visibility, reason codes,
  applicability, leakage, and release impact.
- Exercise rollback evidence without modifying the candidate under review or
  activating the runtime database.
- Produce the independent recommendation and an evidence-backed Data RC
  integration manifest only when the decision supports one.

## Non-goals

- No candidate implementation, tuning, repair, reclassification, manual
  override, threshold change, query modification, graph mutation, or package
  rebuild during review.
- No use of candidate output as its own domain-correctness label.
- No hiding safety or provenance failures behind aggregate scores.
- No runtime database switch, deployment, global release, or activation.

## Write set

Independent review writes are limited to:

- `docs/tasks/V2-TASK023_tpdx_data_rc_independent_validation/`
- `docs/outputs/v2_task023_tpdx_data_rc_validation/` for approved sanitized
  review artifacts

Any canonical governance-log or integration-manifest write requires separately
confirmed exact paths, permission, and serialized workflow-lead coordination.

## Decision rules

- `READY`: all blocking governance, reproducibility, structural, domain,
  query, provenance, safety, abstention, and rollback gates pass.
- `READY_WITH_EXCLUSIONS`: failures are fully bounded, excluded, non-leaking,
  operationally enforceable, and do not violate a blocking safety or
  provenance gate.
- `NOT_READY`: any blocking gate fails, evidence is incomplete or dependent,
  exclusions are unenforceable, rollback is unproven, or results cannot be
  reproduced.
- The recommendation never implies runtime activation or release.

## Deliverables

- [ ] preregistered independent evaluation plan and frozen input inventory
- [ ] six separate correctness and safety scorecards
- [ ] old/new paired outcome inventory
- [ ] complete failures, exclusions, review queues, and leakage assessment
- [ ] rollback assessment and activation-boundary confirmation
- [ ] exactly one `READY`, `READY_WITH_EXCLUSIONS`, or `NOT_READY` decision
- [ ] Data RC integration manifest when supported by the decision
- [ ] exact changed files, commands, evidence, risks, and state in `notes.md`

## Next gate

The independent recommendation returns to the workflow lead. Any integration,
runtime database switch, deployment, or global release remains a separately
authorized system/release decision outside this branch task.
