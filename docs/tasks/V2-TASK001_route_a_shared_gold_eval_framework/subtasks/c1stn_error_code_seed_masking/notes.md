# C1STN error-code seed masking — notes

## Status

Traceability remediation is implemented and code-validated without agent data
access. Earlier formal masking outputs and governance registration were
reported by the data owner, but the latest corrective rerun failed before a new
masking-log event was appended. The candidate is not annotation-ready. A fresh
data-owner formal run, post-audit, and independent evidence review remain
required. The agent has not opened the workbook or generated artifact contents.

## Remediation TODO

- [x] Distinguish the inherited Phase 1/N method from current A/data-line
  implementation and governance ownership.
- [x] Define masking run manifest, row/field lineage, canonical governance
  records, and Data RC integration manifest as separate artifact classes.
- [x] Configure distinct governed input, canonical, and serving source IDs.
- [x] Generate one shared run ID for the run manifest, lineage, and masking-log
  event.
- [x] Store portable manifest and lineage pointers in new masking-log events.
- [x] Remove machine hostname metadata from new masking run manifests.
- [x] Preserve backward readability of historical append-only masking-log
  records.
- [x] Add temporary-fixture regression coverage for run-ID propagation,
  governed source IDs, evidence pointers, and hostname exclusion.
- [ ] Data owner reruns formal masking after the traceability and BOM fixes.
- [ ] Data owner repeats the serving-candidate post-audit.
- [ ] Independent reviewer verifies run-ID/source-ID joins, reconciled counts,
  lineage actions, portable paths, and masking-log evidence.
- [ ] Update the remaining acceptance boxes only after that evidence review.
- [ ] Create the provisional annotation seed only after explicit annotation-use
  approval.

## Data-owner inspection metadata

- Workbook: `C1STN Error code.xlsx`
- Selected sheet: `CG7`
- Dimension reported by the dedicated inspector: 224 data rows by 6 columns
- Header: Excel row 1, represented as `header_row: 0` in the zero-based
  configuration
- Directly matched columns:
  - `Error Description`
  - `Code`
  - `Category`
  - `Error Description (Chinese)`
  - `Repair Actions`
  - `Local Alarm Code`
- Direct rule matches: 6
- Alias matches: 0
- Unmatched columns: 0
- Unused rules: 0

The dedicated inspector reports 224 data rows after the header, resolving the
earlier worksheet-dimension ambiguity. This still differs from the informal
225-row description. The formal manifest must report the observed data, blank,
duplicate, excluded, and output counts; no count may be silently forced to
225.

## Masking classification consequence

All six discovered columns are diagnostic Level C fields under the Phase 1
method. They pass through in both canonical and serving-candidate views.
Therefore the structured run does not itself redact their values.

`Error Description`, `Error Description (Chinese)`, and `Repair Actions` are
review-flagged because free text may contain embedded identifiers or sensitive
operational context. If the local dry-run finds such content, formal masking is
blocked until a targeted rule or approved local preprocessing step is added.
The serving-candidate output is not serving-safe merely because the pipeline
ran successfully.

## Plan

1. The data owner runs the exact-file header-only inspection.
2. Review the sanitized header report and select the sheet/header row.
3. Add the dedicated `v2_task001_c1stn_error_code_seed` source rule.
4. Validate rule resolution without data access.
5. The data owner runs and locally reviews a five-row dry-run.
6. Resolve every unmatched/unused rule and rerun the dry-run.
7. Run formal masking locally.
8. Review manifest, lineage, audit results, and governance state.
9. Build a 10–15-case provisional annotation seed.

## Data-owner commands

The following commands read the raw workbook. The agent must not run them under
the current permission boundary.

### 1. Bootstrap header-only inspection

Use the existing Phase 1 `error_codes_raw` rule only as an inspection template:

```powershell
python scripts/ingest/run_mask_structured.py `
  --source error_codes_raw `
  --raw-dir data/raw `
  --file-patterns "C1STN_error_data/C1STN Error code.xlsx" `
  --inspect
```

Share only the sanitized sheet/header report: sheet names, dimensions, selected
header row, column names, matched aliases, unmatched columns, and unused rules.
Do not share row values.

### 2. After the dedicated source rule is added

Config-only rule review:

```powershell
python scripts/ingest/preview_masking.py rules `
  --source v2_task001_c1stn_error_code_seed
```

Header verification:

```powershell
python scripts/ingest/run_mask_structured.py `
  --source v2_task001_c1stn_error_code_seed `
  --inspect
```

Local five-row dry-run:

```powershell
python scripts/ingest/run_mask_structured.py `
  --source v2_task001_c1stn_error_code_seed `
  --dry-run `
  --rows 5
```

Do not paste the data-preview portion outside the controlled environment.

Formal masking, only after review:

```powershell
python scripts/ingest/run_mask_structured.py `
  --source v2_task001_c1stn_error_code_seed
```

Serving-candidate audit:

```powershell
python scripts/ingest/preview_masking.py audit `
  --scan-dir data/processed/serving/structured
```

## Implemented

- Subtask package created.
- Added the dedicated `v2_task001_c1stn_error_code_seed` source to
  `configs/masking_rules.yaml`.
- The source matches only
  `C1STN_error_data/C1STN Error code.xlsx`, uses zero-based `header_row: 0`,
  allowlists the six reported columns, and review-flags the three free-text
  columns.
- No masking pipeline implementation changed.
- No generated data artifact was created.

## Validation

- `origin/phase1_v1` structured masking method was inspected from Git without
  checking out or modifying the branch.
- The current masking CLI exposes config listing, rule review, inspection,
  dry-run, file-pattern override, sheet/header override, and formal execution.
- The dedicated source appears in `--list-sources`.
- Config-only rule resolution reports six Level C rules and three
  review-flagged columns.
- Python compilation of the structured masking service and CLIs passed.
- No file under `data/raw/` and no XLSX file was opened.

## Risks

- The workbook may not use the Phase 1 `error_codes_raw` headers.
- Free text can contain embedded sensitive content beyond regex detection.
- The serving audit scans known identifier patterns but does not replace human
  review.
- A Phase 1 canonical view may preserve internal B/C values and is not a
  serving release.
- Masking may change the usable row count through blank-row removal or
  deduplication; the manifest must explain the difference.

## Failed gate — exact-path discovery

The first data-owner-run dedicated inspection failed before opening the
workbook:

```text
FileNotFoundError: No files found matching
['C1STN_error_data/CGSF Error code.xlsx'] in .../data/raw
```

This is a path-discovery failure, not a schema, masking, or workbook-content
failure. Formal masking remains blocked. The data owner must verify the exact
literal filename/path locally; the agent remains prohibited from listing or
inspecting `data/raw/`.

Resolution: the data owner corrected the path to
`data/raw/C1STN_error_data/C1STN Error code.xlsx`. The dedicated configuration,
subtask name, and governance identifier were updated before any masking output
was created.

The data owner then reran the dedicated inspection successfully:

```text
sheet=CG7
data_rows=224
columns=6
header_row=0
matched=6
alias=0
unmatched=0
unused_rules=0
```

The path/header gate is resolved. The next gate is the local five-row dry-run;
formal masking remains blocked until the dry-run summary and free-text
sensitivity review are recorded.

## Validated — local dry-run gate

The data owner reported the following non-row dry-run summary:

```text
files=1
sheet=CG7
columns_keep=6
matched_columns=6
missing_columns=0
rows_read=224
rows_before=224
rows_after_filter=224
rows_after_dedupe=224
```

No rows were filtered or deduplicated. The data owner's bounded content review
found expected diagnostic error/alarm codes in free text but no names, person
identifiers, contact information, private paths, or sensitive operational
context.

The formal masking gate is cleared for data-owner execution. All configured
actions are Level C passthrough, so this source does not require
`FAULTDX_MASKING_SALT`. Formal execution still produces governed canonical and
serving-candidate views, manifest, lineage, and masking evidence; it does not
make the output serving-safe or promote any source cause/action to gold.

## Implemented — formal output locations

The data owner ran formal masking. Filename/size/timestamp metadata only was
used to locate the outputs; no generated artifact content was opened:

- canonical:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/v2_task001_c1stn_error_code_seed_canonical.json`
- serving candidate:
  `data/processed/serving/structured/v2_task001_c1stn_error_code_seed_serving.json`
- manifest:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/_manifests/v2_task001_c1stn_error_code_seed_manifest_20260723T183917.json`
- lineage:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/_lineage/v2_task001_c1stn_error_code_seed_lineage_20260723T183917.jsonl`
- governance summary:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/_governance/v2_task001_c1stn_error_code_seed_governance.json`

Formal-output existence is implemented, not yet content-validated. Row-count
reconciliation, manifest/lineage review, serving audit, masking-log evidence,
and derivative inventory registration remain pending.

## Validated — data-owner post-audit

The data owner manually corrected the audit scan path to
`data/processed/serving/structured` and reported that the post-mask audit was
clean. No artifact content or audit snippet was supplied or independently
inspected.

This clears the automated residual-pattern audit gate, but it does not set
`serving_safe=yes`, review the diagnostic semantics, or promote source labels
to gold.

## Implemented — derivative inventory registration

Registered in `data/governance/source_inventory.csv`:

- `processed__canonical__structured__v2_task001_c1stn_error_code_seed`
- `processed__serving__structured__v2_task001_c1stn_error_code_seed`

Both remain non-route-eligible, non-serving, masked candidates with
`reviewed_status=pending`. Inventory row count advanced from 151 to 153, and
both new source IDs are unique.

Still pending:

- manifest and lineage content review;
- masking-log evidence verification;
- approval of the masked derivative for annotation use; and
- deterministic generation of the 10–15-case provisional annotation seed.

## Validation finding — non-portable run references

Bounded evidence review confirmed:

- manifest counts: 224 input, 224 canonical, 224 serving;
- no unmatched/unused headers, filtering, or deduplication;
- first 10 lineage records use Level C passthrough and the configured review
  flags;
- masking-log event `mask_20260723T103917Z_3776060f` exists.

The same review found that the manifest stored machine-absolute, obsolete
output paths, and the masking-log event stored an obsolete canonical path.
Those references do not match the actual governed zone topology. The run is
therefore not yet accepted as annotation-ready even though its counts and
post-audit passed.

### Implemented fix

- `services/ingestion/structured_masking.py` now labels canonical, serving, and
  governance-summary references relative to the run's governed root.
- `services/ingestion/manifest.py` normalizes stored path labels to portable
  forward-slash references.
- `tests/unit/test_name_mapping.py` asserts portable canonical, serving, and
  governance-summary paths.

### Validation

- `python -m unittest tests.unit.test_name_mapping` — 9 tests passed.
- Python compilation passed.
- `git diff --check` passed for the implementation and regression-test files.

A data-owner formal rerun and post-audit are required to regenerate consistent
manifest and masking-log evidence. The historical event remains append-only
and visible.

## Failed gate — masking-log UTF-8 BOM

The first rerun after the portable-path fix regenerated masking outputs but
failed while checking the append-only masking log:

```text
JSONDecodeError: Unexpected UTF-8 BOM
```

The failure occurred after masking output generation and before a new
masking-log event was appended. Raw input was not modified.

### Implemented fix

- `services/governance/storage.py` now reads JSONL with `utf-8-sig`, which
  accepts both ordinary UTF-8 and a legacy BOM without rewriting the log.
- `tests/unit/test_operational_governance_logs.py` includes a BOM regression
  case.

### Validation

- Direct temporary-file BOM JSONL read — passed.
- Structured masking/name-mapping regression suite — 9 tests passed.
- Python compilation and `git diff --check` passed.
- The normal operational-governance pytest suite was not run because `pytest`
  is unavailable in the active environment.

The data owner must rerun formal masking once more so the corrected run can
append a new masking-log event. The post-audit must then be repeated against
the regenerated serving candidate.

## Implemented — masking evidence traceability remediation

The handoff/overlap review identified that run-local evidence and canonical
governance had distinct intended authority but insufficient join keys. The
following compatibility extension is implemented:

- one generated `run_id` is propagated to the masking run manifest, every
  row/field lineage record, and each canonical masking-log event;
- masking-log events now distinguish the masking configuration name from
  governed input, canonical, and serving source IDs;
- masking-log events now include portable `manifest_path` and `lineage_path`
  references;
- `source_id` remains as a compatibility alias for `input_source_id`, so
  historical consumers and append-only rows do not require rewriting;
- the V2-TASK001 masking configuration names its three governed inventory IDs;
- new run manifests omit hostname metadata;
- structured and unstructured manifest/lineage paths are portable; and
- task wording distinguishes the inherited Phase 1/N method from current
  A/data-line ownership and distinguishes masking run manifests from a future
  Data RC integration manifest.

No canonical governance record or generated data artifact was modified by this
implementation work.

### Validation

- Python compilation for the affected ingestion, governance, CLI, and test
  modules — passed.
- `python -m unittest tests.unit.test_name_mapping
  tests.unit.test_masking_run_traceability` — 11 tests passed.
- Config-only V2-TASK001 rule resolution — passed: six Level C columns resolved,
  with the expected three review flags.
- `git diff --check` and trailing-whitespace checks for the new task/test files
  — passed.
- `tests/unit/test_operational_governance_logs.py` was not executed because
  `pytest` is unavailable in the active Python environment; equivalent new
  masking traceability behavior is covered by the unittest module.

### Remaining gate

Code validation does not validate the current files under `data/`. The data
owner must perform the fresh formal run and post-audit, after which an
independent reviewer must verify that the manifest, lineage, and new
masking-log event share the same run ID and governed source IDs.

## Current handoff - corrected formal run and provisional seed

The data owner reran formal masking after the portable-path and BOM fixes. The
explicitly authorized bounded evidence review confirmed manifest
`v2_task001_c1stn_error_code_seed_manifest_20260723T195218.json`, masking-log ID
`mask_20260723T115218Z_c9f59e08`, clean post-mask audit, and 224 input,
canonical, and serving-candidate rows across six columns. No raw workbook was
opened.

The regenerated evidence uses governed relative paths. It is suitable only as
a masked, development-only annotation input; it is not serving-safe, Route A
truth, or an approved gold-label source.

### Implemented - deterministic annotation seed

`services/evaluation/route_a_golden_seed.py` and
`scripts/eval/build_route_a_annotation_seed.py` build a deterministic 15-case
review queue at
`data/processed/review_pending/route_a/v2_task001_c1stn_error_code_annotation_seed_v1.json`.
Selection covers observed category variants, code shapes, duplicate-code cases,
and repair-action diversity. Each case has `source_suggested_only` context and
no accepted label. The seed SHA-256 is
`f2b40fb42747f26881d8058abc6afd6f2780b48c361472fe501065f6d1331073`.

The seed is registered in `data/governance/source_inventory.csv` as
`processed__review_pending__route_a__v2_task001_c1stn_error_code_annotation_seed_v1`,
with `serving_safe=no`, `masking_status=masked`, and `reviewed_status=pending`.
It may not be served, ingested into the KG, or evaluated as gold.

### Validation

- `python -m unittest tests.unit.test_route_a_golden_seed tests.unit.test_route_a_golden_annotation tests.unit.test_name_mapping` - 22 tests passed.
- Seed validation, deterministic rebuild, Python compilation, and `git diff --check` passed.

## Next gate

Before annotation, provide the controlled cause and repair-action ID vocabulary
or approve a governed proposal workflow for new IDs. Independent expert review
and later adjudication are separate gates before any gold or evaluation use.
