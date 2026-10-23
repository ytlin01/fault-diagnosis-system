# V2-TASK010 DEKG DocumentAsset replacement

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_workflow_lead`, `data_contract_engineer`
- Independent reviewer: `data_quality_reviewer`
- Affected consumer / deployment owner: N / system line
- Decision state: `implemented`
- Contract: frozen `dekg_evidence_v2` and `dekg_validation_policy_v2`
- Dependencies: `V2-TASK003`, `V2-TASK009`, complete reviewed E3 SOP inventory

## Goal

Replace the deployed legacy Route B `DocumentAsset` graph with a complete,
contract-valid DEKG evidence release. After deployment, all governed handoff
objects are `DEKGEvidenceRecord` records, all Neo4j evidence nodes are explicit
downstream derivatives retaining `evidence_id`, and no legacy
`DocumentAsset` label/property representation remains.

## Contract interpretation

The frozen contract says `DEKGEvidenceRecord` is a governed transfer object,
not a TPDX or DEKG graph node. Neo4j therefore stores `:DEKGEvidence` derivative
nodes with `record_type=DEKGEvidenceRecord`, `contract_version=dekg_evidence_v2`,
and the stable `evidence_id`. The graph node does not replace the governed
record package.

## Inputs

- An explicit, complete list of reviewed `dekg_evidence_v2` package paths.
- One release ID across the replacement set.
- E3 database identity, migration ID, and verified pre-migration backup ref.
- The frozen contract and policy.

The migration command is transferred to and executed on E3. It connects to the
Neo4j instance local to E3; this development workstation does not mutate E3.

No real package or file under `data/` is read by this implementation task.
Tests use synthetic in-memory and temporary-file fixtures only.

## Scope

- Strictly validate the v2 package and record boundary before connecting.
- Reject unsafe fields/values, invalid modes, missing provenance, duplicate
  evidence identities, TPDX overlap, co-source violations, and promotion.
- Project each governed record into one `:DEKGEvidence` derivative node keyed
  by `evidence_id`.
- Replace the legacy Route B graph in one data transaction.
- Delete legacy `:RouteBGraphNode` nodes and any remaining node carrying the
  `DocumentAsset` label or `schema_node_type=DocumentAsset`.
- Verify expected evidence count, distinct evidence identity count, derivative
  contract markers, and `DocumentAsset=0` before commit.
- Disable the legacy exporter's direct Neo4j write entry point.

## Non-goals

- No conversion from live `DocumentAsset` node properties; they lack sufficient
  frozen-v2 provenance.
- No raw/processed/serving data read, masking, VLM execution, source promotion,
  retrieval redesign, or release approval.
- No E3 execution until `V2-TASK009` fixes the complete deployed SOP set and an
  independent reviewer accepts the replacement candidate and rollback evidence.
- No modification of the frozen contract.

## Write set

- `services/graph/dekg_evidence_store.py`
- `scripts/build_graph/replace_legacy_dekg_neo4j.py`
- `scripts/export_route_b_graphrag_neo4j.py`
- `tests/services/graph/test_dekg_evidence_store.py`
- `docs/tasks/V2-TASK010_dekg_documentasset_replacement/`

## Failure behavior

- Package validation fails before Neo4j connection or mutation.
- Apply requires explicit `--apply`, `--migration-id`, and `--backup-ref`.
- The replacement transaction raises and rolls back if any post-write invariant
  differs from the reviewed input set or any `DocumentAsset` remains.
- The old graph writer raises unconditionally and directs operators to the
  replacement command.

## Rollback

Restore the named pre-migration E3 Neo4j backup. The migration intentionally
does not retain old `DocumentAsset` nodes beside the new release because that
would violate the zero-legacy acceptance gate. A backup ref is mandatory for
apply and must be independently verified before deployment.

## Deployment command shape

```text
python scripts/build_graph/replace_legacy_dekg_neo4j.py \
  --package <reviewed-package-1.json> [--package <reviewed-package-N.json>] \
  --migration-id <approved-id> --backup-ref <verified-backup> --apply
```

The exact E3 paths, database, package hashes, release ID, expected record count,
and backup ref belong in the reviewed deployment manifest, not this task brief.

The complete operator sequence is defined in `e3_dekg_replacement_handoff.md`.
