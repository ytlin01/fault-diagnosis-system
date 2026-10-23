# C1STN replacement-list masking — acceptance

## Governance

- [x] The raw inventory record exists with the exact repository-relative path
  (`raw__C1STN_bom_material__L_ReplacementList`, registered 2026-08-27).
- [x] Raw remains immutable, non-serving, unmasked, and review-pending.
- [x] The masked canonical and serving derivatives receive their own source
  IDs and lineage after the formal run.
- [x] Masking completion, review maturity, and serving eligibility remain
  separate states.

## Configuration and inspection

- [x] `c1stn_replacement_list` matches only the governed workbook.
- [x] The configured sheet and header row are explicit and owner-verified
  (sheet `工作表1`; header at 0-based row 1; one field-description row
  skipped; data starts at Excel row 4).
- [x] Every retained column is allowlisted with an A/C classification and
  canonical/serving actions matching the owner classification note.
- [x] Deferred columns are dropped via `columns_keep` with the inventory note
  as justification; no undeclared column reaches masking.
- [x] Free-text `備註` is review-flagged (redact in canonical, drop in
  serving).
- [x] The masking configuration names the governed raw, canonical, and
  serving source IDs separately.

## Dry-run and formal masking

- [x] The data owner ran and reviewed the local dry-run (2026-08-27): sheet
  and layout confirmed, no unmatched columns reported.
- [x] The dry-run count summary (rows read / after filter / after dedupe) is
  recorded in the subtask notes (superseded by the formal-run manifest: 53
  rows, no filtering, no deduplication).
- [x] `FAULTDX_MASKING_SALT` is supplied through a controlled local secret
  for the tokenize/redact actions and never recorded in Git or notes.
- [x] Formal masking (data-owner run) produces canonical, serving-candidate,
  manifest, and lineage artifacts without modifying the raw input.
- [x] Observed input, blank, duplicate, excluded, canonical-output, and
  serving-output row counts reconcile and any filtering or deduplication is
  explained (53 -> 53 -> 53; serving reduced to 4 columns).

## Audit and evidence

- [x] The serving-candidate post-mask audit
  (`preview_masking.py audit --scan-dir data/processed/serving/structured`)
  is clean (5 `employee_id`-pattern hits reviewed by the data owner on
  2026-09-01: `P2024xxx` are replacement-material codes, not personnel
  identifiers — recorded false positives; see notes).
- [x] Lineage sampling confirms C-level passthrough, A-level tokenize, and
  `備註` redact behavior.
- [x] A masking-log event is appended; one `run_id` joins the run manifest,
  every lineage record, and the log event, with governed source IDs and
  portable evidence paths.
- [x] The masked derivatives are registered in `source_inventory.csv` as
  masked, non-serving, review-pending (rows 175–176, user-authorized
  2026-09-01; IDs unique; conventions match the TASK001 derivative rows).
- [ ] The independent reviewer verifies the run-ID/source-ID joins and
  reconciled counts before any downstream use.

## Failure behavior

- [ ] Missing workbook, wrong sheet, wrong header, unmatched columns, missing
  required salt, empty output, or row-count mismatch fails the gate.
- [ ] A failure or a success produces no serving approval, no KG eligibility,
  no parser-candidate promotion, and no completion claim.

## Relationship to the parent parser

- [x] No parser candidate, review queue, or manifest claims the masked
  derivative as corroboration or as reviewed Route A truth.
- [x] The parser's leakage validation remains independent of masking results.
