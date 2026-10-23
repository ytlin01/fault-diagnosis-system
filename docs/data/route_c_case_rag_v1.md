# Route C Case RAG v1 Baseline

## Purpose

TASK-017 introduces the first Route C related-case retrieval baseline for
`rag_fp_case_candidates_v1`.

This is a lexical baseline, not a default vector-RAG-first path. The goal is to
stabilize the reusable retrieval foundation before later vector or hybrid
upgrades:

- allowlisted case record assembly;
- stable candidate IDs;
- retrieval-safe metadata;
- configurable top-k and score threshold;
- candidate-only `/api/diagnose` result behavior.

Compared with TASK-013's deterministic Route C scan, this task makes the case
branch an explicit record-index and ranking contract. It is still a baseline,
not a production RAG stack.

## Source Boundary

Route C case retrieval indexes exactly one source:

```text
rag_fp_case_candidates_v1 -> case_retrieval
```

It must not index:

- `structured_fp_join_v1_baseline`;
- `structured_fp_join_v1_semantic`;
- broad `data/processed/aggregates/` directory scans.

`structured_fp_join_v1_baseline` remains governance material under
`fp_review_governance`. `error_codes_standardized_serving` remains catalog-only
under `structured_catalog`. Reviewed Route A promotion requires a separate
reviewed artifact and a later Route A executor task.

## Index Record Schema

Case index records are built by `services/retrieval/route_c_case_index.py`.

Each index record uses:

| Field | Source |
| --- | --- |
| `case_id` | `rag_candidate_id` |
| `source_id` | `rag_fp_case_candidates_v1:{rag_candidate_id}` |
| `source_record` | TASK-005 allowlist projection only |
| `indexed_text` | allowlisted retrieval text assembly |
| `source_type` | projected `source_type` |
| `relation_type` | projected `relation_type` |

Records without `rag_candidate_id`, empty indexed text, or
`route_target != rag_case_pool` are skipped with warnings.

## Text Assembly

The lexical text is assembled only from fields allowlisted in
`configs/route_c_source_boundary_v1.json` for `rag_fp_case_candidates_v1`:

- `field_fp_variants`
- `field_fp_normalized`
- `RC`
- `PA`
- selected `evidence` summary fields
- `filter_basis.reason`

Fields such as `standard_fp`, `EC`, `semantic_score`, local paths, raw records,
or non-allowlisted debug fields are not indexed for this Route C baseline.

## Ranking

The current ranking is lexical BM25 over mixed ASCII and CJK-style n-gram
tokens. Defaults are configurable through executor arguments and documented in
`configs/base.yaml`:

```yaml
retrieval:
  route_c:
    case_source_id: rag_fp_case_candidates_v1
    case_ranking: lexical_bm25
    case_top_k: 3
    case_min_score: 0.1
```

This baseline is intentionally auditable. Later vector or hybrid upgrades
should preserve the same source boundary, stable IDs, allowlist projection, and
candidate-only output semantics.

## Result Behavior

Route C case retrieval still returns the existing `result_design_v1` shape.
It does not change `/api/diagnose` response schema.

Case results use:

- `result_type=case_reference`
- `status=candidate`
- evidence `evidence_type=related_case`
- evidence `source_type=structured_case_candidate`
- action `source_status=candidate_supported`

Route C case retrieval must never emit `confirmed_diagnosis`, `reviewed`, or
Route A source types such as `reviewed_structured_chain`.

## Eval Boundary

TASK-017 reuses existing TASK-009 eval fixtures:

- `data/eval/phase1_case_retrieval_eval_v0.json`
- relevant Route C safety cases from
  `data/eval/phase1_safety_negative_eval_v0.json`

The current case-retrieval fixtures check source policy and candidate-only
behavior. They do not yet provide gold `rag_candidate_id` labels, so top-1 and
top-3 related-case hit metrics are only available for synthetic/unit fixtures
until a later unified Route B/C retrieval benchmark adds stable gold IDs.
