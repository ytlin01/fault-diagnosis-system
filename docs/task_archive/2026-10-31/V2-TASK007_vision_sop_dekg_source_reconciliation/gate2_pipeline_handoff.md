# Gate 2 handoff - Vision SOP DEKG producer

## Handoff decision

- Upstream task: `V2-TASK007_vision_sop_dekg_source_reconciliation`
- Next owner: `data_pipeline_kg_engineer`
- Independent reviewer: `data_quality_reviewer`
- Contract: `dekg_evidence_v2`
- Ingestion mode: `evidence_residual`
- Runtime owner: N/system line; runtime binding is out of scope

## Raw-source boundary

The governed source path is recorded in canonical inventory, but Codex is not
authorized to open, hash, parse, preview, or indirectly read the raw PPTX.
Real-source execution must be performed by an explicitly authorized human or
pipeline environment. Implementation and tests prepared by Codex must use
synthetic fixtures unless separately authorized.

## Frozen partition inputs

### Exclude as Route A / TPDX-selected content

- slide 7 BOM;
- slides 8-14 CCD configuration tables;
- slides 36 and 38 Fool-Proof List.

The authorized producer must emit exact selected-table block IDs in its
partition manifest. Those anchors must never appear in DEKG evidence records.

### Remaining-table decisions

- `VS-TBL-01` revision history: `not_eligible`.
- `VS-TBL-02` hardware specifications: `dekg_candidate`.
- `VS-TBL-03` locating-feature/specification tables: `dekg_candidate`.

### J residual lineage

The user confirmed J's residual package derives from the current source. Treat
it as a historical selection baseline. Regeneration must produce a new
manifest and reconcile every difference; absent historical artifacts are not
current release inputs.

## Producer sequence

### 1. Authorized canonical regeneration

- Run the deterministic PowerPoint parser in an authorized local environment.
- Preserve mother-document identity, slide/table/image anchors, source version,
  parser version, and input/config digest.
- Write a run manifest; do not use inherited default eligibility flags as the
  partition decision.

### 2. Partition before enrichment

- Apply the Route A/TPDX selected-table manifest first.
- Exclude `VS-TBL-01`.
- Retain `VS-TBL-02` and `VS-TBL-03` as evidence-only table candidates.
- Reconcile native text and J's image selection with explicit candidate,
  excluded, and quarantined counts and reasons.
- Attach one co-source group to TPDX and DEKG derivatives from this mother
  document; they cannot count as independent corroboration.

### 3. Native text and table path - no VLM

- Native text goes directly to masking/review and deterministic chunking.
- `VS-TBL-02` and `VS-TBL-03` remain structured table evidence; do not flatten
  them into reviewed diagnostic facts.
- Preserve slide, block, table, row/chunk, and source anchors.
- Reject missing or unstable anchors rather than inventing them.

### 4. Image path - local VLM only

- Use only reviewed image candidates from the authorized regenerated manifest.
- Run target-resolution dry-run, then one-target smoke, then full E3 batch.
- VLM enrichment may write only metadata/evidence candidates; it must not
  overwrite base text or create `Phenomenon`, `MappingRecord`, or confirmed
  diagnosis truth.
- Raw images, asset paths, endpoints, secrets, and raw provider responses stay
  internal and must not enter serving output.

### 5. Masking and serving-safe projection

- Run masking dry-run before the formal run.
- Produce internal masked canonical and a separate serving-safe candidate.
- Native text, eligible tables, and VLM-derived text converge only after their
  source anchors and exclusions are preserved.
- The serving candidate remains `document_evidence + evidence_only`.

### 6. DEKG contract adapter

- Emit `DEKGEvidenceRecord` objects with stable `evidence_id`, `source_id`,
  source version, `doc_id`, `block_id`, `chunk_id`, anchor, content kind, and
  partition/co-source fields.
- Set `ingestion_mode=evidence_residual`.
- Include the approved partition decision and exact excluded table anchors.
- Fail if a selected TPDX anchor reappears, provenance is ambiguous, unsafe
  fields are present, or a promotion claim is made.

### 7. Frozen candidate handoff

- Deliver immutable candidate package, manifest, lineage, checksums, config and
  producer versions, counts, warnings, exclusions, quarantine list, and
  rollback/rebuild instructions.
- The `data_quality_reviewer` independently checks reproducibility, no-overlap,
  source safety, anchor stability, candidate coverage, and old/new differences.
- Graph/index derivation and N's consumer validation remain later gates.

## Required validation evidence

- deterministic rerun for equivalent input/config;
- selected-table no-overlap assertion;
- table/text/image candidate and exclusion reconciliation;
- schema and policy validation;
- forbidden-field and private-path scan;
- manifest/checksum/lineage completeness;
- failure tests for missing anchors, unsafe content, promotion claims, and
  identity collisions;
- independent `READY`, `READY_WITH_EXCLUSIONS`, or `NOT_READY` recommendation.
