# Gate 1 - Vision SOP DEKG source reconciliation

## Decision status

`GATE1_REVIEWED`

The approved governance mutation is validated. Pipeline execution remains a
separate gate.

## Raw-source restriction

The user identified the raw source as:

`data/raw/C1STN_manuals/sop/L_C1_C1STN_Vision Flow_v1.3.pptx`

This file must not be opened, hashed, parsed, previewed, sampled, grepped, or
read indirectly by a script, validator, or other tool. Its path is recorded
only from the user's statement.

Source identity, version, checksum, content, anchors, and equivalence must come
from a user-supplied value or another explicitly approved manifest/sidecar.
This task will not derive them from the raw file.

## Evidence that remains usable

The user separately permitted reads of:

- `data/governance/source_inventory.csv`
- `data/processed/vision_sop_bom.csv`
- `data/processed/vision_sop_ccd.csv`

Those files establish only that:

- the inventory contains an older mother-document row named for
  `Luster_CGLink_CGSF_Vision Flow_v1.3.pptx`;
- a 23-row BOM artifact is anchored to slide 7;
- a seven-row CCD configuration artifact is anchored one row per slide on
  slides 8-14;
- historical Route A and Route B derivative registrations exist.

The user has supplied the authoritative lineage decision that
`L_C1_C1STN_Vision Flow_v1.3.pptx` is the same governed source as the older
`Luster_CGLink_CGSF` records, that the recorded Route A consumption boundary is
correct, and that J's residual package derives from this source. This is a
human governance decision; it was not inferred by reading the raw file.

Historical TASK-041/TASK-042 documents and the onboarding copy may be used as
workflow/history evidence, but not as proof of the prohibited raw file's
identity or contents.

## Conclusions that remain retracted

The following earlier proposals are withdrawn as production decisions:

- checksum equality between the governed raw source and onboarding copy;
- the proposed inventory update that would have overwritten the older source
  row with a different path;
- exact parser block IDs as the raw source's TPDX exclusion set;
- the 23-table and 46-image dispositions as the raw source's DEKG ledger.

Those table/image findings came from historical/onboarding material. The user
has now confirmed their source lineage, but their DEKG eligibility remains a
review question rather than an approved production decision.

## Human-confirmed identity and lineage evidence

The user has supplied:

1. the corrected raw filename and path;
2. confirmation that it is the same governed source as the historical
   `Luster_CGLink_CGSF` work;
3. confirmation that the Route A consumption boundary is correct;
4. confirmation that J's residual package belongs to the current source.

Still required before a governance write are the final canonical source-ID
presentation, custody/sensitivity note, and reviewed remaining-table
disposition. No source checksum will be derived by this task.

## Confirmed Route A consumption boundary

- slide 7: BOM;
- slides 8-14: CCD configuration tables;
- slides 36 and 38: Fool-Proof List.

These semantic anchors are confirmed. Exact producer block IDs must come from
an approved partition manifest, not from this task reading the raw file.

## Table review gate

The user completed the remaining-table review on 2026-07-25:

- `VS-TBL-01`: `not_eligible`;
- `VS-TBL-02`: `dekg_candidate`;
- `VS-TBL-03`: `dekg_candidate`.

The source-specific ingestion mode is therefore `evidence_residual`. The
confirmed Route A table groups are excluded through a producer partition
manifest; `VS-TBL-01` is excluded; `VS-TBL-02` and `VS-TBL-03` may proceed only
through masking, serving-safe projection, and contract validation as
`document_evidence + evidence_only` candidates.

Exact block IDs remain a producer-manifest responsibility. This decision did
not read the raw PPTX.

## Safe next step

Obtain approval for the corrected governance dry-run, then prepare the
pipeline handoff from human-supplied or approved sidecar evidence only. Until
then:

- do not mutate `source_inventory.csv`;
- do not regenerate J's residual package from the raw file;
- do not run VLM, masking, DEKG adapters, graph/index builds, or validators
  that touch the raw file;
- do not execute a pipeline run or bind a runtime consumer.

## Corrected governance dry-run

The corrected `inventory.record(..., dry_run=True)` proposal completed without
writing governance:

| Field | Proposed value |
|---|---|
| `source_id` | `raw__C1STN_system_arch__Luster_CGLink_CGSF_Vision Flow_v1.3` |
| `file_path` | `data/raw/C1STN_manuals/sop/L_C1_C1STN_Vision Flow_v1.3.pptx` |
| `zone` | `raw` |
| `source_type` | `sop` |
| `route_eligibility` | `route_a|route_b` |
| `serving_safe` | `no` |
| `masking_status` | `pending` |
| `reviewed_status` | `reviewed` |
| `date_added` | `2026/5/26` |

The note preserves the human-confirmed alias/lineage, source version `v1.3`,
raw-file access prohibition, confirmed Route A boundary,
`evidence_residual` mode, three table decisions, J residual lineage, and
non-serving/masking-pending state.

The existing historical source ID is preserved because the user confirmed
that the corrected filename is the same governed source, not a new source.
No checksum is claimed. The user approved this row; it was written through the
governance API on 2026-07-27 and exact API read-back matched the proposal.
