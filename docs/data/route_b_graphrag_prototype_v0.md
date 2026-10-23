# Route B GraphRAG Prototype v0

> **Retired 2026-08-08.** The prototype implementation
> (`services/retrieval/route_b_graphrag_prototype.py`, its eval runner, and unit
> test) has been removed; the experiment did not outperform lexical retrieval and
> was never the default Route B path. This document is retained as a historical
> method reference only — the runner command referenced below no longer exists.

## Purpose

This document records the TASK-020 Route B GraphRAG-style prototype and shows
the full Route B chain on the current benchmark. It is an engineering
showcase, not a production GraphRAG design.

Markdown is the source-of-truth format for this prototype. HTML is deferred to
future interactive demo work, and LaTeX is deferred to later polished reports.

## Boundary

The prototype consumes only serving-safe Route B document chunks derived from:

```text
data/serving_unstructured_vlm/
```

It does not read raw data, internal canonical data, processed VLM data, masked
canonical data, image assets, local paths, raw VLM responses, endpoint fields,
or debug fields.

The default Route B executor still uses the TASK-016 BM25 baseline. The
prototype is invoked only by the TASK-020 comparison runner.

## Chain Overview

```text
user query
  -> TASK-016 serving-safe chunk view
  -> BM25 candidate retrieval
  -> lightweight document-structure / concept rerank
  -> TASK-018 benchmark comparison
  -> result semantics remain document_evidence + evidence_only
```

The prototype does not write Route B graph candidates into the Route A reviewed
diagnosis KG. It does not emit confirmed diagnosis.

## Prototype Signal

The prototype reranks BM25 candidates using explainable, source-safe signals:

| Signal | Purpose | Safety note |
| --- | --- | --- |
| BM25 normalized score | Preserve lexical baseline relevance | Uses existing TASK-016 chunks |
| Schema/concept overlap | Reward candidates that cover query action/component concepts | Uses a small static alias map, no external model |
| VLM cap | Prevent `vlm_text` from dominating rerank by itself | VLM-derived evidence remains evidence-only |

The current concept aliases cover a small set of manufacturing action/component
terms such as automatic, take, install, screw, CG, cowling, and sensor. This is
not a confirmed diagnosis ontology and should not be written into Route A KG.

## Benchmark Result

Command:

```powershell
python scripts\run_eval\run_route_b_graphrag_prototype_v0.py
```

Comparison on TASK-018 benchmark v0:

| Metric | BM25 baseline | Prototype v0 |
| --- | ---: | ---: |
| total cases | 35 | 35 |
| positive cases | 28 | 28 |
| no-hit cases | 7 | 7 |
| source_safety_pass | 35/35 | 35/35 |
| anchor_correct | 28/28 | 28/28 |
| top1_block_hit | 24/28 | 24/28 |
| top3_block_hit | 27/28 | 28/28 |
| mrr | 0.9196 | 0.9226 |
| no_hit_precision | 7/7 | 7/7 |

The prototype improves the known top-3 miss without changing source safety or
no-hit precision.

## Hard Case: RBBENCH-0021

Query:

```text
C1STN automatic take Sensor cowling install to CG screw
```

Expected block:

```text
C1STN-_SOPV1.2_8aff482b6083:b0126
```

BM25 ranked the expected block at rank 4. Prototype v0 moves it to rank 3.

| Rank | Block | BM25 norm | Concept score | Matched concepts |
| ---: | --- | ---: | ---: | --- |
| 1 | `DFM_C1STN_V1.2_-_0416_aaffe6b828ae:b0007` | 1.0000 | 0.7143 | install, screw, cg, cowling, sensor |
| 2 | `DFM_C1STN_V1.2_-_0416_aaffe6b828ae:b0000` | 0.8600 | 0.5714 | install, screw, cg, cowling |
| 3 | `C1STN-_SOPV1.2_8aff482b6083:b0126` | 0.5032 | 1.0000 | automatic, take, install, screw, cg, cowling, sensor |
| 4 | `DFM_C1STN_V1.2_-_0416_aaffe6b828ae:b0025` | 0.5888 | 0.8571 | take, install, screw, cg, cowling, sensor |
| 5 | `C1STN-_SOPV1.2_8aff482b6083:b0149` | 0.4849 | 0.7143 | take, install, cg, cowling, sensor |

The expected block wins enough structure/concept support because it covers all
active query concepts while staying anchored to the serving-safe SOP block.

Evidence snippet:

```text
C1STN 設備：自動取 Sensor cowling, 自動安裝到 CG 上，並自動鎖螺絲固定。
```

Result semantics remain:

```text
result_type = document_evidence
status = evidence_only
source_type = serving_document
reviewed = false
serving_safe = true
```

## Interpretation

The current result is a small positive signal, not a production adoption
decision.

What looks useful:

- The prototype fixes the only top-3 miss in benchmark v0.
- No-hit precision stays at 7/7.
- Source safety stays at 35/35.
- The rerank reasons are explainable.

What should not be concluded yet:

- This does not prove that full GraphRAG is needed.
- This does not justify defaulting Route B to GraphRAG.
- This does not validate a persistent graph store.
- This does not create reviewed diagnostic facts.

## Next Review Questions

- Is the static concept alias map acceptable as a controlled prototype signal,
  or should it become a reviewed config before any wider use?
- Should the next experiment compare this rerank against a lighter lexical
  query-expansion baseline?
- Are more mixed cases needed before deciding whether graph-style rerank is
  worth keeping?
- Should `vlm_text` remain capped at the current level, or should VLM-only
  candidates always require manual review before influencing top-3 ranking?
