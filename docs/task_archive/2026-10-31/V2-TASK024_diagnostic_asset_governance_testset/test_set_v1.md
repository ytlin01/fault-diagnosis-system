# Synthetic governance and validation test set v1

## Purpose

This set turns the two reports into executable acceptance scenarios without
copying source records. Every fixture is synthetic. The set tests governance,
canonicalization, Schema 4.2 contract behavior, graph structure, query safety,
and independent evaluation. It is not a domain gold set and cannot establish
production readiness by itself.

## Result vocabulary

- `pass`: expected behavior is observed.
- `fail_closed`: publication or execution is rejected safely.
- `review_queue`: a bounded ambiguity or conflict is retained for human review.
- `excluded`: content is withheld with a reason code and no leakage.
- `abstain`: the system lacks sufficient governed evidence.
- `no_result`: a valid query has no applicable result.
- `error`: execution or contract failure, distinct from no result.

## Case families

| Family | Cases | Main gate |
|---|---:|---|
| governance and provenance | GOV-001 to GOV-004 | inventory, masking, lineage, co-source |
| canonicalization and mapping | CAN-001 to CAN-006 | aliases, ambiguity, candidate preservation |
| diagnostic contract | MAP-001 to MAP-004 | MappingRecord, review, pairing, many-to-many |
| topology and BOM | TOP-001 to TOP-005 | hierarchy, edges, normalization, reconciliation |
| query safety | QRY-001 to QRY-006 | registry, read-only behavior, statuses |
| independent evaluation | EVAL-001 to EVAL-004 | label independence, leakage, regressions |

The machine-readable source is `test_set_v1.jsonl`. A runner should record
case ID, input/config fingerprint, output fingerprint, observed status,
reason codes, and reviewer disposition without mutating the fixture.

## Expected gate interpretation

Any failure in provenance, promotion evidence, unreviewed content filtering,
unsafe query execution, or leakage control is blocking. Aggregate mapping or
query accuracy must not offset a blocking safety or provenance failure.
