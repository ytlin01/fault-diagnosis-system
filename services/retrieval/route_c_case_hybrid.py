"""Opt-in local vector and hybrid ranking prototypes for Route C eval."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from services.retrieval.route_c_case_index import (
    CASE_RETRIEVAL_SOURCE_ID,
    DEFAULT_CASE_MIN_SCORE,
    RouteCCaseIndexRecord,
    RouteCCaseSearchHit,
    build_route_c_case_records,
    rank_route_c_case_records,
    tokenize_for_route_c_case,
)


DEFAULT_VECTOR_MIN_SCORE = 0.1
DEFAULT_HYBRID_LEXICAL_WEIGHT = 0.7
DEFAULT_HYBRID_VECTOR_WEIGHT = 0.3


@dataclass(frozen=True)
class RouteCCaseHybridScore:
    """Debug score for opt-in Route C ranking comparison."""

    case_id: str
    lexical_score: float
    vector_score: float
    combined_score: float


def search_route_c_cases_vector(
    query_text: str,
    records: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    min_score: float = DEFAULT_VECTOR_MIN_SCORE,
    source_id: str = CASE_RETRIEVAL_SOURCE_ID,
    warnings: list[str] | None = None,
) -> list[RouteCCaseSearchHit]:
    """Rank cases by local sparse-vector cosine over allowlisted text only."""
    index_records = build_route_c_case_records(records, source_id=source_id, warnings=warnings)
    return rank_route_c_case_records_vector(query_text, index_records, top_k=top_k, min_score=min_score)


def search_route_c_cases_hybrid(
    query_text: str,
    records: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    min_score: float = DEFAULT_CASE_MIN_SCORE,
    source_id: str = CASE_RETRIEVAL_SOURCE_ID,
    lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
    warnings: list[str] | None = None,
) -> list[RouteCCaseSearchHit]:
    """Rank cases with normalized BM25 plus local sparse-vector cosine."""
    index_records = build_route_c_case_records(records, source_id=source_id, warnings=warnings)
    return rank_route_c_case_records_hybrid(
        query_text,
        index_records,
        top_k=top_k,
        min_score=min_score,
        lexical_weight=lexical_weight,
        vector_weight=vector_weight,
    )


def rank_route_c_case_records_vector(
    query_text: str,
    records: Sequence[RouteCCaseIndexRecord],
    *,
    top_k: int,
    min_score: float = DEFAULT_VECTOR_MIN_SCORE,
) -> list[RouteCCaseSearchHit]:
    if top_k <= 0:
        return []

    query_vector = _sparse_vector(query_text)
    if not query_vector:
        return []

    hits: list[RouteCCaseSearchHit] = []
    for record in records:
        score = _cosine_similarity(query_vector, _sparse_vector(record.indexed_text))
        if score >= min_score:
            hits.append(RouteCCaseSearchHit(record=record, score=score))

    hits.sort(key=lambda hit: (-hit.score, hit.record.case_id))
    return hits[:top_k]


def rank_route_c_case_records_hybrid(
    query_text: str,
    records: Sequence[RouteCCaseIndexRecord],
    *,
    top_k: int,
    min_score: float = DEFAULT_CASE_MIN_SCORE,
    lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
) -> list[RouteCCaseSearchHit]:
    if top_k <= 0:
        return []
    if lexical_weight < 0 or vector_weight < 0:
        raise ValueError("Route C hybrid weights must be non-negative.")

    lexical_hits = rank_route_c_case_records(
        query_text,
        records,
        top_k=len(records),
        min_score=0.0,
    )
    lexical_by_id = {hit.record.case_id: hit.score for hit in lexical_hits}
    max_lexical = max(lexical_by_id.values(), default=0.0)
    query_vector = _sparse_vector(query_text)

    hits: list[RouteCCaseSearchHit] = []
    for record in records:
        lexical_score = lexical_by_id.get(record.case_id, 0.0)
        normalized_lexical = lexical_score / max_lexical if max_lexical > 0 else 0.0
        vector_score = _cosine_similarity(query_vector, _sparse_vector(record.indexed_text))
        combined = lexical_weight * normalized_lexical + vector_weight * vector_score
        if combined >= min_score:
            hits.append(RouteCCaseSearchHit(record=record, score=combined))

    hits.sort(key=lambda hit: (-hit.score, hit.record.case_id))
    return hits[:top_k]


def explain_route_c_case_hybrid_scores(
    query_text: str,
    records: Sequence[RouteCCaseIndexRecord],
    *,
    lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT,
    vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT,
) -> list[RouteCCaseHybridScore]:
    """Return comparable debug scores without changing result semantics."""
    lexical_hits = rank_route_c_case_records(query_text, records, top_k=len(records), min_score=0.0)
    lexical_by_id = {hit.record.case_id: hit.score for hit in lexical_hits}
    max_lexical = max(lexical_by_id.values(), default=0.0)
    query_vector = _sparse_vector(query_text)
    scores: list[RouteCCaseHybridScore] = []
    for record in records:
        lexical_score = lexical_by_id.get(record.case_id, 0.0)
        normalized_lexical = lexical_score / max_lexical if max_lexical > 0 else 0.0
        vector_score = _cosine_similarity(query_vector, _sparse_vector(record.indexed_text))
        scores.append(
            RouteCCaseHybridScore(
                case_id=record.case_id,
                lexical_score=lexical_score,
                vector_score=vector_score,
                combined_score=lexical_weight * normalized_lexical + vector_weight * vector_score,
            )
        )
    scores.sort(key=lambda score: (-score.combined_score, score.case_id))
    return scores


def _sparse_vector(value: Any) -> Counter[str]:
    return Counter(tokenize_for_route_c_case(value))


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = set(left).intersection(right)
    numerator = sum(left[token] * right[token] for token in overlap)
    if numerator <= 0:
        return 0.0
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return numerator / (left_norm * right_norm)
