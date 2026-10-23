# V2-TASK009 acceptance

## Task and safety

- [x] `V2-TASK009` was unused before task creation.
- [x] Owner, reviewers, E3 evidence provider, scope, non-goals, initial write
  set, and next-gate rule are explicit.
- [x] Existing mixed-worktree changes remain untouched.
- [x] No local file under `data/` was opened while planning the audit.
- [x] The user explicitly permitted reading
  `data/governance/source_inventory.csv` solely for E3 SOP reconciliation.
- [x] A checksummed, metadata-only SOP governance baseline was recorded without
  opening any referenced source or derivative artifact.
- [x] A standalone read-only E3 DEKG governance handoff is defined separately
  from VLM, package production, Neo4j replacement, and runtime activation.
- [ ] E3 access or an approved metadata-only export is available.
- [ ] Every executed E3 query is demonstrably read-only.
- [ ] No raw text, image, embedding, secret, endpoint, credential, or
  unapproved internal path is exported.

## Deployed corpus inventory

- [ ] The target database, graph/index version, and audit timestamp are fixed.
- [ ] The inventory includes every deployed SOP, with an explicit completeness
  rule that does not rely only on filename matching.
- [ ] Each SOP has stable deployed identity, source/version lineage, labels,
  counts, and run/producer metadata or a visible missing-field finding.
- [ ] Legacy `DocumentAsset` records and frozen-v2-derived records are reported
  separately.
- [ ] Duplicate document/source identities, orphan blocks/chunks, dangling
  edges, and conflicting versions are enumerated.

## Governance and contract reconciliation

- [ ] Each SOP is matched to exactly one governed mother source or marked
  unregistered/ambiguous.
- [x] The local inventory candidate set and its current governance states are
  enumerated for comparison with E3.
- [ ] Sensitivity, masking, serving, route, review, promotion, and release states
  are checked independently.
- [ ] The applicable ingestion mode is identified per SOP.
- [ ] `evidence_residual` SOPs have reviewed table exclusions, exact anchors,
  no-overlap evidence, and co-source provenance.
- [ ] Applicable v2 records/derivatives preserve `evidence_id`, `source_id`,
  `doc_id`, `block_id`, `chunk_id`, and anchor lineage.
- [ ] No record is treated as reviewed `Phenomenon`, `MappingRecord`, or
  diagnosis because it exists in DEKG.

## Independent review and decision

- [ ] The quality reviewer receives a frozen, checksummed inventory and query
  bundle without implementation changes mixed into the review.
- [ ] Coverage, missingness, duplicates, collisions, orphans, safety, route
  leakage, and promotion checks are reported with visible failures/exclusions.
- [ ] Any content sample has explicit path/query-bounded permission and a
  recorded sampling rule.
- [ ] Every SOP receives `READY`, `READY_WITH_EXCLUSIONS`, or `NOT_READY` with
  rationale and required remediation.
- [ ] A corpus-level recommendation is issued without hiding per-source
  failures behind aggregate counts.
- [ ] `planned`, `implemented`, `validated`, `reviewed`, and `released` remain
  distinct states.
