# C1STN replacement-list masking — notes

## Status

Formal masking executed by the data owner on 2026-09-01 (run
`maskrun_20260901T034134Z_865c656a`); manifest, lineage, and masking-log
evidence verified under a user-granted bounded evidence read. The post-mask
audit's 5 `employee_id`-pattern hits were classified by the data owner as
replacement-material codes (false positives); the audit gate is closed with
that review. Derivatives are registered in `source_inventory.csv` (rows
175–176, user-authorized agent write). Remaining gate: independent evidence
review. The agent has not
opened the raw workbook, the canonical/serving artifacts, or any row values;
`data/` reads are limited to the permitted registration row and this run's
technical evidence files (manifest, lineage actions, masking-log event).
On 2026-09-01 the user additionally permitted reading the masked canonical
and serving artifacts to support the parent-parser ingestion walkthrough; the
raw workbook remains unopened by the agent.

## 2026-09-01 - implemented: subtask package recorded

### Plan

- Give the in-flight masking work a governed home as a subtask of
  `V2-TASK017` (user decision): record the implemented configuration, the
  owner-verified layout, the completed dry-run gate, and the remaining gates.
- Keep the masking track separate from the parser track: same raw source, no
  cross-promotion, no shared completion claims.

### Changed files

- `docs/tasks/V2-TASK017_material_parser_integration/subtasks/c1stn_replacement_list_masking/brief.md`
  (created)
- `docs/tasks/V2-TASK017_material_parser_integration/subtasks/c1stn_replacement_list_masking/acceptance.md`
  (created)
- `docs/tasks/V2-TASK017_material_parser_integration/subtasks/c1stn_replacement_list_masking/notes.md`
  (created)
- `configs/masking_rules.yaml` (stale row-layout comment in the
  `c1stn_replacement_list` block corrected to the owner-verified layout; no
  rule values changed)

Pre-existing uncommitted masking work from the 2026-08-27 session, now
governed by this subtask: the `c1stn_replacement_list` source block in
`configs/masking_rules.yaml` and the raw registration row in
`data/governance/source_inventory.csv` (data-owner governance write).

### Validation

- Config-only, no raw/artifact reads:
  - `python scripts/ingest/run_mask_structured.py --list-sources` lists
    `c1stn_replacement_list` with pattern
    `C1STN_bom_material/L_ReplacementList.xlsx`.
  - `python scripts/ingest/preview_masking.py rules --source c1stn_replacement_list`
    resolves all 10 columns: 4 Level C passthrough, 5 Level A tokenize/drop,
    `備註` Level A redact/drop with review flag.
- Layout alignment cross-check (code reading, no data access): masking
  `data_start = header_row(1) + 1 + skip(1)` and parser
  `data_start = header_row(1) + data_offset(2)` both start data at 0-based
  row 3 (Excel row 4).
- Bounded permission read of `source_inventory.csv` line 174 confirmed the
  registration matches the config `governance_ids` and the classification
  note quoted in the yaml block.

### Risks

- Tokenize/redact require `FAULTDX_MASKING_SALT`; a formal run without it
  must fail closed.
- `備註` free text can embed identifiers beyond column-level actions; serving
  drops it and the review flag keeps residual risk visible for the audit.
- Tokenized `單價`/`耗材QPL` remain distinguishable by hash (accepted design,
  recorded in the yaml note); they are dropped from serving regardless.
- `設備QPL`/`是否與D9X通用` linkage columns are deferred, not classified for
  retention; reintroducing them requires a new recorded owner decision.
- The dry-run count summary was reviewed by the owner but not yet captured in
  these notes; the formal manifest must still reconcile observed counts.

### State

Subtask decision state: `implemented` (configuration) with dry-run gate
passed; formal masking and evidence gates pending.

## 2026-09-01 - validated: formal run and evidence

### Run

- The data owner placed the raw workbook at the registered governed path
  (copy from the `FaultDx_local` worktree), ran formal masking from this
  worktree with `FAULTDX_MASKING_SALT` in a controlled local shell, and
  cleared the variable after the run.
- `run_id`: `maskrun_20260901T034134Z_865c656a`; masking-log event:
  `mask_20260901T034134Z_f3949cf9`; `rules_version: 2`.

### Evidence verified (bounded permission read)

- One `run_id` joins the masking-log event, the run manifest, and every
  lineage record; the log event carries the governed input/canonical/serving
  source IDs and portable manifest/lineage paths.
- Manifest counts reconcile: 53 input rows -> 53 canonical rows (10 columns)
  -> 53 serving rows (4 columns); 14 workbook columns dropped by
  `columns_keep`; no filtering or deduplication applied.
- Header resolution clean: 10/10 direct matches, 0 aliases, 0 unmatched, 0
  unused rules; sheet `工作表1`, `header_row_used: 1`.
- Lineage action summary over all 53 rows matches the configuration exactly:
  C passthrough (canonical + serving) for `自動化工站`, `耗材品名`, `耗材規格`,
  `station`; A tokenize (canonical) + drop (serving) for `品牌`, `廠商 PN`,
  `單價`, `耗材QPL`, `聯繫人`; `備註` redact (canonical) + drop (serving).
- Input fingerprint recorded by the manifest: MD5
  `6e093493622a6fa41d438159794d911f`.

### Post-mask audit — pending classification

- `preview_masking.py audit --scan-dir data/processed/serving/structured`
  reported 5 `employee_id`-pattern hits (`P2024035` on 4 rows, `P2024129` on
  1) in the serving candidate. The pattern is `[A-Z]\d{6,8}`
  (`preview_masking.py:153`).
- Structural evidence indicates false positive: the serving file contains
  only the four C-level columns (manifest `col_count: 4`); `聯繫人` was
  tokenized in canonical and dropped from serving; one value repeating across
  four material rows matches station linkage, not distinct personnel.
- The gate stays open until the data owner classifies the values. If they are
  station codes, record that review here and close the gate; if they are
  person identifiers, block the serving candidate, add a targeted rule for
  the offending column, and rerun formal masking under a new run ID.

### Resolution — data-owner classification (2026-09-01)

The data owner classified the `P2024xxx` values as codes for the replacement
materials themselves — business identifiers of the materials, not personnel
identifiers and not residual PII. The 5 audit hits are recorded false
positives of the broad `[A-Z]\d{6,8}` employee-ID pattern; the audit gate is
closed with this review.

Note for future runs: the shared audit pattern will re-flag these material
codes on every audit of this source. Re-accept them by reference to this
classification instead of re-litigating; changing the shared audit pattern is
a separate reviewed change and was not made here.

### Derivative registration (2026-09-01, user-authorized)

The user authorized the agent to register the derivatives in
`data/governance/source_inventory.csv`. Appended rows 175–176, matching the
`v2_task001_c1stn_error_code_seed` derivative conventions exactly:

- `processed__canonical__structured__c1stn_replacement_list` —
  `structured_masked_canonical`, `route_eligibility=n_a`, `serving_safe=no`,
  `masked`, `pending`, notes carry run `maskrun_20260901T034134Z_865c656a`
  and do-not-serve/do-not-promote restrictions.
- `processed__serving__structured__c1stn_replacement_list` —
  `structured_masked_serving_candidate`, same states; notes additionally
  record the audited-and-classified material-code false positives.

Verification: inventory advanced 174 -> 176 rows; all 176 `source_id` values
unique; zero blank lines; no BOM introduced; `git diff --numstat` shows the
expected 3 insertions against HEAD (the 2026-08-28 raw registration plus
these two rows). A stray blank line introduced by the append was removed with
a count-guarded byte-level collapse of the single duplicated CRLF before
verification.

### Changed files

- `docs/tasks/V2-TASK017_material_parser_integration/subtasks/c1stn_replacement_list_masking/notes.md`
  (this section) and `acceptance.md` (formal-run evidence boxes checked).

### State

Formal-run, traceability, count-reconciliation, and lineage-action gates
passed; audit classification, derivative registration, and independent review
pending.

## Data-owner gates completed

- 2026-08-27: dry-run run and reviewed by the data owner. Confirmed:
  single-sheet workbook `工作表1`; row 0 blank/title; row 1 headers; row 2
  field-description row (skipped). No unmatched columns reported.
- 2026-09-01: formal masking executed from the governed worktree with the
  controlled salt (run `maskrun_20260901T034134Z_865c656a`); post-mask audit
  run — 5 pattern hits classified by the data owner as replacement-material
  codes (reviewed false positives).

## Data-owner commands

These commands read the raw workbook or generated artifacts. The agent must
not run them under the current permission boundary.

### 1. Dry-run summary capture (rerun if counts were not retained)

```powershell
python scripts/ingest/run_mask_structured.py `
  --source c1stn_replacement_list `
  --dry-run `
  --rows 5
```

Share only the non-row summary (files, sheet, columns, matched/missing,
rows_read, rows_before/after filter/dedupe).

### 2. Formal masking (requires the controlled local salt)

```powershell
$env:FAULTDX_MASKING_SALT = "<controlled local secret>"
python scripts/ingest/run_mask_structured.py `
  --source c1stn_replacement_list
Remove-Item Env:FAULTDX_MASKING_SALT
```

### 3. Serving-candidate post-mask audit

```powershell
python scripts/ingest/preview_masking.py audit `
  --scan-dir data/processed/serving/structured
```

### 4. After the formal run

- Register `processed__canonical__structured__c1stn_replacement_list` and
  `processed__serving__structured__c1stn_replacement_list` in
  `data/governance/source_inventory.csv` (masked, non-serving,
  review-pending).
- Record the run `run_id`, manifest/lineage paths, and count reconciliation
  here; the independent reviewer then verifies the joins before any
  downstream use.
