# C1STN error-code seed masking — acceptance

## Governance

- [ ] The raw inventory record uses the exact repository-relative path.
- [ ] Raw remains immutable, non-serving, non-KG, and non-evaluation input.
- [ ] The dedicated masked derivative receives its own source ID and lineage.
- [ ] Masking completion, review maturity, annotation eligibility, and
  serving eligibility remain separate states.

## Configuration and inspection

- [ ] A header-only inspection identifies sheet names, dimensions, header row,
  matched aliases, unmatched columns, and unused rules.
- [ ] No raw row values are copied into task documentation or chat.
- [ ] `v2_task001_c1stn_error_code_seed` matches only the intended workbook.
- [ ] Every discovered column is allowlisted or explicitly excluded.
- [ ] Every retained column has an A/B/C classification and canonical/serving
  action.
- [ ] Free-text diagnostic and repair fields are review-flagged.
- [ ] The configured sheet and header row are explicit after inspection.

## Dry-run and formal masking

- [ ] The data owner reviews a local five-row dry-run.
- [ ] The dry-run has no unmatched columns.
- [ ] Unused rules are absent or have a documented explanation.
- [ ] `FAULTDX_MASKING_SALT` is supplied through a controlled local secret when
  tokenize/hash actions are required; it is never recorded in Git or notes.
- [ ] Formal masking produces canonical, serving-candidate, manifest, and
  lineage artifacts without modifying raw input.
- [ ] Observed input, blank, duplicate, excluded, canonical-output, and
  serving-output row counts reconcile; any difference from the reported 225 is
  explained.

## Audit and annotation handoff

- [ ] Lineage sampling confirms A-level tokenize/drop, B-level
  retain/generalize-or-drop, and C-level passthrough behavior.
- [ ] The serving-candidate audit reports no unresolved identifiers or
  sensitive operational context.
- [ ] Review-flagged free text receives a bounded human review.
- [ ] The masked derivative remains non-serving unless separately approved.
- [ ] A successful run records masking evidence in the canonical masking log.
- [ ] The annotation adapter consumes only the reviewed masked derivative.
- [ ] The first annotation queue contains 10–15 development cases and marks
  source causes/actions as `source_suggested`, not gold.

## Failure behavior

- [ ] Missing workbook, wrong sheet, wrong header, unmatched columns, missing
  required salt, empty output, or row-count mismatch fails the gate.
- [ ] A failure does not produce a gold label, serving approval, KG
  eligibility, or a completion claim.

## Run evidence traceability

- [x] The masking configuration names the governed raw, canonical, and serving
  source IDs separately.
- [x] One run ID is written to the masking run manifest, every lineage record,
  and the canonical masking-log event.
- [x] New masking-log events include portable run-manifest and lineage paths.
- [x] Run manifests omit machine hostname and machine-root paths.
- [x] Existing append-only masking-log rows remain readable without rewriting
  history.
- [ ] A fresh data-owner formal run proves that the emitted manifest, lineage,
  and masking-log event carry the same run ID and governed source IDs.
