# E3 DEKG replacement handoff

## Execution boundary

The legacy `DocumentAsset` nodes already exist in Neo4j on E3. This handoff is
therefore executed locally on the E3 workstation after the reviewed code and
DEKG package bundle are transferred there. Running the implementation or tests
on the development workstation does not change E3.

## Owners and gates

- Package producer: `data_pipeline_kg_engineer`
- E3 transfer/deployment owner: N / system line
- Governance reconciliation: `data_workflow_lead` through `V2-TASK009`
- Contract review: `data_contract_engineer`
- Independent release recommendation: `data_quality_reviewer`

Do not apply until the complete E3 SOP inventory and complete replacement
package list agree exactly.

## Transfer bundle

Transfer through the team-approved offline mechanism:

- `services/graph/dekg_evidence_store.py`
- `services/graph/neo4j_client.py`
- `scripts/build_graph/replace_legacy_dekg_neo4j.py`
- frozen DEKG contract/policy/schema files;
- every approved `dekg_evidence_v2` package in the replacement release;
- reviewed deployment manifest with each relative package path and SHA-256;
- code commit/diff identity and validation evidence.

Do not transfer `.git`, `.env`, credentials, raw SOPs, unmasked intermediates,
model caches, or unrelated data. E3 keeps its own local Neo4j credentials.

## E3 sequence

Run from the transferred project root on E3.

### 1. Fix the target

Record before any write:

- hostname/environment identity;
- Neo4j server and Python-driver versions;
- database name;
- code identity;
- package hashes, release ID, and expected record count;
- migration ID;
- backup command/output/ref and restore owner.

Do not assume the default database or backup command. Select the backup/restore
procedure for the Neo4j edition and version actually reported by E3.

### 2. Read-only legacy preflight

With E3's local Neo4j environment variables loaded:

```bash
python scripts/build_graph/replace_legacy_dekg_neo4j.py \
  --database <approved-database> \
  --inspect
```

Save the returned counts for `RouteBGraphNode`, `DocumentAsset`, and existing
`DEKGEvidence` nodes in the deployment evidence. This command does not load
package files and does not write.

### 3. Create and verify the backup

Create a recoverable Neo4j backup/dump using the procedure approved for the
actual E3 version. Verify the artifact exists, record its checksum/location,
and confirm the restore owner. The resulting identifier becomes
`<verified-backup-ref>`.

Stop if backup creation or verification is incomplete.

### 4. Validate the complete replacement set offline

Pass every manifest-listed package explicitly; broad directory scanning is not
supported:

```bash
python scripts/build_graph/replace_legacy_dekg_neo4j.py \
  --package <package-1.json> \
  --package <package-N.json>
```

This validates the frozen contract, single release, safety, provenance,
partition/co-source rules, and unique `evidence_id` set without connecting to
Neo4j.

The reported package count, release ID, and evidence count must match the
reviewed deployment manifest exactly.

### 5. Apply on E3

```bash
python scripts/build_graph/replace_legacy_dekg_neo4j.py \
  --database <approved-database> \
  --package <package-1.json> \
  --package <package-N.json> \
  --migration-id <approved-migration-id> \
  --backup-ref <verified-backup-ref> \
  --apply
```

The data transaction deletes the existing DEKG derivative set, the legacy
Route B graph, and any remaining `DocumentAsset` label/property nodes; it then
creates the reviewed evidence derivative set. Any verification mismatch raises
inside the transaction and rolls it back.

### 6. Independent read-back

Run `--inspect` again and retain the output. Required results:

- `document_assets = 0`;
- `route_b_graph_nodes = 0`;
- `dekg_evidence_nodes = <reviewed expected count>`.

Also independently verify:

- distinct `evidence_id` count equals node count;
- every node has `record_type=DEKGEvidenceRecord`;
- every node has `contract_version=dekg_evidence_v2`;
- every node is serving-safe and evidence-only;
- release ID, migration ID, source/version, and backup ref match the manifest;
- the forbidden/reference-only SOP and any excluded SOP are absent;
- no selected Route A anchor was re-emitted in an evidence-residual package.

### 7. Consumer smoke and review

Run the approved E3 retrieval/consumer smoke against the new representation.
Do not claim release based only on successful ingestion or zero legacy counts.
The independent quality reviewer must assess coverage, provenance, safety,
missingness, duplicates, and exclusions.

## Stop conditions

Stop without applying, or rely on transaction rollback, if any of the following
occurs:

- E3 inventory and package manifest differ;
- a package/hash/release/record count differs from review evidence;
- backup is absent or unverified;
- database identity or Neo4j version is not the reviewed target;
- package validation fails;
- any post-write count or contract marker differs;
- any `DocumentAsset` or legacy Route B node remains;
- consumer smoke or independent quality review fails.

## Rollback

If post-commit consumer validation fails, stop downstream access and restore
the named pre-migration backup using the version-specific E3 restore procedure.
Record the restore result and rerun the read-only inventory. Do not reconstruct
legacy nodes from partial Cypher or relabel new evidence nodes back to
`DocumentAsset`.
