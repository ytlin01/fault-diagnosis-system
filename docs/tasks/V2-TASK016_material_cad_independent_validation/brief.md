# V2-TASK016 Material and CAD independent validation

## Identity

- Owner: `data_quality_reviewer`
- Reviewers: `data_workflow_lead`; domain reviewers for material and CAD labels
- Candidate suppliers: `data_pipeline_kg_engineer` owners of `V2-TASK017` and
  `V2-TASK015`
- Decision state: `planned`
- Candidate versions: material-parser candidate from `V2-TASK017` pending;
  CAD A/B/C Phase 3 r10 frozen by `V2-TASK015` for independent validation
- Dependencies: complete manifests, provenance, exclusions, rollback evidence,
  explicit bounded data permission, and independent review labels
- Downstream consumers: Data RC review and separately owned graph/runtime
  activation decisions

## Goal

Independently determine whether the material parser and CAD A/B/C candidates are
governed, reproducible, contract-correct, domain-correct, safe, and sufficiently
evaluated to advance, returning `READY`, `READY_WITH_EXCLUSIONS`, or
`NOT_READY` without modifying either candidate.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_quality_reviewer.md`
- `V2-TASK017` and `V2-TASK015` briefs, acceptance, notes, frozen candidates,
  configs, manifests, exclusions, audits, lineage, and rollback evidence
- independently governed material/CAD review labels and applicability rules

Before any direct or indirect content read under `data/` or the local handoff
data locations, obtain explicit user permission for the bounded paths.

## Scope

- Verify governance, permission, masking, lineage, review-state, contract, and
  manifest completeness.
- Reproduce equivalent runs without changing candidate code or configuration.
- Evaluate material nodes, joins, candidates, exclusions, collision behavior,
  missingness, leakage, and relationship precision/coverage.
- Evaluate CAD classification overlays, field extraction, index joins, BOM
  extraction/audit, overrides, relationships, missingness, and final outputs.
- Separate pipeline correctness, domain correctness, and downstream
  faithfulness/safety scorecards.
- Compare the approved baseline and candidate where a valid old/new comparison
  exists, reporting old-pass/new-fail, old-fail/new-pass, both-fail, and
  exclusions.
- Report applicability, label independence, leakage risks, all failures,
  exclusions, rollback readiness, and remediation requirements.

## Non-goals

- No implementation, tuning, alias adjustment, threshold adjustment, manual
  override creation, or candidate repair during review.
- No use of candidate output as its own independent correctness label.
- No hiding failures behind aggregate scores.
- No runtime activation, graph mutation, deployment, or release packaging.

## Write set

Review writes are limited to:

- `docs/tasks/V2-TASK016_material_cad_independent_validation/`
- `docs/outputs/v2_task016_material_cad_validation/` for approved sanitized
  review artifacts only

Any canonical governance-log update requires separately confirmed exact paths,
permission, and serialized workflow-lead coordination.

## Deliverables

- [ ] preregistered evaluation plan, applicability, exclusions, and go/no-go
  gates
- [ ] independent material and CAD review sets with maturity and leakage status
- [ ] reproducibility, contract, graph, domain, regression, and safety results
- [ ] paired old/new differences where applicable
- [ ] complete failure and exclusion inventory
- [ ] rollback assessment
- [ ] `READY`, `READY_WITH_EXCLUSIONS`, or `NOT_READY` recommendation
- [ ] exact changed files, commands, evidence, risks, and state in `notes.md`
