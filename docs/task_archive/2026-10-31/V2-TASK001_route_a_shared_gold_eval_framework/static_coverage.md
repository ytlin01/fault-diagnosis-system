# V2-TASK001 Static Coverage Framework

## Status

Implemented as a `DRAFT` framework. No TP-DX graph snapshot has been run yet.

## Purpose

Static coverage evaluates a frozen, adapter-normalized graph snapshot without using graph-returned candidates as domain truth. It reports what the candidate contains and connects relative to explicit coverage targets. It does not score answer ranking or establish diagnostic correctness.

## Contracts and boundary

- Input: `contracts/evaluation/route_a_static_coverage_input_v1.schema.json`
- Runner: `scripts/eval/eval_route_a.py`
- Implementation: `services/evaluation/route_a_static_coverage.py`

The adapter supplies graph-specific extraction and maps physical IDs outside the coverage target. The input has a `candidate.data_maturity` field. For the old TP-DX baseline it must be `assumed_label_provisional`; that status is preserved in the report.

## Metrics

| Metric | Meaning |
| --- | --- |
| Entity recall | Expected stable domain entities present in the snapshot |
| Relation recall | Expected source/target/relation triples present in the snapshot |
| Path recall | Required topology, diagnostic, and bridge paths present end to end |
| Bridge source coverage | Eligible bridge-source nodes that have a configured bridge relation |
| Provenance completeness | Required relation types carrying source ID and source-local anchor |
| Integrity | Dangling endpoints and duplicate nodes/relations |

`entity_recall`, `relation_recall`, and `path_recall` are coverage against the supplied targets. If targets are provisional, these are provisional coverage metrics—not reviewed domain recall.

## Safety gates

Dangling relations and missing provenance for configured required relation types are visible blockers. They cannot be offset by aggregate coverage percentages. Review-state counts remain visible and do not upgrade a candidate's maturity.

## Run

```powershell
python scripts/eval/eval_route_a.py `
  --static-coverage-input <adapter-normalized-snapshot.json> `
  --static-coverage-output <static-coverage-report.json> `
  --skip-scenarios --skip-audit
```

The runner performs no Neo4j access. The old- and new-KG adapters must create equivalent normalized snapshots with a frozen graph version, snapshot ID, and configuration digest before a paired comparison.

## Next handoff

The pipeline/KG owner supplies an old TP-DX snapshot adapter. The quality reviewer supplies versioned coverage targets and verifies the report. Domain reviewers are required before any target set is used for reviewed domain-correctness claims.
