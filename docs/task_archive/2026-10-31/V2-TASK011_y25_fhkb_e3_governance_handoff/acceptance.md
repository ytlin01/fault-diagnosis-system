# V2-TASK011 acceptance

## Task and safety

- [x] `V2-TASK011` was the next unused zero-padded task identifier after the
  existing `V2-TASK007` through `V2-TASK010` worktree packages.
- [x] Owner, reviewers, downstream owner, scope, non-goals, write set, and next
  gates are explicit.
- [x] The user explicitly authorized reads of `data/governance/` before the
  canonical governance audit.
- [x] No E3 or Y25 data artifact was opened, copied, hashed, or transformed.
- [x] Existing mixed-worktree and canonical-inventory changes remain untouched.

## Current governance gap

- [x] The canonical inventory was checked for Y25 downtime, FHKB,
  `rag_fp_case_candidates_v1`, and case-candidate registrations; zero matches
  were found.
- [x] The canonical masking, annotation, index, and evaluation logs were checked;
  none contains a Y25/FHKB governance event.
- [x] The historical source and derivative paths are recorded as discovery
  leads, not asserted present artifacts.
- [x] The older handoff's `DRAFT` statement is superseded by the live frozen
  FHKB contract and policy.

## E3 discovery gate

- [ ] E3 custodian and exact machine/bundle location are recorded.
- [ ] Filename and filesystem metadata identify the exact raw workbook(s),
  canonical artifact, governance sidecar, Route C candidate artifact, and
  review baseline.
- [ ] Explicit bounded permission is obtained before opening any E3 data file.
- [ ] Approved reads establish source owner, source version/snapshot, checksum,
  sensitivity, sheet/record scope, governed location, and custody lineage.
- [ ] Artifact checks establish schema/version, counts, manifest/checksum,
  masking evidence, serving-safety evidence, and derivation lineage.
- [ ] Evidence distinguishes the candidate runtime artifact from the
  review-only baseline and records any missing or conflicting artifact.

## Governance and producer gate

- [ ] The workflow lead prepares an exact source-specific inventory/masking/
  annotation proposal as a dry run, with rollback evidence.
- [ ] The contract engineer reviews source ID/version, field projection,
  canonical identity, `source_refs`, collision behavior, and missingness.
- [ ] One explicit governance write owner executes only the approved records;
  exact read-back validation passes.
- [ ] The pipeline/KG engineer produces a deterministic named FHKB package with
  manifest, config digest, lineage, counts, and per-record disposition.
- [ ] Package and records validate against frozen `fhkb_case_v1` and
  `fhkb_validation_policy_v1`.
- [ ] Accepted, review, and rejected counts and reasons reconcile to the input;
  no record is silently dropped.

## Independent and consumer gates

- [ ] The quality reviewer independently checks rebuild determinism, identity
  collisions, blocked fields, promotion safety, exclusions, and offline
  retrieval evidence.
- [ ] `index_registry.jsonl` is updated only for an accepted, named index.
- [ ] `eval_run_log.jsonl` is updated only for an executed, evidence-backed
  evaluation.
- [ ] N validates the immutable package or approved serving-safe projection in
  an independent consumer environment.
- [ ] Data RC or runtime activation remains a separate reviewed decision.
