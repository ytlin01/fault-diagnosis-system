# V2-TASK007 notes

## 2026-07-24 - planned

### Plan

- Use the `data_workflow_lead` role for read-only triage and the source-specific
  governance decision.
- Reconcile N's DEKG onboarding, J's TASK-041/TASK-042 evidence, and the frozen
  `dekg_evidence_v2` boundary.
- Confirm source identity, table consumption, residual eligibility, co-source
  provenance, and the next write owner before any real-data pipeline run.
- Do not read `data/` contents until the user grants path-bounded permission.

### Evidence collected without reading `data/` contents

- Branch: `feature/v2-data-pipeline`.
- `V2-TASK006_phase2_masking_identity` already exists, so this task uses the
  next unused identifier, `V2-TASK007`.
- Git tree checks found no committed `data/processed/route_b_residual/`
  artifacts on `main`, `origin/main`, `origin/phase1_v1`, the
  `phase1-v1.1-e3-20260609` tag, or J's `cbcb2b1` commit.
- J's tracked regeneration script exists at
  `scripts/ingest/extract_route_b_images.py` in commit `cbcb2b1` and the
  current branch.
- Filesystem metadata shows the source copy at
  `docs/onboarding/vision_sop_onboarding/Luster_CGLink_CGSF_Vision Flow_v1.3.pptx`.
- Filename/metadata inspection found two related processed artifacts:
  `data/processed/vision_sop_bom.csv` and
  `data/processed/vision_sop_ccd.csv`.
- No contents under `data/` were opened.

### Initial changed files

- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/brief.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/acceptance.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/notes.md`

### Current blockers and decisions

- Explicit permission is required before reading
  `data/governance/source_inventory.csv` or either related processed CSV.
- The authoritative governed source location is not yet established; the
  visible PPTX is under onboarding documentation rather than a governed data
  zone.
- The CCD hardware-specification table has inconsistent historical status and
  needs one current decision.
- The four historical residual registrations must be reconciled with the
  mother-document identity and frozen DEKG derivation model.
- The worktree contains extensive unrelated user changes, including governance
  modifications; this task will not overwrite or normalize them.

### State

Task package: `implemented`.

Source reconciliation: `planned`.

Reviewed: no.

Released: no.

## 2026-07-25 - table review completed

### Human decisions

- `VS-TBL-01`: `not_eligible`.
- `VS-TBL-02`: `dekg_candidate`.
- `VS-TBL-03`: `dekg_candidate`.

### Result

- The source-specific DEKG ingestion mode is `evidence_residual`.
- Confirmed Route A table groups remain excluded from DEKG through a future
  producer partition manifest.
- The revision-history table is excluded.
- Hardware-specification and locating-feature/specification tables may proceed
  only as evidence-only DEKG candidates after masking, serving-safe projection,
  and contract validation.
- No raw PPTX content was read during this decision update.

### State

Source lineage: `reviewed`.

Table disposition: `reviewed`.

Source-specific DEKG mode: `reviewed`.

Governance mutation: not executed; corrected dry-run pending approval.

Released: no.

### Corrected governance dry-run

- Executed `inventory.record(..., dry_run=True)` only; the API returned the
  proposed row without opening or writing `source_inventory.csv`.
- Preserved the historical source ID and registration date.
- Proposed the user-supplied corrected raw path.
- Proposed `source_type=sop`, `route_eligibility=route_a|route_b`,
  `serving_safe=no`, `masking_status=pending`, and
  `reviewed_status=reviewed`.
- Recorded no checksum claim.
- Governance write and read-back remain pending explicit human approval.

## 2026-07-24 - initial source reconciliation implemented

### Permission

The user explicitly permitted content reads of:

- `data/governance/source_inventory.csv`
- `data/processed/vision_sop_bom.csv`
- `data/processed/vision_sop_ccd.csv`
- `data/raw/C1STN_manuals/sop/Luster_CGLink_CGSF_Vision Flow_v1.3.pptx`

The last path was later corrected by the user: it is not the authoritative raw
file. The hash/read result from that different filename is retracted and must
not be used as source evidence.

The actual raw path is
`data/raw/C1STN_manuals/sop/L_C1_C1STN_Vision Flow_v1.3.pptx`. The user
explicitly prohibits reading it. This exact file has not been opened or hashed.

### Implemented

- Added `gate1_source_reconciliation.md` with the proposed mother-document identity,
  `evidence_residual` decision, table partition, residual classification,
  inventory relationship, and next handoff.
- Confirmed the permitted BOM artifact has 23 rows, all anchored to slide 7.
- Confirmed the permitted CCD artifact has seven rows, one on each slide 8-14.
- Confirmed ten related inventory records: one mother document, five Route A
  derivatives, and four Route B residual derivatives.
- Identified that the mother-document row points to a retired path and remains
  `missing_review_needed`.
- A differently named `Luster_CGLink_CGSF` file was incorrectly treated as the
  governed source under the prior path statement. That conclusion is
  retracted; it establishes nothing about the prohibited `L_C1_C1STN`
  raw file.
- Parsed the onboarding reference copy in memory without writing data output:
  35 tables, 38 native text blocks, and 60 legacy media blocks.
- Historical/onboarding analysis produced a reference table/image ledger, but
  it is withdrawn as a production decision until approved lineage connects it
  to the prohibited raw source.
- Reconciled J's claimed 34-image VLM total to 32 unique listed target media,
  seven explicit exclusions, 15 additional referenced media, and five
  unreferenced packaged media files.
- Completed local visual review of the 15 omitted referenced images using only
  the onboarding PPTX. Fourteen are proposed VLM evidence/context candidates;
  `image55.png` is excluded because it duplicates the selected Fool-Proof
  table and carries sensitive-table risk.
- The complete proposed image ledger is 46 candidates, eight referenced
  exclusions, and five unreferenced package assets.
- Found path drift between the current BOM/CCD inventory paths and their actual
  legacy flat locations.
- Executed an earlier `inventory.record(..., dry_run=True)` proposal against
  the wrong source/path assumption. It made no write and is withdrawn.

### Changed files

- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/brief.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/acceptance.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/notes.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/gate1_source_reconciliation.md`

### Validation pending

- Human-supplied or approved sidecar identity/version for the prohibited raw
  source.
- Approved lineage connecting or separating it from the historical BOM/CCD and
  J residual records.
- A new governance proposal based only on that evidence. The earlier dry-run is
  withdrawn and no mutation was executed.

### State

Source reconciliation proposal at this point: `paused_for_identity_evidence`.
This state is superseded by the later human lineage confirmation below.

Validated: partial, pending the checks above.

Reviewed: no.

Released: no.

## 2026-07-24 - human lineage confirmation

### Confirmed by user

- Corrected filename: `L_C1_C1STN_Vision Flow_v1.3.pptx`.
- It is the same governed source as the historical
  `Luster_CGLink_CGSF_Vision Flow_v1.3.pptx` work.
- The Route A consumption boundary is correct: BOM slide 7, CCD configuration
  slides 8-14, and Fool-Proof List slides 36/38.
- J's residual package derives from the current raw source.
- The remaining tables must be reviewed before finalizing the DEKG partition.

### Implemented

- Added `gate1_table_review.md` with three bounded review groups and allowed
  dispositions.
- Advanced task state from identity-evidence pause to table-review pending.
- Kept the raw-file prohibition unchanged.

### State

Source lineage: `reviewed` by human confirmation.

Table disposition: `planned`.

Source-specific DEKG partition: not finalized.

Reviewed for release: no.

Released: no.

## 2026-07-27 - governance update implemented and validated

### Approval

The user approved the corrected single-row inventory update.

### Implemented

- Updated the existing mother-document row through
  `services.governance.inventory.record(...)`.
- Preserved the historical source ID and `date_added`.
- Corrected the governed path and `source_type=sop`.
- Set `route_eligibility=route_a|route_b`, `serving_safe=no`,
  `masking_status=pending`, and `reviewed_status=reviewed`.
- Recorded human-confirmed lineage, Route A boundary, `evidence_residual`
  mode, table decisions, J residual lineage, and the raw access restriction.
- Added `gate2_pipeline_handoff.md` for the next producer task.

### Validation

- `inventory.get(source_id)` matched the approved row exactly:
  `READ_BACK_MATCH=True`.
- The raw PPTX was not opened, hashed, or parsed.
- No other governance row was intentionally changed by this task.

### Changed files

- `data/governance/source_inventory.csv` - one approved row updated.
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/brief.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/acceptance.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/notes.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/gate1_source_reconciliation.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/gate1_table_review.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/gate2_pipeline_handoff.md`

### State

Gate 1 source reconciliation: `validated` and `reviewed`.

Released: no.

Next owner: `data_pipeline_kg_engineer`.

## 2026-07-27 - gate artifact naming

### Implemented

- Renamed `source_reconciliation.md` to
  `gate1_source_reconciliation.md`.
- Renamed `table_review.md` to `gate1_table_review.md`.
- Renamed `pipeline_handoff.md` to `gate2_pipeline_handoff.md`.
- Added a gate-artifact map to `brief.md`.
- Preserved the required task-control filenames `brief.md`, `acceptance.md`,
  and `notes.md` because they span the entire task lifecycle.

### Validation

- Repository reference scan found no stale references to the former supporting
  filenames.
- Scoped `git diff --check` passed.
- Workflow guard passed with no protected workflow changes.
- No file under `data/` was opened during the rename.
