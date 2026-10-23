# Route B GraphRAG v1

> **Retired 2026-08-08.** The GraphRAG v1 implementation
> (`services/retrieval/route_b_graphrag.py`, the Neo4j export script, the eval
> runner, and its tests) has been removed. It depended on the superseded
> `route_b_evidence_v2` contract (replaced by the frozen `dekg_evidence_v2`
> contract) and never became the default Route B path — BM25 via
> `route_b_index.py` remains the default retriever. Retained as a historical
> method reference only.

## Purpose

Route B GraphRAG v1 builds a serving-safe document evidence graph for document
retrieval and Neo4j visualization. It is separate from the Route A reviewed
diagnosis KG and remains evidence-only.

## Artifacts

Generated artifacts:

```text
artifacts/route_b_graphrag_v1/route_b_graphrag_v1.json
artifacts/route_b_graphrag_v1/route_b_graphrag_v1.cypher
artifacts/route_b_graphrag_v1/cypher_parts/
```

The Cypher file can be opened in Neo4j Browser or run through `cypher-shell`.
Direct write is optional through:

```powershell
python scripts\export_route_b_graphrag_neo4j.py --write-neo4j
```

The write path reads Neo4j settings from `.env`:

```text
FAULTDX_NEO4J_HOST
FAULTDX_NEO4J_USER
FAULTDX_NEO4J_PASSWORD
```

If the Python `neo4j` package or Neo4j service is unavailable, the JSON and
Cypher export path still works.

For Neo4j Desktop import instructions, see:

```text
docs/data/route_b_graphrag_neo4j_desktop_runbook.md
```

## Graph Shape

The graph contains:

| Node/edge | Purpose | Validator outcome |
| --- | --- | --- |
| `DocumentAsset` / `RouteBDocument` | schema 3.0 aligned serving document node | `published_graph` in Route B evidence graph |
| `RouteBBlock` | serving-safe block/chunk evidence anchor | `candidate_review` |
| `RouteBConcept` | extracted retrieval concept, not a diagnosis fact | `candidate_review` |
| `HAS_EVIDENCE_BLOCK` | document-to-block evidence relation | `candidate_review` |
| `MENTIONS_CONCEPT` | block-to-concept retrieval relation | `candidate_review` |
| `NEXT_BLOCK` | same-document adjacency | `candidate_review` |

Current export summary:

```text
schema_version: diagnostic_schema_v4_0
nodes: 4941
edges: 12276
validator_summary:
  published_graph: 3
  candidate_review: 17214
  rejection: 0
```

## schema 3.0 and Validator Policy

schema 3.0 is used as the source of truth for graph semantics and publication
policy. In this first Route B graph:

- `DocumentAsset` is the only schema 3.0 published node type.
- Block/concept/adjacency objects are Route B support artifacts, not Route A KG
  facts.
- Support artifacts remain `candidate_review`.
- No graph item is allowed to become confirmed diagnosis.
- Raw/internal sources and forbidden fields are rejected by validator checks.

This keeps the graph useful in Neo4j while avoiding accidental promotion of
document evidence into reviewed diagnosis.

## `/api/diagnose` Projection

GraphRAG search hits can be projected into result API v1 Route B shape:

```text
decision.route_family = route_b_document
decision.route = document_evidence_retrieval
decision.answer_type = document_evidence
decision.status = evidence_only
diagnosis_results[].result_type = document_evidence
diagnosis_results[].status = evidence_only
evidence[].source_type = serving_document
evidence[].evidence_type = document_snippet
```

The projection intentionally does not include graph internals as extra API
fields, because `legacy/root/result_design_v1_schema.json` disallows unknown properties.

## Benchmark

Command:

```powershell
python scripts\run_eval\run_route_b_graphrag_v1.py
```

TASK-018 benchmark v0 comparison:

| Metric | BM25 baseline | Route B GraphRAG v1 |
| --- | ---: | ---: |
| source_safety_pass | 35/35 | 35/35 |
| anchor_correct | 28/28 | 28/28 |
| top1_block_hit | 24/28 | 26/28 |
| top3_block_hit | 27/28 | 28/28 |
| mrr | 0.9196 | 0.9524 |
| no_hit_precision | 7/7 | 7/7 |

## Boundary

Route B GraphRAG v1 is not the default Route B executor path yet. It should
remain a separately invoked, benchmarked path until a later adoption decision.
