# V2-TASK015 notes

## 2026-07-31 - planned

### Plan

- Treat S's cleaned complete A/B/C handoff as candidate source material and the
  smaller `feature/material-layer` subset as comparison input.
- Selectively reimplement the pipeline within current v2 governance and contract
  boundaries.
- Validate synthetically first and stop before all approved local-data reads.
- Preserve preview/write gates, missingness, manual-review debt, audit blocking,
  and rollback.

### Changed files

- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/brief.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/acceptance.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/notes.md`

### Validation

- Confirmed `V2-TASK015` was unused before allocation.
- Reviewed the pipeline/KG role boundary and S handoff source accounting.
- Confirmed the external handoff includes B02, C01, C02, Tasks 044-045, vector
  diagnostics, and manual-override governance absent from S's branch subset.
- The current environment could not collect the handoff synthetic suite because
  `PyMuPDF`/`fitz` is unavailable; the handoff's seven-pass report remains
  historical evidence only.
- No drawing, classification, BOM, relationship, or generated-output content
  was read.

### Risks

- The historical branch and cleaned handoff contain different implementations;
  source accounting is required before code selection.
- Real template, vector, OCR, BOM, and relationship quality remains unvalidated.
- Final project-owner field naming needs affected-consumer approval.
- High-priority B02 findings and unknown child types must remain visible.

### State

Task decision state: `planned`.

## 2026-08-08 - reconciled after completed human review

### Plan

- Reconcile the live branch and recoverability before accepting prior Task 015
  work as current.
- Validate the completed 54-record human review without exposing protected
  identifiers or mutating the review artifact.
- Serialize Phase 1 governance before contract or pipeline restoration.

### Changed files

- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/reconciliation_report_2026-08-08.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/notes.md`

### Validation

- Confirmed branch `feature/v2-data-pipeline` at startup HEAD `724b332` and
  preserved the pre-existing untracked continuation handoff and
  `reference_work/`. An unrelated user commit advanced local HEAD to `7a0fd61`
  during reconciliation and does not overlap Task 015 or governance paths.
- Found a selectively recoverable implementation candidate at `kg_pipeline`
  commit `ee3316a`; no whole-commit cherry-pick is safe because that commit has
  broad unrelated repository deletions.
- Confirmed zero Task 015 matches in all five canonical governance files.
- Validated 54 unique review records and 54 matching PDF digests: 8 `asm`, 44
  `prt`, and 2 `exclude`; all required human decision metadata is present.
- Confirmed the completed review file is valid JSON with SHA-256
  `997e28ef1252a967c6433c3c41064ce0bfab5613a4be332282f844c60e6c98a1`.
- Did not access `data/raw/` and did not send protected data externally.

### Risks

- Phase 1 canonical governance registration remains incomplete.
- The source review schema still omits `exclude` and reports a pending review
  state; preserve it as evidence and use a derived contract-valid projection.
- The 507-PDF redaction package remains non-serving and KG-ineligible pending
  independent whole-document review.
- Recovered code is candidate material only until selectively restored,
  adapted to the reviewed contract, and revalidated.

### State

Reconciliation is `validated`. Task decision state remains `planned`; Phase 1
inventory/governance is the next gate and is owned by `data_workflow_lead`.

## 2026-08-08 - Phase 1 inventory and governance implemented and validated

### Plan

- Register only the four bounded Task 015 sources proven by current local
  evidence.
- Restore masking and annotation events without fabricating a historical run,
  serving approval, index, or evaluation.
- Preserve all local artifacts as non-serving candidates and pass Phase 2 to
  the contract engineer.

### Changed files

- `data/governance/source_inventory.csv`
- `data/governance/masking_log.jsonl`
- `data/governance/annotation_log.jsonl`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/acceptance.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/reconciliation_report_2026-08-08.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/notes.md`

### Validation

- `source_inventory.csv` parses with 165 unique source IDs and exactly four
  Task 015 registrations; SHA-256 is
  `376df3d4529de72b56cef8fbc0a02929243d5cdc3317c4ab136b3df8dd0810f5`.
- `masking_log.jsonl` parses with five events and one Task 015 event; SHA-256 is
  `95f8c5d0da3cf77bd7dd8fafd68758f0e89fa00ebdc2c79afdc54393f6ce70ed`.
- `annotation_log.jsonl` parses with three events and two Task 015 events;
  SHA-256 is
  `7c2e1504a073710c8785d6264f1c6f46afb62706e9998c2aa86392659e51cf9d`.
- All new Task 015 records are non-serving; masking and annotation events are
  KG-ineligible and contain no `data/raw/` reference.
- `index_registry.jsonl` and `eval_run_log.jsonl` were unchanged because no
  index or evaluation run occurred.
- `git diff --check` passed.

### Risks

- Phase 1 registration is evidence-backed governance, not an independent
  whole-document security review or serving approval.
- The completed review still requires a derived governed projection;
  its immutable source file was not changed.
- Historical outputs and recovered code remain candidates only.

### State

Phase 1 inventory/governance is `implemented` and `validated`. It is not an
independent quality review or release. Next serialized owner is
`data_contract_engineer` for Phase 2.

## 2026-08-08 - Phase 2 classification rules validated

The immutable derived projection and behavioral tests validated `exclude`,
explicit multi-view grouping, multi-page identity, distinct occurrences, and
source/PDF provenance without changing the completed v1 review evidence. The
rules then awaited the user's direct decision.

## 2026-08-08 - Phase 2 rules approved directly; stale contracts removed

The user directly approved the following Task015 rules:

- classifications are `ASM`, `PRT`, and `exclude`;
- excluded drawings never enter BOM or KG output;
- explicitly reviewed multi-view drawings may share one definition;
- a multi-page drawing remains one definition;
- individual BOM occurrences remain distinct and retain source/PDF provenance.

This direct decision completes the Phase 2 decision gate. At the user's
request, the stale standalone `manual_classification_review_v2_contract.md`,
`manual_classification_review_v2.schema.json`, and their schema-only unit test
were removed. Behavioral enforcement remains in the pipeline implementation
and focused pipeline/projection tests. The obsolete `REVIEWED_PROPOSAL` marker
was removed from newly generated projections.

This approval does not accept a B02 finding, promote data, activate the KG, or
change the Phase 3 candidate's blocked state.

## 2026-08-08 - Phase 3 implementation restored; candidate blocked at B02

### Plan

- Selectively restore only Task 015 blobs from recovery commit `ee3316a`.
- Implement the immutable v1-to-v2 projection and `exclude` non-promotion
  semantics before real candidate runs.
- Run preview-first A01, A03, governed historical B01 reuse, and fresh B02;
  fail C01 closed on unresolved blockers.

### Changed files

- `configs/pipelines/cad_2d_pipeline_v2.yaml`
- `services/ingestion/cad_2d_pipeline_v2/`
- `scripts/pipelines/cad_2d_v2/`
- `tests/unit/cad_2d_v2/`
- `data/governance/source_inventory.csv`
- `data/governance/annotation_log.jsonl`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/acceptance.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/reconciliation_report_2026-08-08.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/notes.md`

Local ignored outputs created under:

- `data/processed/review_pending/route_a/v2_task015_cad_2d_manual_classification_review_v2/`
- `data/processed/review_pending/route_a/v2_task015_cad_2d_pipeline_v2_candidate/`

### Validation

- 34 Task 015 tests passed; two PyMuPDF redaction tests were skipped because
  that optional dependency is unavailable.
- Real v2 projection preview/write passed with 54 records, zero unresolved,
  four explicit shared-view members, one multi-page record, and two excluded
  records.
- A01 preview/write passed with 507 outputs: 453 historical records plus 54
  governed reviewed additions.
- A03 preview/write passed with 507 outputs, zero missing fields, and zero
  field-only identifiers.
- B01 preview/write retained only reviewed ASM: 32 governed historical
  structured BOM parents were reused; eight newly reviewed ASM lack source
  extraction and remain visible findings. This is not claimed as a fresh PDF
  extraction.
- Fresh B02 preview/write produced 36 blocking findings: 25 suspicious
  identifiers, 9 classification/empty-BOM, and 2 blank part numbers.
- C01 preview failed closed with `count=36`; C02 did not run.
- Canonical governance parses with 167 inventory rows (six Task 015), five
  masking events (one Task 015), and four annotation events (three Task 015).
- `git diff --check` passed.

### Risks

- The eight newly reviewed ASM require governed BOM extraction or explicit
  reviewed decisions; current local Python lacks PyMuPDF and no extraction was
  invented.
- The 25 suspicious identifiers and two blank part numbers require domain/source
  review; no blanket regex override is authorized.
- C01/C02, 2D-to-3D reconciliation, frozen-candidate creation, Task 016 handoff,
  graph activation, and release remain blocked.
- Two unrelated user commits and separate workflow-system edits appeared during
  this work; they were preserved and not included in Task 015 changes.

### State

Phase 3 implementation is `implemented` and synthetically `validated`; the
real candidate is `blocked_by_b02` with 36 current findings. Task 015 remains
`planned`, not frozen, reviewed, or released.

## 2026-08-08 - PDF-assisted B01 refinement and complete B02 inventory

### Plan

- Use the repository virtual environment for local-only PDF extraction and
  representative visual validation under the recorded bounded permission.
- Combine governed historical structured BOM evidence with fresh PDF-derived
  candidates only for uncovered reviewed ASM.
- Carry B01 extraction exclusions into B02 and C01 recomputation; do not invent
  values or relax audit rules.

### Changed files

- `scripts/pipelines/cad_2d_v2/extract_reviewed_asm_words.py`
- `scripts/pipelines/cad_2d_v2/run_stage.py`
- `services/ingestion/cad_2d_pipeline_v2/__init__.py`
- `services/ingestion/cad_2d_pipeline_v2/stages.py`
- `tests/unit/cad_2d_v2/test_cli.py`
- `tests/unit/cad_2d_v2/test_pipeline.py`
- `data/governance/source_inventory.csv`
- `data/governance/annotation_log.jsonl`
- this task's `acceptance.md`, `notes.md`, and reconciliation report

Local ignored outputs were added under candidate `B00/`, `B01_combined/`, and
`B02_combined/`.

### Validation

- The repository virtual environment passed all 36 remaining Task 015 tests,
  including
  PyMuPDF-dependent tests; package compilation passed.
- All eight reviewed ASM PDFs were locally hash-verified and their configured
  BOM pages extracted. Visual inspection found readable BOM tables for seven.
  All three pages of the reviewed multi-page assembly were inspected and none
  contains a BOM table, so it remains an explicit reliable-header blocker.
- Combined B01 contains 39 parents: 32 governed historical structured reuse and
  seven fresh PDF-derived candidates. One of 40 reviewed ASM remains unresolved.
  B01 retains 219 extraction findings instead of discarding difficult rows.
- Fresh combined B02 contains 266 findings, of which 261 are blocking: 201
  `INVALID_BOM_QUANTITY`, 17 `BLANK_BOM_PART_NUMBER`, 38
  `SUSPICIOUS_IDENTIFIER`, 2 `BLANK_PART_NUMBER`, 2
  `CLASSIFICATION_OR_EMPTY_BOM`, 1 `RELIABLE_BOM_HEADER_NOT_FOUND`, and 5
  non-blocking `ITEM_SEQUENCE_GAP` warnings.
- C01 recomputed the same B02 inputs and failed closed with `count=261`; C02 was
  not run.
- Combined B01 result SHA-256 is
  `232bb19c0e404f50ae398ab7d2057c0654040b825db9e392644c3ecb7953c7c1`;
  combined B02 result SHA-256 is
  `1729d868490816cd87222eaaaf13ee0380eb461002617a80b827638456533f37`.

### Risks and state

- The large extraction-finding set shows that the geometry parser is only a
  candidate and requires template/domain review; no excluded row was promoted.
- The 38 suspicious identifiers and two blank part numbers require source or
  domain decisions. No automatic override or regex relaxation was applied.
- Phase 3 code is synthetically validated, but the data candidate remains
  `blocked_by_b02`. It is not frozen, handed to Task 016, reviewed for Data RC,
  serving eligible, KG eligible, or released.
- Final governance validation parsed 167 unique inventory rows, five annotation
  events, and five masking events. SHA-256 values are
  `d6495cf3af920e05a3f4efbacec1af005fd6bdb50e7673560dce4fcde5fc60a8`
  (`source_inventory.csv`),
  `dceb6d6339f2c27b6892c4b10686f53cc67c1eeb8ef8b1e28945542f564b7aa4`
  (`annotation_log.jsonl`), and
  `95f8c5d0da3cf77bd7dd8fafd68758f0e89fa00ebdc2c79afdc54393f6ce70ed`
  (`masking_log.jsonl`).
- Independent adversarial code re-review found no remaining high/blocking
  findings. The reviewer confirmed that forged B00 bundles are rejected by the
  pinned canonical bundle digest and pinned source/projection lineage checks,
  and classified the scoped B00/combined-B01 implementation as code-review
  ready. This does not change the real candidate's B02-blocked state.

## 2026-08-08 - Phase 3 fail-closed BOM parser refinement

### Plan

- Remove false findings caused by parsing all drawing text below a BOM header.
- Validate quantity and part-number cell ownership geometrically without
  inventing or silently joining cross-row content.
- Regenerate B01/B02 and keep C01 closed on every unresolved finding.

### Changed files

- `configs/pipelines/cad_2d_pipeline_v2.yaml`
- `services/ingestion/cad_2d_pipeline_v2/config.py`
- `services/ingestion/cad_2d_pipeline_v2/stages.py`
- `tests/unit/cad_2d_v2/test_pipeline.py`
- Task015 notes/reconciliation and canonical governance evidence

### Validation

- PDF visual/geometry QA showed that the original 219 extraction findings were
  dominated by title-block, drawing-callout, optional-description-column, and
  wrapped-cell parsing errors.
- The final safe parser accepts only same-row, center-owned item, part, and
  quantity tokens. Unattached part-column lines and ambiguous headers fail
  closed rather than being concatenated into valid-looking identifiers.
- The repository virtual environment passed 41 Task015 tests, including
  adversarial neighboring-column, between-row, and post-last-row continuation
  cases.
- Latest B01 has 38 parents: 32 governed historical and six fresh PDF-derived.
  Two reviewed ASM remain unresolved. Its 17 explicit findings are seven blank
  extracted part numbers, six ambiguous continuations, two invalid quantities,
  and two reliable-header failures. Canonical result SHA-256:
  `d6d4983083e02d3e25978fd0630a30f8ca20e689165290e06a5a7389187ca16d`.
- Latest B02 has 62 findings, 60 blocking: 38 suspicious identifiers, seven
  blank extracted part numbers, six ambiguous continuations, three
  classification/empty-BOM findings, two invalid quantities, two historical
  blank part numbers, two reliable-header failures, and two non-blocking item
  sequence gaps. Canonical result SHA-256:
  `ed102725d501f9afba58ac086120b99b44e67533959f7c49322bfbdb4c3f2d62`.
- C01 recomputed the same input set and failed closed with `count=60`; C02 was
  not run.

### State and risks

- This supersedes the earlier 261-blocker parser candidate; that older count is
  historical evidence, not current status.
- Remaining findings require source/domain review. No identifier-pattern
  relaxation, cross-row merge, manual value invention, or risk acceptance was
  applied.
- Phase 3 remains `blocked_by_b02`; it is not frozen, promotable, serving/KG
  eligible, handed to Task016, or released.

### Independent review

- Independent adversarial code review found no remaining high or blocking
  parser defects. The wide optional-column overlap, between-row continuation,
  and post-last-row continuation probes all fail safely; the implementation is
  code-review ready.
- Independent quality review reproduced B01 and B02 exactly, verified the
  manifest and provenance chain, passed 41 focused tests, compilation, and
  `git diff --check`, and confirmed C01 fails closed with 60 blockers.
- Review decision: pipeline safety evidence is acceptable, but the r9 data
  candidate is `NOT_READY` for promotion or release until all 60 blocking
  findings receive governed source/domain review and a new frozen candidate is
  independently reviewed.

## 2026-08-10 - Phase 3 r10 governed blocker resolution (B02 60 → 0)

### Decision

- The 60 B02 r9 blocking findings were triaged into three governed classes per
  user-approved plan `distributed-singing-dijkstra.md`:
  1. **17 source-anchored extraction findings** (7 `BLANK_BOM_PART_NUMBER`,
     6 `AMBIGUOUS_BOM_PART_CONTINUATION`, 2 `INVALID_BOM_QUANTITY`, 1
     `RELIABLE_BOM_HEADER_NOT_FOUND` + 1 `CLASSIFICATION_OR_EMPTY_BOM` for
     A091-91300) — the safe parser dropped or truncated real BOM rows physically
     on the page. Restored via a new **governed BOM-correction mechanism** at
     B01 combine (`data/governance/task015_b01_bom_corrections_v1.json`, 20
     corrections: 24 rows added, 10 repaired, 1 new parent A091-91300 with its
     verified 15-row BOM).
  2. **6 silently-truncated wrapped values** (91200 items 8,15; 92000 items
     3,4; 311A0 items 6,16) whose first-line fragments matched the identifier
     pattern so B02 never flagged them. Repaired to the full joined values
     (governed reviewer decision, source-anchored; not automatic concatenation).
  3. **38 `SUSPICIOUS_IDENTIFIER` + 5 parent-level** accepts via the existing
     C01 governed override path (`data/governance/task015_c01_overrides_v1.json`,
     56 overrides total = 51 suspicious + 2 `BLANK_PART_NUMBER` + 2
     `CLASSIFICATION_OR_EMPTY_BOM` + 1 `RELIABLE_BOM_HEADER_NOT_FOUND`). Pure
     Chinese part names are accepted as `unknown_child` (no definition node).
     No identifier rule was relaxed.

### Result

- B01 r10: 39 parents (32 governed historical + 6 fresh + 1 governed correction
  parent A091-91300), 1 remaining extraction finding
  (`AE1-387-D274-11101-1` `RELIABLE_BOM_HEADER_NOT_FOUND`, governed accept).
- B02 r10: **56 findings, all blocking, all governed-accepted; 0 unresolved.**
  Corrected parents show items 1–16 / 1–7 / 1–16 in order. The 2
  `ITEM_SEQUENCE_GAP` warnings also cleared (restored rows).
- C01 r10: **passed closed with 0 unresolved** (r9 failed closed at 60).
  446 relationships, 181 `unknown_child`, 244 confirmed PRT children, 21 known
  ASM children. 56 accepted-risk findings.
- C02 r10: 446 relationships, 505 drawings with 38 parent-counts / 246
  child-counts. 505 drawings (of 507) have a parent or child count recorded.
- Tests: `python -m pytest tests/unit/cad_2d_v2 -q` → **47 passed, 6 subtests
  passed** (item-order insertion + C01 exclusion-shape tests added).

### r10 bundle SHA-256s (canonical result)

- B01_phase3r10: `b43b2d49b20163438da63047a8612a17756ba95c5a872f844bb1c29d5306d794`
  (run `cad2d_b01_e0fe91911fff348a`; input hashes pinned incl.
  `corrections=9af58e8cff41fb56`)
- B02_phase3r10: `2b6a873783c6d3f6f07d2875bcd04d3aa6375f191b89d9293934d439e8da6ad4`
  (run `cad2d_b02_b15e6eaaef9699d7`)
- C01_phase3r10: `39bf155aac03a886021410be1edbb999680387229ff67ac809d4f25dd61db796`
  (run `cad2d_c01_29e5b4d2c50bd97a`; `overrides=0198ea02bde39554`; regenerated
  2026-08-11 with the review concern fix — see Independent review below)
- C02_phase3r10: `34a45065d9a0f601c5c043d28329e6af7ffca320331458893c19605a270f6d22`
  (run `cad2d_c02_cf2dffdcf41c79af`)
- Governance artifacts: `data/governance/task015_b01_bom_corrections_v1.json`
  (20 corrections) and `data/governance/task015_c01_overrides_v1.json`
  (56 overrides).

### Independent review (Task #5) — 2026-08-10/11

- Multi-agent independent quality review (Reproduce / Audit / Probe / Verdict)
  completed with verdict **`READY_FOR_REVIEW_SIGN_OFF`** — **0 blocking**, 1
  concern, 12 info. All 6 agents (3 repro, 2 audit, 1 probe) completed with 0
  errors.
- **Reproduction (independent, byte-for-byte):** B01 `b43b2d49…`, B02
  `2b6a8737…`, C01 `3c926c02…`, C02 `34a45065…` all matched the recorded r10
  hashes; C01 **fails closed** without `--overrides` (exit 1, count=56); unit
  suite 46 passed + 6 subtests; `git diff --check` clean.
- **Audit:** all 17 correction `resolved_finding_ids` exist in B02 r9 with
  matching parent; the 6 empty-resolved corrections are exactly the wrapped-value
  repairs; corrected item sequences strictly ascending; 91300 present with 15
  rows; spot-checked values confirmed against page geometry; all 56 overrides map
  1:1 onto B02 r10 findings (0 orphans, 0 dangling).
- **Probes:** no assembly loops (18 dual parent/child are legitimate nested ASMs;
  cycle detection clean), 12100 blank-child exclusions confirmed, no
  correction/override overlap, quantities sane (1–56), 0 duplicate children or
  occurrence_ids, `occurrence_ordinal == item_no` on every record.
- **Concern (addressed 2026-08-11, per user decision "Fix + regenerate C01"):**
  C01 `BLANK_CHILD_IDENTIFIER`/`EXCLUDED_CHILD_NOT_PROMOTED` exclusion records
  carried only `reason_code` + `record_index`, omitting `parent_part_number`
  (linkage to parent 12100 items 4/5 was only inferable by cross-referencing
  B01). Fix: `build_relationships` now emits `parent_part_number` + `item_no`
  on both exclusion shapes (`services/ingestion/cad_2d_pipeline_v2/stages.py`).
  C01 regenerated: relationships and audit byte-identical, exclusions carry the
  parent link; C02 unchanged (`34a45065…`, same run id — its inputs are only the
  relationship records). New C01 bundle+manifest installed in
  `C01_phase3r10/`; tests 47 passed + 6 subtests.
- **Documented info note (non-blocking):** 4 r9-only findings (2 SUSPICIOUS
  item-16 on 311A0/91200; 2 ITEM_SEQUENCE_GAP) are not enumerated in any
  correction's `resolved_finding_ids` but are implicitly resolved by the
  corrections to the same parents — recorded as a completeness gap in the
  artifact's traceability, not a violation.

### State

- Phase 3 r10 candidate has **passed the independent quality review** with
  verdict `READY_FOR_REVIEW_SIGN_OFF` (0 blocking) and the single non-blocking
  auditability concern has been fixed and re-verified. It is ready for reviewer
  sign-off / freeze. Until frozen it is not yet promotable, serving/KG eligible,
  handed to Task016, or released.

## 2026-08-11 - Phase 3 r10 candidate frozen and handed to Task016

### Plan

- Freeze the cleaned Task015 candidate in place without moving or rewriting any
  A01-C02 stage bundle or stage manifest.
- Pin the complete artifact set, governance dependencies, code/config/test
  content, failure inventory, and decision boundaries in one immutable freeze
  manifest.
- Hand only the CAD lane to Task016 and preserve the missing Task017 material
  candidate as a visible blocker to a combined Task016 review decision.

### Data-content permission

The user explicitly authorized direct validation of these bounded paths on
2026-08-11:

- `data/processed/review_pending/route_a/v2_task015_cad_2d_pipeline_v2_candidate/`
- `data/governance/task015_b01_bom_corrections_v1.json`
- `data/governance/task015_c01_overrides_v1.json`
- `data/governance/source_inventory.csv`
- `data/governance/masking_log.jsonl`
- `data/governance/annotation_log.jsonl`

No PDF, `data/raw/`, or other data path was read.

### Changed files

- `data/processed/review_pending/route_a/v2_task015_cad_2d_pipeline_v2_candidate/task015_freeze_manifest.json`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/brief.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/acceptance.md`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/notes.md`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/brief.md`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`

No stage bundle, stage manifest, governance artifact, pipeline implementation,
configuration, or test file was modified by the freeze.

### Frozen candidate

- Freeze manifest:
  `data/processed/review_pending/route_a/v2_task015_cad_2d_pipeline_v2_candidate/task015_freeze_manifest.json`.
- Freeze-manifest file SHA-256:
  `e76469c5cb84bd37bfab883c0f9e6910990cd0dbe62b3feff5e52e7ca21452e8`.
- Candidate version: `phase3r10`.
- Surviving B00 identity after the user's data cleanup: `B00_phase3r5`; the
  previously referenced `B00_verified` and `B00_pinned` directories are absent.
  B01 pins the surviving B00 records, exclusions, and manifest exactly.
- The freeze contains 14 immutable stage files across A01, A03, B00, B01, B02,
  C01, and C02. Every canonical result matches its stage manifest.
- The 22-file code/config/test tree is pinned by SHA-256
  `db0dcf5896e054702e80e2f434e717cbead2cb6d4b4e99e5e96977c2896cfd19`.
  These files remain untracked and have no Git commit identity; the content
  fingerprint, not a commit, is the local freeze identity.

### Complete failure and exclusion inventory

- B01 retains one `RELIABLE_BOM_HEADER_NOT_FOUND` exclusion. It is represented
  in the B02 inventory and governed acceptance chain.
- B02 contains 56 error-severity findings: 51 `SUSPICIOUS_IDENTIFIER`, two
  `BLANK_PART_NUMBER`, two `CLASSIFICATION_OR_EMPTY_BOM`, and one
  `RELIABLE_BOM_HEADER_NOT_FOUND`.
- All 56 finding IDs are unique and map exactly 1:1 to 56 complete governed
  accepted overrides. Unresolved blocking finding count is zero.
- Twenty complete governed corrections reference 17 unique historical finding
  IDs. Four r9-only findings remain documented as a non-blocking traceability
  completeness gap because same-parent corrections resolve them implicitly.
- C01 contains 446 relationship records and two linked
  `BLANK_CHILD_IDENTIFIER` exclusions. C02 contains 505 drawing records and two
  `DRAWING_NOT_PROMOTED` exclusions.

### Validation

- Parsed all 14 stage JSON files, the two Task015 governance JSON files, 167
  inventory rows, five masking events, and six annotation events successfully.
- All seven bundle-to-manifest canonical result hashes passed.
- All 15 checked A03/B00/B01/B02/C01/C02 lineage links passed, including the
  exact correction and override hashes.
- Canonical r10 results remain B01 `b43b2d49...`, B02 `2b6a8737...`, C01
  `39bf155a...`, and C02 `34a45065...` as recorded above.
- `.venv\\Scripts\\python.exe -m pytest tests/unit/cad_2d_v2 -q` passed with
  50 tests and 6 subtests.
- Python compilation passed for the Task015 service, CLI, and unit-test trees.

### Risks and Task016 blockers

- **CAD blocker closed:** closing and freezing are now distinct recorded
  transitions. The Phase 3 r10 CAD candidate, complete failure inventory,
  governance dependencies, and exact local code fingerprint are handed to
  Task016.
- **Recoverability risk remains:** all 22 fingerprinted code/config/test files
  are still untracked. A later commit requires separate explicit user approval;
  until then, the freeze is exact but local-worktree-only.
- **Material blocker remains:** Task017 is still `planned`; its configured
  implementation paths and frozen candidate do not exist. Task016 therefore
  has no material candidate to evaluate and cannot issue its combined final
  recommendation.
- Task016 remains `planned`. Its independent owner may preregister the
  evaluation plan after normal startup confirmation, but candidate scoring must
  preserve reviewer independence and requires its own exact bounded data
  permission.
- The frozen CAD candidate remains in `review_pending`. Freeze does not set
  serving safety, KG eligibility, promotion, graph activation, Data RC, or
  release.
- 2D-to-3D reconciliation is explicitly deferred from this Task015 candidate;
  no completeness claim is made for that separate future boundary.

### State

Task015 implementation: `implemented` and `validated`.

Independent candidate review: `READY_FOR_REVIEW_SIGN_OFF`, concern fixed and
reverified.

Task015 candidate decision: `frozen_for_v2_task016_independent_validation`.

Task015 handoff: CAD lane handed to `V2-TASK016`.

Serving/KG/release state: `not eligible / not activated / not released`.
