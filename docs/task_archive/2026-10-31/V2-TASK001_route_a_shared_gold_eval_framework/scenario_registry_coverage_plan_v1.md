# V2-TASK001 Route A scenario registry and coverage plan v1

## Status and boundary

This is a **planned**, data-free coverage design for the graph-independent
Route A golden set. It does not contain source content, queries, case labels,
graph results, adapter mappings, or blind labels. It is not a golden-case set
and does not create a domain-correctness or release claim.

Each future golden case will reference one `scenario_id` from this registry.
Query paraphrases and translations remain variants of the same scenario; they
do not create additional independent scenarios or cross-partition evidence.

## Scenario identifier format

`RA-GOLD-<TYPE>-<NN>`

`TYPE` is one of `EC`, `PHEN`, `ASSET`, `AMB`, `PARTIAL`, `MULTI`, or
`ABSTAIN`. `NN` is a zero-padded sequence within the type. IDs describe
coverage only; they do not encode a source, graph, cause, action, or label.

## Initial coverage allocation

The initial target is 42 underlying scenarios: six per required query type.
Within every type, pre-assign four scenarios to development, one to validation,
and one to blind. Actual scenario selection may not move a scenario between
partitions after graph output, evaluation behavior, or tuning feedback is seen.

| Type | Meaning | Development | Validation | Blind | Total |
| --- | --- | ---: | ---: | ---: | ---: |
| `EC` | Error-code-led diagnostic question | 4 | 1 | 1 | 6 |
| `PHEN` | Phenomenon/symptom-led diagnostic question | 4 | 1 | 1 | 6 |
| `ASSET` | Asset/equipment-scope question | 4 | 1 | 1 | 6 |
| `AMB` | Ambiguous query requiring bounded interpretation or clarification | 4 | 1 | 1 | 6 |
| `PARTIAL` | Partial diagnostic-chain question with explicit missingness | 4 | 1 | 1 | 6 |
| `MULTI` | Multiple independently acceptable cause/action answers | 4 | 1 | 1 | 6 |
| `ABSTAIN` | No-hit or safety-bounded question requiring abstention | 4 | 1 | 1 | 6 |
| **Total** |  | **28** | **7** | **7** | **42** |

## Cross-cutting coverage targets

The registry owner assigns the following tags when an underlying scenario is
selected. The tags are coverage metadata, not labels.

| Dimension | Required target before baseline freeze |
| --- | --- |
| Equipment scope | At least one scenario each for station, module, component/sub-component, and cross-scope or scope-unknown handling. |
| Difficulty | Every query type includes low, medium, and high difficulty; no partition may contain only one difficulty. |
| Language | Include every supported evaluation language in both development and validation. A blind language allocation is fixed before labels are exposed. |
| Abstention | `ABSTAIN` scenarios use `required`; `AMB` may use `allowed` only when independently justified; other types default to `not_expected` until review changes them. |
| Multiple answers | `MULTI` scenarios retain all acceptable alternatives; no arbitrary single answer is selected for scoring convenience. |
| Missingness | `PARTIAL` scenarios must state what is unknown and must not turn missing context into an invented cause or action. |
| Source independence | Every future accepted label needs an independent governed source anchor; graph output is never an authority. |
| Label maturity | Development/calibration may use provisional labels. Reviewed domain-correctness and blind comparison use only `reviewed` or `adjudicated` labels. |

## Partition and leakage controls

1. Assign a partition by `scenario_id` before retrieving graph results or
   drafting ranking outputs.
2. Keep all variants, translations, near-duplicate wording, and the same
   underlying failure context in the same partition.
3. The blind partition is query-only for execution. Its labels remain in a
   separate governed location and are unavailable to graph construction,
   retrieval, prompt tuning, calibration, and metric debugging.
4. A capability exclusion is recorded explicitly; it is not converted into a
   pass, a no-hit label, or an abstention success.
5. Reclassification requires a recorded reason and independent quality review;
   never move a difficult scenario after observing an old- or new-KG result.

## Creation workflow

1. Create the 42 registry rows with only `scenario_id`, type, partition, and
   coverage tags. No data access is needed for this step.
2. Check the allocation and duplicate-scenario rules before writing queries.
3. With explicit permission for a bounded data scope, select source-backed
   representative cases and create records under
   `route_a_golden_case_v1`.
4. Domain reviewers annotate independently anchored acceptable causes and
   cause/action pairs; disagreements enter adjudication.
5. Export only reviewed/adjudicated labels to a reviewed expert-ranking run.
   Preserve provisional cases for framework/calibration evidence only.

## Freeze gate

Before the old-KG baseline, the data workflow lead verifies governance and
partition handling; the data contract engineer reviews contract compatibility;
domain reviewers approve label semantics; and the quality reviewer verifies
coverage, independence, duplicates, leakage controls, and calibration/mutation
readiness. The registry and labels are frozen separately. Neither JSON validity
nor a complete count of 42 freezes either artifact.
