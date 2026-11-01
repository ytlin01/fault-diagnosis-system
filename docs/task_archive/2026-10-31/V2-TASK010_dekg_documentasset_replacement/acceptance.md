# V2-TASK010 acceptance

## Task and safety

- [x] `V2-TASK010` was unused before task creation.
- [x] Ownership, review independence, scope, write set, failure behavior, and
  rollback are explicit.
- [x] Implementation and tests read no file under `data/`.
- [x] Apply is impossible without explicit flags and a backup reference.
- [x] E3 has a read-only `--inspect` mode that loads no package and performs no
  mutation.

## Contract-valid replacement

- [x] Only frozen `dekg_evidence_v2` packages are accepted.
- [x] Every graph derivative retains `evidence_id` and identifies its governed
  record type and contract version.
- [x] Invalid safety, provenance, partition, co-source, route, promotion, and
  duplicate-identity cases fail before mutation.
- [x] One replacement set must use one release ID.
- [x] The legacy exporter cannot write `DocumentAsset` nodes to Neo4j.

## Transaction and zero-legacy gate

- [x] Replacement removes the legacy Route B graph and any remaining
  `DocumentAsset` label/property representation inside the data transaction.
- [x] Post-write verification requires expected node count, distinct
  `evidence_id` count, valid derivative markers, and zero `DocumentAsset`.
- [x] Verification failure raises before commit.
- [x] Synthetic transaction tests cover success and rollback-triggering count
  or legacy-node mismatches.

## Deployment and review

- [ ] `V2-TASK009` provides the complete reviewed E3 SOP inventory.
- [ ] Every included SOP has a governed, masked, serving-safe v2 package and
  approved ingestion mode.
- [ ] The package list, hashes, release ID, database, expected counts, migration
  ID, and backup ref are frozen in a deployment manifest.
- [ ] Independent quality review recommends `READY` or
  `READY_WITH_EXCLUSIONS`.
- [ ] E3 preflight and replacement succeed against the approved database.
- [ ] E3 read-back proves `DocumentAsset=0` and exact evidence counts.
- [ ] Runtime/retrieval consumer validation passes before release.
