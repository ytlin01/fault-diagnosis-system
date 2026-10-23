# Route C Case Hybrid Retrieval Eval

## Purpose

TASK-028 evaluates whether Route C related-case retrieval should upgrade from
the TASK-017 lexical BM25 baseline and TASK-027 light-RAG stub path to vector or
hybrid retrieval.

This is an eval and decision note, not a default runtime migration. Route C
case retrieval remains candidate-only and continues to use only:

```text
rag_fp_case_candidates_v1 -> case_retrieval
```

Blocked materials remain outside this task:

- `structured_fp_join_v1_baseline` for case retrieval;
- `structured_fp_join_v1_semantic`;
- broad `data/processed/aggregates/` directory scans.

## Preconditions

TASK-026 is complete and provides the comparison gate:

- total cases: 8
- positive cases: 6
- no-hit cases: 2
- label gaps recorded from TASK-009: 3
- lexical BM25 baseline top1/top3: 5/6 and 5/6
- lexical BM25 baseline MRR: 0.8542
- known hard miss: `RCBENCH-0006`

TASK-027 is also complete. Its deterministic light-RAG stub preserves the
contract and safety behavior but does not improve retrieval quality over
lexical BM25.

## Compared Strategies

All strategies use the same benchmark fixture:

```text
data/eval/route_c/route_c_case_benchmark_v0.json
```

All strategies consume the same governed candidate artifact:

```text
data/processed/aggregates/rag_fp_case_candidates_v1.json
```

Compared strategies:

| Strategy | Implementation | Provider use | Default runtime path |
| --- | --- | --- | --- |
| `lexical_only` | TASK-017 BM25 | none | yes |
| `light_rag_stub` | TASK-027 stub rerank/summary | deterministic stub only | no, explicit opt-in |
| `local_sparse_vector` | local token sparse-vector cosine | none | no, explicit eval flag |
| `hybrid_bm25_local_sparse_vector` | normalized BM25 + local vector score | none | no, explicit eval flag |

The vector/hybrid prototype is deliberately local and deterministic. It is not
a claim about a production semantic embedding model. It exists to test the
ranking, source-safety, candidate-only, and operational shape before introducing
embedding caches or provider dependencies.

## Source-Safety Rules

The vector/hybrid prototype uses `build_route_c_case_records()`, so its text is
assembled from the TASK-005/TASK-017 allowlisted projection only:

- `field_fp_variants`
- `field_fp_normalized`
- `RC`
- `PA`
- selected `evidence` summary fields
- `filter_basis.reason`

The prototype does not index or send:

- raw records;
- local paths;
- `source_refs`;
- `standard_fp`;
- `semantic_score`;
- debug fields;
- unallowlisted aggregate fields.

No external embedding or provider call was used in TASK-028.

## Benchmark Command

```powershell
python scripts\run_eval\run_route_c_case_benchmark_v0.py --compare-hybrid --json
```

## Results

| Strategy | top1 | top3 | MRR | candidate-only | source-safety | no-hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `lexical_only` | 5/6 | 5/6 | 0.8542 | 8/8 | 8/8 | 2/2 |
| `light_rag_stub` | 5/6 | 5/6 | 0.8542 | 8/8 | 8/8 | 2/2 |
| `local_sparse_vector` | 2/6 | 4/6 | 0.5278 | 8/8 | 8/8 | 2/2 |
| `hybrid_bm25_local_sparse_vector` | 5/6 | 5/6 | 0.8333 | 8/8 | 8/8 | 2/2 |

`RCBENCH-0006` remains unresolved. The expected candidate is
`RAG_6890abacba460aa1`. The query is an English paraphrase, while the candidate
text is primarily Chinese:

```text
C1STN QPL_1 上料轴掉使能，回零过程中料盘打翻
```

The local vector prototype cannot bridge that bilingual paraphrase gap. The
hybrid strategy keeps safety behavior intact but does not improve top1/top3 and
slightly reduces MRR.

## Operational Cost

Keeping lexical BM25 has the lowest operating cost:

- no embedding cache;
- no provider dependency;
- deterministic local ranking;
- simple refresh behavior when `rag_fp_case_candidates_v1` changes;
- fully reproducible benchmark results.

Adopting production vector retrieval would add:

- embedding model/provider selection;
- cache generation and refresh logic;
- cache lineage and invalidation tied to `rag_candidate_id`;
- reproducibility controls for model/version drift;
- additional source-safety review for embedding text;
- fallback behavior when provider/cache is unavailable.

Given the current benchmark, those costs are not justified.

## Decision

Recommendation: defer Route C vector/hybrid adoption and keep lexical BM25 as
the default Route C case retrieval baseline. Keep TASK-027 light-RAG as an
explicit opt-in contract path for approved local/provider experiments, not as a
quality-proven default.

Revisit hybrid/vector only when at least one of the following is true:

- reviewed benchmark coverage grows enough to represent real Route C usage;
- bilingual or paraphrase misses exceed a defined threshold;
- an approved local embedding model is available and benchmarked without source
  or candidate-only regressions;
- vector/hybrid improves top3 and MRR over lexical BM25 while preserving 100%
  candidate-only, source-safety, and no-hit behavior.

Future reviewed Route A promotion remains separate. A related case candidate
must not become `confirmed_diagnosis` or `reviewed` through Route C retrieval
alone.
