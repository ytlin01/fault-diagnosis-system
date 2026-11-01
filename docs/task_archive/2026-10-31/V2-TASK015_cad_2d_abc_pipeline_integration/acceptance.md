# V2-TASK015 acceptance

## Ownership and source selection

- [x] `data_pipeline_kg_engineer` is the single implementation write owner.
- [x] The cleaned S A/B/C handoff is the candidate source; the historical branch
  subset is comparison input, not a whole-branch merge target.
- [x] A source-accounting table maps every retained, replaced, and excluded
  branch/handoff component to the current-v2 implementation.

## A/B/C pipeline

- [x] A01 rejects duplicate identifiers and preserves authoritative reviewed
  classification decisions without changing row count.
- [x] A02 uses controlled template profiles and preserves valid empty fields.
- [x] A03 uses classification as left-hand authority, reports field-only keys,
  and produces deterministic join audits.
- [x] B01 processes only approved ASM records, gates on reliable BOM structure,
  and flags difficult rows rather than inventing them.
- [x] B02 distinguishes extraction, classification, sequence, duplicate,
  quantity, suspicious-identifier, and pending-source-review findings.
- [x] Manual BOM/audit overrides are governed and traceable.
- [x] C01/C02 do not run past unresolved high-priority B02 findings unless an
  explicit reviewed risk acceptance is recorded.
- [x] Parent ASM, all-child, confirmed PRT-child, and unknown-child semantics
  remain distinguishable.

## Reproducibility and safety

- [x] All stages are CLI/config driven, preview-first, deterministic, and
  manifested.
- [x] Equivalent inputs and configuration produce equivalent canonical outputs.
- [x] Raw PDFs and protected extracted values remain outside Git.
- [x] Synthetic positive, negative, audit, relationship, and determinism tests
  pass.
- [x] Approved representative template/PDF validation is recorded after bounded
  permission.
- [x] A frozen candidate and complete failure inventory are handed to
  `V2-TASK016`.

## Data-content permission

- [x] Task creation did not inspect drawing/classification/BOM/output content.
- [x] Exact bounded paths and explicit permission are recorded before any direct
  or indirect real-data read.
