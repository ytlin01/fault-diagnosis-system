# V2-TASK003 acceptance

## Task and ownership

- [x] The task remains within its declared contract-and-offline-adapter write
  set.
- [x] Contract state is `FROZEN`; no file claims released or
  released status.
- [x] Contract owner, reviewers, affected consumers, and next gate are named.
- [x] No `data/` contents are read directly or indirectly.

## DEKG evidence contract

- [x] The evidence contract and validation policy remain separate artifacts
  with reciprocal references.
- [x] The governed handoff object is `DEKGEvidenceRecord`, not
  `DocumentAsset` or a replacement graph node.
- [x] `full_document` is the default mode and carries all eligible serving-safe
  document content when no table is selected for TPDX.
- [x] `evidence_residual` is allowed only when anchored tabular content is
  selected for TPDX; selected table anchors are excluded from DEKG records.
- [x] Routing order is explicit: govern the mother document, decide table
  selection, hand selected tables to the TPDX candidate/review path first, then
  deliver the remaining content to DEKG.
- [x] Every record has a stable `evidence_id`; residual-mode records carry the
  TPDX partition decision, consumption state, excluded anchors, and an explicit
  no-overlap assertion.
- [x] Required provenance includes `source_id`, source version, `doc_id`,
  `block_id`, `chunk_id`, and `anchor`.
- [x] External semantics are fixed to
  `route_b_document/document_evidence/evidence_only`.
- [x] DEKG evidence records are not declared as TPDX Schema 4.1 or DEKG graph
  nodes; downstream representations must derive from `evidence_id`.
- [x] Co-source TPDX/DEKG references require a shared provenance group and
  cannot count as independent corroboration.
- [x] Raw/internal paths, VLM raw responses, endpoints, secrets, and unmasked
  content are rejected by policy.
- [x] Diagnosis promotion is forbidden.

## FHKB case contract

- [x] Required provenance includes stable case/source record IDs, source
  version, and record-level `source_refs`.
- [x] External semantics are fixed to
  `route_c_case/case_reference/candidate`.
- [x] The contract distinguishes producer marker `rag_case_pool` from consumer
  target `case_retrieval`.
- [x] Missing cause/action/context stays nullable; no chain completion is
  inferred.
- [x] In-place promotion to reviewed diagnosis or `MappingRecord` is forbidden.
- [x] Broad aggregate-directory scanning and unnamed source fallback are
  rejected by policy.
- [x] The executable schema uses canonical `case_id` and emits no legacy
  identifier alias.
- [x] Canonical case content, source references, temporal/equipment context,
  evidence summary, and field authority have closed typed shapes.
- [x] Canonical identity is deterministic from governed source identity and
  derivation rule version; conflicting collisions fail.

## Compatibility and validation

- [x] Compatibility with Route B evidence/policy v2 and Route C source boundary
  v1 is explicit.
- [x] Breaking changes, migration steps, rollback, and rejected payload behavior
  are documented.
- [x] Synthetic valid fixtures pass.
- [x] Fixtures with diagnosis promotion, unsafe content, missing provenance, or
  wrong route markers fail.
- [x] Contract and policy JSON parse successfully and reciprocal references
  resolve.
- [ ] Both executable JSON Schemas pass an independent Draft 2020-12
  metaschema check. The active environment has no JSON Schema validator;
  parsing, dialect declaration, closed record shapes, and generated-output
  invariants are validated locally.
- [x] The FHKB adapter maps approved legacy fields without inventing missing
  cause, action, time, equipment, or evidence values.
- [x] The DEKG adapter supports full-document mode and excludes only explicitly
  selected table anchors in evidence-residual mode.
- [x] Both adapters reject unsafe fields, ambiguous provenance, promotion
  claims, and identity collisions.
- [x] Adapter tests use only synthetic fixtures and perform no `data/` reads.
