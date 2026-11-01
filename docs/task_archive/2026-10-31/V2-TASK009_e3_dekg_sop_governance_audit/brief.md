# V2-TASK009 E3 DEKG SOP governance audit

## Identity

- Owner: `data_workflow_lead`
- Contract reviewer: `data_contract_engineer`
- Independent reviewer: `data_quality_reviewer`
- E3 evidence provider / affected consumer: N / system line
- Decision state: `planned`
- Dependencies: frozen `dekg_evidence_v2`; `V2-TASK003`; source-specific
  decisions such as `V2-TASK007`; deployed E3 DEKG state
- Downstream owner: `data_pipeline_kg_engineer` through
  `V2-TASK010_dekg_documentasset_replacement`; execution remains gated on this
  audit's complete E3 inventory

## Goal

Inventory and review every SOP that N has already ingested into DEKG on E3,
then issue a source-by-source governance and quality disposition without
changing the deployed graph or promoting document evidence to diagnostic truth.

## Current evidence

- The user requested a review of all SOPs already ingested by N into DEKG on
  E3.
- Local documentation identifies E3 as the N-owned `gx10` Ubuntu server.
- This workspace has no configured E3/gx10 SSH target; both names resolve only
  as literal, unreachable aliases.
- The configured Neo4j endpoint in this workspace is loopback, not E3.
- Historical Route B graph code may publish `RouteBDocument:DocumentAsset`
  nodes, while the frozen v2 contract governs non-node `DEKGEvidenceRecord`
  handoffs whose downstream derivatives must retain `evidence_id`.
- `V2-TASK007` and `V2-TASK008` cover the Vision SOP specifically and do not
  establish the complete deployed E3 SOP corpus.
- With explicit user permission, the canonical inventory was read for this
  audit. It contains 17 `source_type=sop` rows: 11 raw registrations, four
  processed Vision residual registrations, and two serving registrations for
  one apparent legacy SOP document family.
- Of the 11 raw SOP registrations, nine are `route_b` with masking and review
  pending, one Vision SOP is `route_a|route_b` and source-reviewed but masking
  pending, and one repair SOP is explicitly `n_a`, unmasked, and pending.
- The inventory schema does not carry E3 database/deployment identity,
  `evidence_id`, `doc_id`, ingestion mode, producer run, or graph counts, so it
  cannot establish which SOPs are deployed on E3.

## Scope

### Gate 1 - deployed corpus inventory

- Run read-only E3 queries to identify every SOP document and its graph/index
  representation.
- Record database name, graph/index version, deployment/run identifier,
  ingestion timestamp, producer commit/config/model when available, and node,
  block, chunk, media, and relationship counts.
- Capture stable identity and provenance fields without exporting document
  text, images, embeddings, secrets, endpoints, or raw/internal paths.
- Distinguish legacy `DocumentAsset` deployment from a derivative of frozen
  `dekg_evidence_v2` records.

### Gate 2 - governance and contract reconciliation

- Reconcile each deployed SOP with its governed mother-document registration,
  source/version, sensitivity, masking, serving, route, review, promotion, and
  release states.
- Verify `full_document` versus `evidence_residual`, selected Route A table
  exclusions, no-overlap assertions, and co-source provenance.
- Verify stable `source_id`, `doc_id`, `block_id`, `chunk_id`, `anchor`, and
  `evidence_id` lineage where the applicable contract requires them.
- Classify missing, duplicate, conflicting, orphaned, stale, or unregistered
  records without repairing them during review.

### Gate 3 - independent quality review

- Check coverage, duplicate identities/content hashes when approved, dangling
  edges, collisions, missing provenance, unsafe properties, route leakage, and
  forbidden diagnosis promotion.
- Perform bounded human content sampling only after explicit permission for
  the exact E3 artifact/query scope and any local `data/` paths involved.
- Issue `READY`, `READY_WITH_EXCLUSIONS`, or `NOT_READY` per SOP and for the
  deployed corpus as a whole.

## Non-goals

- No E3 mutation, Neo4j write, re-ingestion, masking, VLM run, graph/index
  rebuild, runtime change, release, or cleanup.
- No inspection of local files under `data/` without a separate explicit
  path-bounded permission.
- No raw SOP access or content export by default.
- No modification of frozen contracts, `Faultdx_ref/`, or workflow-system
  files.
- No claim that graph presence, successful ingestion, similarity, or a complete
  chain makes an SOP reviewed Route A truth.

## Initial write set

- `docs/tasks/V2-TASK009_e3_dekg_sop_governance_audit/`

The E3 operator procedure is defined in `e3_dekg_governance_handoff.md`.

Any governance-record mutation or remediation implementation requires a later
reviewed proposal with an exact write set, owner, rollback, and validation.

## Required E3 evidence

Either provide read-only E3 Neo4j/graph access from this workspace or have N
return an approved metadata-only export containing:

1. database and graph/index identity plus deployment/run manifest;
2. all SOP document identities and labels;
3. source/version/provenance and contract fields;
4. per-document block/chunk/media/edge counts;
5. masking, serving, review, promotion, and release state fields;
6. partition/co-source fields and excluded Route A anchors;
7. schema/label/property inventory and duplicate/orphan validation results.

## Planned validation

- Verify task identity, branch, mixed-worktree preservation, and no overlap
  with `V2-TASK007`/`V2-TASK008`.
- Execute only read-only graph metadata queries first and save query text,
  database identity, timestamps, counts, and result checksums.
- Reconcile the deployed set against governance only after explicit permission
  for `data/governance/source_inventory.csv` or an approved bounded export.
  Permission for that exact CSV was granted on 2026-07-27 and the local
  baseline is recorded in `gate1_governance_baseline.md`.
- Keep pipeline correctness, governance/contract correctness, domain review,
  and answer faithfulness/safety as separate findings.
