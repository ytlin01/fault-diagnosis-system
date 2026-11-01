# V2-TASK019 acceptance

## Ownership and governance

- [x] `V2-TASK019` was unused before allocation.
- [x] `data_pipeline_kg_engineer` is the single implementation write owner.
- [ ] Exact source registrations, versions, sensitivities, masking states,
  governed locations, and serving/promotion decisions are recorded.
- [ ] Explicit bounded permission is recorded before any direct or indirect
  real-data content read.
- [ ] An independent quality reviewer and authorized diagnostic-domain
  reviewer are named before candidate acceptance.

## Source-to-contract behavior

- [ ] Governed Error Code, Repair SOP, and reviewed table-extraction records
  are supported through explicit source adapters.
- [ ] Output validates as Schema 4.2 `Phenomenon`, `ErrorCode`, `Cause`,
  `Action`, `ActionStep`, and `MappingRecord` records.
- [ ] Source row/cell and document anchors, source and extraction identity,
  masking state, review decision, promotion evidence, and co-source provenance
  survive every transformation.
- [ ] A field named `Root Cause` or similar is not promoted without separate
  authorized review and promotion evidence.
- [ ] Missing or unsupported semantics remain missing and are not synthesized.

## Pairing and assertion authority

- [ ] Every Cause-to-Action assertion has a non-empty reviewed
  `cause_action_pair_id`.
- [ ] Independent cause and action lists never generate a Cartesian product.
- [ ] Every direct chain assertion has deterministic `assertion_edge_id` and
  exactly one backing `mapping_record_id`.
- [ ] Duplicate, contradictory, unbacked, ambiguous, unreviewed, or unsafe
  assertions fail closed or enter a reason-coded review/exclusion artifact.
- [ ] Human-review decisions are append-only evidence and deterministic reruns
  consume only explicitly selected reviewed decisions.

## Reproducibility and handoff

- [ ] Equivalent inputs, configuration, contracts, review decisions, and code
  produce byte-equivalent canonical outputs and manifests.
- [ ] The manifest fingerprints every input, contract, configuration, review
  decision, output, exclusion, queue, and validation result.
- [ ] Synthetic positive, negative, ambiguity, pairing, provenance, leakage,
  and determinism tests pass.
- [ ] A frozen candidate, complete failure inventory, exclusions, and rollback
  evidence are handed to independent review.
- [ ] No package, graph-import, runtime-activation, release, or Data RC claim
  exceeds the recorded evidence.

## Data-content permission

- [x] Task creation did not inspect any file contents under `data/`.
- [ ] Exact bounded paths and user permission are recorded before real-data
  execution or validation.
