# V2-TASK013 acceptance

## Ownership and boundaries

- [x] `data_pipeline_kg_engineer` is the single implementation write owner.
- [x] Schema 4.2 is identified as `FROZEN`, not runtime-active or released.
- [x] Frozen Schema 4.1 remains the unchanged rollback baseline.
- [x] Runtime/Text2Cypher implementation, DEKG contract migration, independent
  evaluation, freeze, and release remain outside implementation ownership.
- [ ] Exact governed data input/output paths are recorded after explicit
  bounded permission and before any real-data access.

## Deterministic migration

- [x] Equivalent input, config, Schema 4.2 pair, and code version produce
  byte-equivalent canonical candidate, exclusion, and manifest artifacts.
- [x] `HAS_CODE`, `HAS_CAUSE`, `HAS_ACTION`, and `HAS_STEPS` use deterministic
  assertion IDs and exactly one backing `MappingRecord` per stored projection.
- [x] Cause-to-Action projections require explicit reviewed pairs and never use
  a Cartesian product.
- [x] `HAS_STEP` converts to `HAS_STEPS` only with unique valid MappingRecord
  backing; dual publication is rejected.
- [x] Unreviewed, unsafe, ambiguous, contradictory, duplicate, unbacked, or
  invalid records fail closed or appear in explicit governed exclusions.
- [x] Missing values remain missing and are not synthesized.

## Manifest and graph boundary

- [x] The run manifest records input, config, code, Schema 4.2, output,
  exclusion, and validation fingerprints, plus the Schema 4.1 rollback-baseline
  fingerprint used for comparison.
- [x] Graph import is idempotent and cannot silently overwrite independent
  MappingRecord-backed assertions between the same endpoints.
- [x] Packaging validates the self-contained Schema 4.2 contract without a
  Schema 4.1 runtime or package dependency; deployment and activation remain
  outside this task.
- [x] The Schema 4.1 graph remains available and the rollback procedure is
  executable without publishing parallel `HAS_STEP`/`HAS_STEPS` truth.

## Validation and handoff

- [x] Synthetic structural and semantic positive cases pass.
- [x] Negative provenance, pairing, identity, review, safety, duplicate, and
  step-order cases fail as specified.
- [x] A rerun-determinism test passes.
- [x] The separate graph-import boundary rejects legacy `HAS_STEP`, requires a
  frozen contract, and exposes independent assertion conflicts; affected
  legacy loader, Text2Cypher, and Route A evaluation migrations remain open.
- [x] Exact validation commands and observed results are recorded in
  `notes.md`.
- [ ] Independent quality-review inputs include old/new KG comparison,
  exclusions, rollback evidence, and known consumer gaps.
- [ ] Old/new KG comparison reports old-pass/new-fail, old-fail/new-pass,
  both-pass, both-fail, and excluded cases with source anchors and explicit
  applicability rules.
- [x] No completion, freeze, activation, release, or Data RC claim exceeds the
  recorded evidence.

## Data-content permission

- [x] Task creation and initial planning did not inspect file contents under
  `data/`.
- [ ] Explicit bounded user permission is obtained and recorded before any
  direct or indirect real-data read.
