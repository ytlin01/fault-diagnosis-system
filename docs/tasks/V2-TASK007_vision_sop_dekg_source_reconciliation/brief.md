# V2-TASK007 Vision SOP DEKG source reconciliation

## Identity

- Owner: `data_workflow_lead`
- Reviewers: `data_contract_engineer`, affected Route B producer owner
- Decision state: `planned`
- Dependencies: `V2-TASK003_dekg_fhkb_ingestion_contracts`, historical
  `TASK-041_route_a_table_extraction`, historical
  `TASK-042_route_b_residual_split`
- Downstream owner: `data_pipeline_kg_engineer`

## Goal

Reconcile the Vision Flow SOP mother document, its reviewed Route A table
consumption boundary, and J's historical Route B residual handoff into one
source-specific governance decision for the frozen `dekg_evidence_v2`
contract.

## Gate artifact map

| Gate | Artifact | Purpose |
|---|---|---|
| Gate 1 - inventory and governance | `gate1_source_reconciliation.md` | Source identity, lineage, route state, governance decision, and approved inventory update |
| Gate 1 - partition review | `gate1_table_review.md` | Human decisions for Route A exclusions and remaining-table DEKG eligibility |
| Gate 2 - producer handoff | `gate2_pipeline_handoff.md` | Text/table lane, VLM lane, masking, DEKG adapter, validation, and independent-review requirements |

The standard task-control files `brief.md`, `acceptance.md`, and `notes.md`
span the whole task and retain their required names.

## Current evidence

- The user identifies the raw source path as
  `data/raw/C1STN_manuals/sop/L_C1_C1STN_Vision Flow_v1.3.pptx` and
  explicitly prohibits reading it.
- The onboarding `Luster_CGLink_CGSF` copy is historical/reference material and
  is not proof of the prohibited raw file's identity or contents.
- J's extraction script is tracked at
  `scripts/ingest/extract_route_b_images.py`.
- No committed `data/processed/route_b_residual/` package exists on `main`,
  `origin/main`, `origin/phase1_v1`, the `phase1-v1.1-e3-20260609` tag, or
  J's `TASK-042` commit. The historical package was gitignored and must be
  regenerated from an approved source copy.
- The worktree currently contains
  `data/processed/vision_sop_bom.csv` and
  `data/processed/vision_sop_ccd.csv`; their contents have not been inspected
  in this task.
- Historical acceptance records four `candidate_residual` registrations, 34
  VLM-candidate images, five text-only slides, seven excluded images, and
  co-source boundaries on slides 8-14 and 38.
- `dekg_evidence_v2` is frozen. Runtime activation, graph/index derivation,
  real-data production, and release remain separate gates.

## Decisions required

1. Obtain the authoritative `source_id`, source version/checksum, owner,
   sensitivity, and lineage from human-supplied or approved sidecar evidence;
   do not derive them from the prohibited raw file.
2. Confirm whether this source uses `evidence_residual` because anchored table
   content was selected for TPDX/Route A.
3. Freeze the exact selected-table anchor set excluded from DEKG.
4. Resolve the CCD hardware-specification table eligibility inconsistency in
   the historical records.
5. Confirm the accepted residual baseline: 34 VLM-candidate images, five
   text-only slides, seven excluded images, and the slide-level co-source
   groups.
6. Decide whether the four historical residual inventory rows remain governed
   source records or become derived-artifact records under one mother-document
   registration.
7. Name the pipeline owner, real-data read scope, rebuild outputs, validation,
   and next handoff.

## Human-confirmed lineage

- `L_C1_C1STN_Vision Flow_v1.3.pptx` is the same governed source as the
  historical `Luster_CGLink_CGSF_Vision Flow_v1.3.pptx` work.
- The reviewed Route A consumption boundary is correct.
- J's historical residual package derives from the current raw source.
- The remaining-table DEKG disposition must be reviewed before the partition
  decision is finalized.

## Scope

- Read-only source and governance reconciliation after explicit permission for
  each required path under `data/`.
- Source/version and route-eligibility decision.
- TPDX-consumed anchor and DEKG residual boundary.
- Co-source and promotion-state decision.
- A reviewed handoff to a future deterministic producer task.

## Non-goals

- No residual regeneration, VLM execution, masking, serving projection,
  adapter execution, graph/index build, Neo4j import, benchmark, runtime
  binding, or release decision.
- No modification of the frozen DEKG/FHKB contracts.
- No inspection of any file under `data/` without explicit bounded user
  permission.
- No mutation of canonical governance records before a reviewed dry-run plan.
- No use of `Faultdx_ref/`.

## Initial write set

- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/`

Any later governance mutation must be proposed separately with an exact row
set, dry-run evidence, reviewer, and rollback. It is not authorized by this
brief.

## Planned validation

- Verify branch, task identity, and task overlap.
- Record only human-supplied or approved sidecar identity/version evidence; do
  not open or hash the prohibited raw file.
- Reconcile historical TASK-041/TASK-042 decisions against the frozen DEKG
  contract.
- With permission, read only the bounded governance and processed artifacts
  required to verify source registration and consumed-boundary claims.
- Produce an explicit decision table and pipeline/KG handoff.
