# Gate 1 - Vision SOP remaining-table review

## Purpose

Freeze the remaining-table disposition before the source-specific DEKG
partition is approved. This review uses human-confirmed lineage and historical
task evidence. It does not authorize reading the raw PPTX.

## Already confirmed for Route A / TPDX

| Slides | Table group | Decision |
|---|---|---|
| 7 | BOM | Route A consumed; exclude the selected table anchors from DEKG |
| 8-14 | CCD configuration tables | Route A consumed; exclude the selected table anchors from DEKG |
| 36 and 38 | Fool-Proof List | Route A consumed; exclude the selected table anchors from DEKG |

Exact block IDs will be supplied by an approved producer partition manifest.

## Remaining groups requiring review

| Review ID | Slides | Historical table description | Recommended decision | Final decision | Review notes |
|---|---|---|---|---|---|
| `VS-TBL-01` | 2 | Revision history | `not_eligible` | `not_eligible` | User review, 2026-07-25: exclude from DEKG |
| `VS-TBL-02` | 8-14 | Hardware specifications (`Item / Class / Specifications / Qty`) | `dekg_candidate` | `dekg_candidate` | User review, 2026-07-25: evidence-only DEKG candidate; remains outside Route A |
| `VS-TBL-03` | 15-30 | Locating-feature and specification tables (`Locating Feature / Description / Spec`) | `dekg_candidate` | `dekg_candidate` | User review, 2026-07-25: evidence-only DEKG candidate |

## Allowed final decisions

- `dekg_candidate`: eligible for the later masking/serving-safe DEKG producer
  path.
- `not_eligible`: exclude with a recorded reason.
- `quarantine`: retain internally but block downstream production.
- `needs_domain_review`: do not decide until a named reviewer resolves it.

## Review rules

- Do not promote an unselected table to Route A merely because it is
  structured.
- Do not emit Route A-selected table anchors again through DEKG.
- Preserve missingness and the source slide/table relationship.
- DEKG output remains `document_evidence + evidence_only`.
- Co-source TPDX/DEKG output is not independent corroboration.
- No raw file access is authorized by this review sheet.

## Review completion

The table gate was completed by user review on 2026-07-25. The resulting
partition must be represented by an approved producer manifest before any
pipeline run. Exact block IDs must come from that manifest; this review did not
read the raw PPTX.
