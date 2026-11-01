# V2-TASK023 acceptance

## Independence and frozen inputs

- [x] `V2-TASK023` was unused before allocation.
- [x] The `data_quality_reviewer` does not own Tasks 019-022 candidate writes.
- [ ] Exact component packages, release package, shadow import, query registry,
  results, configurations, manifests, exclusions, and code fingerprints are
  frozen before review.
- [ ] Independent labels are governed, maturity-tagged, leakage-checked, and
  not derived from the candidate under review.
- [ ] Applicability, thresholds, exclusions, safety gates, and decision rules
  are preregistered before scoring.
- [ ] Exact bounded paths and independent-review data permission are recorded.

## Pipeline and package correctness

- [ ] Equivalent runs reproduce canonical producer outputs, component
  packages, release manifest, and graph/query evidence where applicable.
- [ ] Contract versions, package identities, hashes, lineage, masking,
  promotion, review, serving, and dependency references are correct.
- [ ] Review queues, exclusions, collisions, ambiguity, missingness, and
  partial failures are complete and visible.

## Graph and diagnostic correctness

- [ ] Schema 4.2 constraints, indexes, identities, counts, graph digest, and
  idempotent reload evidence are independently verified.
- [ ] Orphan, dangling, duplicate, conflicting, contradictory, unbacked, and
  legacy `HAS_STEP` audits pass or every failure is reported.
- [ ] Diagnostic records and Cause-to-Action pairs are evaluated against
  independent domain labels with traceable source anchors.
- [ ] Source headings such as `Root Cause` are not treated as review or
  promotion evidence.

## Query, provenance, and safety correctness

- [ ] Every registered validation query returns contract-valid, deterministic,
  provenance-bearing results for applicable cases.
- [ ] `no_result`, `ambiguous`, `excluded`, `abstain`, and `error` behavior is
  correct and safe.
- [ ] Candidate/review-state filtering prevents unreviewed content leakage.
- [ ] MappingRecord and assertion provenance remain traceable through package,
  graph, and query results.
- [ ] Co-source Route A/B facts are not counted as independent corroboration.
- [ ] Safety-gate failures cannot be offset by aggregate quality scores.

## Regression, rollback, and decision

- [ ] Old-pass/new-fail, old-fail/new-pass, both-pass, both-fail, excluded, and
  non-applicable cases are reported with applicability rules.
- [ ] Rollback evidence is executable and independent of the candidate being
  reviewed.
- [ ] All failures, exclusions, limitations, and remediation requirements are
  included in the recommendation.
- [ ] The final recommendation is exactly `READY`,
  `READY_WITH_EXCLUSIONS`, or `NOT_READY`.
- [ ] A Data RC integration manifest is produced only when supported by the
  evidence and decision.
- [ ] The decision explicitly does not activate a runtime database or release.

## Data-content permission

- [x] Task creation did not inspect candidate or evaluation contents under
  `data/`.
- [ ] This task's own exact bounded permission is recorded before review reads;
  permissions from upstream tasks are not reused implicitly.
