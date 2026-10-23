# V2-TASK016 acceptance

## Independence and applicability

- [x] `data_quality_reviewer` owns review and does not own candidate writes.
- [ ] Candidate versions, configs, manifests, exclusions, and code fingerprints
  are frozen before review.
- [ ] Review labels are independent, governed, maturity-tagged, and leakage
  checked.
- [ ] Applicability and exclusion rules are preregistered before scoring.

## Pipeline and contract correctness

- [ ] Equivalent reruns reproduce material and CAD canonical artifacts.
- [ ] Contract, semantic, provenance, masking, review-state, and manifest gates
  pass or each failure is reported visibly.
- [ ] Missingness, duplicates, collisions, ambiguity, dangling relationships,
  unsafe overrides, and exclusion behavior are measured separately.
- [ ] Rollback evidence is executable and does not depend on the candidate under
  review.

## Domain correctness and safety

- [ ] Material identity/join/relationship precision and coverage are evaluated
  against independent labels.
- [ ] CAD classification, field, BOM, audit, and relationship correctness are
  evaluated against approved representative samples.
- [ ] Pipeline correctness, domain correctness, and downstream
  faithfulness/safety are separate scorecards.
- [ ] Safety-gate failures cannot be offset by aggregate quality scores.

## Decision

- [ ] Old-pass/new-fail, old-fail/new-pass, both-fail, and excluded cases are
  reported wherever paired comparison is valid.
- [ ] All failures, exclusions, limitations, and remediation requirements are
  included in the recommendation.
- [ ] The final recommendation is exactly `READY`, `READY_WITH_EXCLUSIONS`, or
  `NOT_READY` and does not imply runtime activation or release.

## Data-content permission

- [x] Task creation did not inspect candidate or review data content.
- [x] Exact bounded paths and explicit permission are recorded before any direct
  or indirect data-content read. (Read: masked derivative only; read/write:
  `data/processed/` incl. `v2_task017_material_candidate/run1/`; raw
  `data/raw/...` not permitted. See notes 2026-09-01.)
