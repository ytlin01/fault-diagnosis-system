# V2-TASK017 notes

## 2026-09-01 - released (to review): run1 frozen and handed to V2-TASK016

### Plan

- Freeze the validated `run1` candidate as the immutable review input and
  hand it to `V2-TASK016` independent validation (user decision).

### Changed files

- `docs/tasks/V2-TASK017_material_parser_integration/material_candidate_handoff_task016.md`
  (created): freeze declaration, exact command, input/config/schema/code
  fingerprints, artifact digests, candidate contents, governance state,
  reviewer instructions, and known open items.
- `docs/tasks/V2-TASK017_material_parser_integration/notes.md` (this entry)
- `docs/tasks/V2-TASK017_material_parser_integration/acceptance.md`
  (frozen-candidate handoff box checked)
- `docs/tasks/V2-TASK017_material_parser_integration/brief.md`
  (deliverable checkbox ticked)

### Freeze declaration

Run `material_cef539710b861b7d` artifacts under
`data/processed/review_pending/route_a/v2_task017_material_candidate/run1/`
are immutable from 2026-09-01. Any change to config, code, schema, input, or
output requires a new run under a new `run_id` and a new handoff. The
independent reviewer must not modify them.

### Validation

- All six frozen artifacts confirmed present in `run1/` (filename listing
  only); digests cited from the run manifest — independent digest
  re-computation is assigned to `V2-TASK016`.
- Handoff document records the reviewer's verification duties, including the
  open determinism-rerun item and the independence requirement (reviewer
  must not be the implementation author).

### Risks

- Open items carried into the handoff: real-data rerun determinism, stale
  BOM03 acceptance wording, optional candidate registration, and the masking
  subtask's independent evidence review.
- `V2-TASK016` findings may bounce the candidate back here for a new run;
  that is the designed failure path, not a defect.

### State

Task decision state: candidate frozen and handed off to independent
validation; task017 implementation work is complete pending `V2-TASK016`
review outcome.

## 2026-09-01 - validated: first real-data candidate run (complete_candidate)

### Run (data-owner executed)

- Command: `python scripts/build_graph/build_material_layer_v2_candidate.py
  --config configs/pipelines/replacement_extract.yaml --bom04
  data/raw/C1STN_bom_material/L_ReplacementList.xlsx --schema
  contracts/schema/tpdx_kg_schema_v4_2.schema.json` plus the six output
  paths under
  `data/processed/review_pending/route_a/v2_task017_material_candidate/run1/`.
- `run_id: material_cef539710b861b7d`; `run_status: complete_candidate`;
  exit 0. Salt supplied via `FAULTDX_MASKING_SALT` and cleared after the run.
- Inputs: workbook sha256
  `b80f1d845884f5747818e76fe76b44f8aeab239b61b9349663826754167facdf`;
  sheet `工作表1` auto-detected (`fell_back: false`), header at Excel row 2
  (the owner-verified layout); frozen Schema 4.2 digest matches the brief
  (`1fb4d2ad…f4310`); code fingerprint over service + CLI recorded.
- Counts: 53 consumable rows -> 52 nodes (one exact name+spec duplicate
  merged; 0 alias-collision nodes; 0 spec-missing rows); 53 station-usage
  review entries; 53 lineage records; 0 document exclusions.
- Validation: JSON schema passed; semantic passed; 23 forbidden values
  checked; `leak_count: 0`.
- Governance posture: `promotion_state: candidate`, `graph_activation:
  false`, rollback flags set — no import, no activation.

### Validation recorded here

- The manifest fingerprints config, inputs, schema, code, outputs, and
  validation results, with sha256 digests for all six artifacts.
- Station usage stayed in the review queue (decision 3) and output stayed
  node-only (decision 5); no edges were emitted.

### Risks / open

- Byte-equivalent rerun determinism on real data is not yet demonstrated; a
  rerun into a fresh output directory must reproduce `run_id
  material_cef539710b861b7d` before the determinism acceptance line closes.
- The acceptance line "Approved BOM03 and BOM04 inputs are supported
  independently" predates decision 5 (BOM03 path removed); reword it at the
  next acceptance revision rather than ticking it silently.
- The candidate artifacts are not yet registered in `source_inventory.csv`
  (optional, consistent with prior review-pending candidates).
- Next gate: freeze this run and hand candidate + manifest to `V2-TASK016`
  independent validation.

### State

Task decision state: `implemented`; first governed real-data run validated
as recorded above. Independent validation, review, and handoff pending.

## 2026-09-01 - implemented: masking subtask recorded

### Plan

- Continue the in-flight masking work as a governed subtask of this package
  (user decision): `subtasks/c1stn_replacement_list_masking/`.
- Bring the already-implemented `c1stn_replacement_list` masking source and
  the raw governance registration from the 2026-08-27 session under the task
  write set and record their gates.

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
- `docs/tasks/V2-TASK017_material_parser_integration/brief.md` (decision 6,
  masking scope bullet, write-set extension, data-permission paragraph)
- `docs/tasks/V2-TASK017_material_parser_integration/acceptance.md` (masked
  derivative subtask section)
- `docs/tasks/V2-TASK017_material_parser_integration/notes.md` (this entry)

### Validation

- Config-only rule resolution for `c1stn_replacement_list` passed: 10
  columns resolved (4 Level C passthrough; 5 Level A tokenize/drop; `備註`
  Level A redact/drop with review flag); the source appears in
  `run_mask_structured.py --list-sources`.
- Layout alignment cross-check by code reading (no data access): masking
  `header_row(1) + 1 + skip(1)` and parser `header_row(1) + data_offset(2)`
  both start data at 0-based row 3 (Excel row 4).
- Bounded permission read of the single new `source_inventory.csv` row
  (`raw__C1STN_bom_material__L_ReplacementList`, line 174) confirmed the
  registration matches the config `governance_ids` and the owner
  classification note quoted in the yaml block.
- No raw workbook, masking artifact, or other `data/` file was opened.

### Risks

- Formal masking (requires `FAULTDX_MASKING_SALT`), post-mask audit,
  masking-log evidence, and derivative registration remain data-owner gates;
  the dry-run gate was owner-run and reviewed 2026-08-27.
- Masking derivatives and parser candidates are co-source on the same raw
  workbook; neither promotes or corroborates the other.

### State

Task decision state: `planned`; the masking track is now recorded as subtask
`c1stn_replacement_list_masking` (implemented configuration, dry-run gate
passed, formal gates pending).

## 2026-08-27 - implemented: scope reduced to the BOM04 replacement list only

### Plan

- Record the data-owner decision (brief decision 5): process only the
  governed BOM04 replacement list (`L_ReplacementList`); remove the BOM03
  spare-BOM path, topology endpoint resolution, and `REPLACEMENT_FOR`
  edge emission. Keep output node-only with review-queue semantics.
- Apply the same reduction to config, service, runner, and synthetic tests.

### Changed files

- `configs/pipelines/replacement_extract.yaml` (renamed from
  `material_extract_v2.yaml`; bom03/relationships/topology_endpoint
  sections removed; `equipment_col` made optional and dropped from config;
  `單價`/`耗材QPL` added to sensitive_columns from the approved
  L_ReplacementList column classification)
- `services/ingestion/material_layer_v2.py` (hierarchy/topology/edge
  machinery removed; `build_material_layer` now takes the single BOM04
  extraction; `_schema_exclusions` now returns exclusion dicts — fixes a
  latent runner crash on the blocked-by-exclusions path)
- `scripts/build_graph/build_material_layer_v2_candidate.py` (CLI is
  `--bom04` only; `--bom03`/`--topology-index` removed)
- `tests/unit/test_material_layer_v2.py` (bom04-only coverage; new
  legacy-flag rejection test; blocked-by-exclusions path covered via
  name-only identity config)
- `docs/tasks/V2-TASK017_material_parser_integration/brief.md` (goal,
  scope, mapping table, decision 5)

### Validation

- `pytest tests/unit/test_material_layer_v2.py`: 19 passed, 4 subtests
  passed (synthetic fixtures only; no file under `data/` read).
- Blocked-by-exclusions CLI path reproduced manually before/after the
  exclusion-dict fix: returncode 3 then 0 with `--allow-exclusions`.
- The two pre-existing CLI test failures (runner required
  `--topology-index` with `--bom03` even for `--inspect`) are resolved by
  removal of the bom03 path.

### Risks

- Node-only output: no source currently feeds `REPLACEMENT_FOR` edges;
  reintroducing edges requires a new recorded decision and a governed
  topology source (brief decision 5).
- `bom04.source_id` is bound to the governance id
  `raw__C1STN_bom_material__L_ReplacementList` (user decision 2026-08-27);
  lineage anchors and manifests now reference the registered source
  directly. Done before any real-data run, so no existing artifacts are
  invalidated.

### State

Task decision state: `planned`; implementation now bom04-only as recorded
above. Real-data execution still waits for explicit bounded permission,
governed paths, and salt ownership.

## 2026-08-10 - task identity repaired

### Plan

- Make the active material-parser package identity consistently `V2-TASK017`.
- Preserve the separate unified data-package manifest task as its own package
  identity.

### Changed files

- `docs/tasks/V2-TASK017_material_parser_integration/brief.md`
- `docs/tasks/V2-TASK017_material_parser_integration/acceptance.md`
- `docs/tasks/V2-TASK017_material_parser_integration/notes.md`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/brief.md`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`

### Validation

- Confirmed no remaining legacy material-parser task-path references.
- Confirmed Task 016 names `V2-TASK017` as the material-parser candidate
  supplier and review input.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.

### Risks

- Task 017 remains `planned`; implementation and real-data gates are unchanged.

### State

Task decision state: `planned`.

## 2026-07-31 - planned

### Plan

- Treat the user-confirmed material-schema compatibility review as completed
  upstream work and require its authoritative artifact to be named before
  implementation.
- Reimplement the cleaned S parser behavior against the current v2 contract
  boundary rather than restoring historical Schema v4.0.
- Begin with synthetic fixtures and fail-closed validation.
- Stop before real-data access, graph import, activation, or release.

### Changed files

- `docs/tasks/V2-TASK017_material_parser_integration/brief.md`
- `docs/tasks/V2-TASK017_material_parser_integration/acceptance.md`
- `docs/tasks/V2-TASK017_material_parser_integration/notes.md`

### Validation

- Confirmed the active material-parser package identity is `V2-TASK017`.
- Reviewed the pipeline/KG role boundary and active v2 task contract.
- The cleaned S handoff's focused synthetic suite was independently rerun on
  2026-07-31: 22 tests passed.
- No real BOM, base-triple, alias, salt, or generated-output content was read.

### Risks

- The completed compatibility decision has not yet been named in the active
  task package.
- Historical parser output targets Schema v4.0 and cannot be adopted unchanged
  under the Schema 4.2 working baseline.
- Salt ownership, approved base triples, controlled aliases, match calibration,
  and production-like security review remain open.

### State

Task decision state: `planned`.
