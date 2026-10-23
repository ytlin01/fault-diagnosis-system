"""Route C related-case record assembly and lexical retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from services.routing.query_router import CASE_RETRIEVAL
from services.routing.route_c_source_boundary import project_route_c_record, route_c_target_for_source


CASE_RETRIEVAL_SOURCE_ID = "rag_fp_case_candidates_v1"
CASE_ROUTE_MARKER = "rag_case_pool"
DEFAULT_CASE_TOP_K = 3
DEFAULT_CASE_MIN_SCORE = 0.1

_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


@dataclass(frozen=True)
class RouteCCaseIndexRecord:
    """Retrieval-safe case candidate built from TASK-005 allowlisted fields."""

    case_id: str
    source_id: str
    source_record: Mapping[str, Any]
    indexed_text: str
    source_type: str
    relation_type: str


@dataclass(frozen=True)
class RouteCCaseSearchHit:
    """Ranked Route C related-case hit."""

    record: RouteCCaseIndexRecord
    score: float


def build_route_c_case_records(
    records: Sequence[Mapping[str, Any]],
    *,
    source_id: str = CASE_RETRIEVAL_SOURCE_ID,
    warnings: list[str] | None = None,
) -> list[RouteCCaseIndexRecord]:
    """Project raw case candidates into retrieval-safe index records."""
    if source_id != CASE_RETRIEVAL_SOURCE_ID or route_c_target_for_source(source_id) != CASE_RETRIEVAL:
        if warnings is not None:
            warnings.append(
                f"Route C case index blocked source `{source_id}`; only `{CASE_RETRIEVAL_SOURCE_ID}` is allowed."
            )
        return []

    index_records: list[RouteCCaseIndexRecord] = []
    for raw_record in records:
        projected = project_route_c_record(source_id, raw_record)
        if projected.get("route_target") != CASE_ROUTE_MARKER:
            if warnings is not None:
                warnings.append("Skipped Route C case candidate with non-case route_target.")
            continue

        case_id = str(projected.get("rag_candidate_id") or "").strip()
        if not case_id:
            if warnings is not None:
                warnings.append("Skipped Route C case candidate without rag_candidate_id.")
            continue

        indexed_text = assemble_case_index_text(projected)
        if not indexed_text:
            if warnings is not None:
                warnings.append(f"Skipped Route C case candidate `{case_id}` because indexed text is empty.")
            continue

        index_records.append(
            RouteCCaseIndexRecord(
                case_id=case_id,
                source_id=f"{source_id}:{case_id}",
                source_record=projected,
                indexed_text=indexed_text,
                source_type=str(projected.get("source_type") or ""),
                relation_type=str(projected.get("relation_type") or ""),
            )
        )
    return index_records


def search_route_c_cases(
    query_text: str,
    records: Sequence[Mapping[str, Any]],
    *,
    top_k: int = DEFAULT_CASE_TOP_K,
    min_score: float = DEFAULT_CASE_MIN_SCORE,
    source_id: str = CASE_RETRIEVAL_SOURCE_ID,
    warnings: list[str] | None = None,
) -> list[RouteCCaseSearchHit]:
    """Run the first lexical related-case baseline over projected case records."""
    index_records = build_route_c_case_records(records, source_id=source_id, warnings=warnings)
    return rank_route_c_case_records(query_text, index_records, top_k=top_k, min_score=min_score)


def rank_route_c_case_records(
    query_text: str,
    records: Sequence[RouteCCaseIndexRecord],
    *,
    top_k: int,
    min_score: float = DEFAULT_CASE_MIN_SCORE,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[RouteCCaseSearchHit]:
    if top_k <= 0:
        return []

    query_tokens = tokenize_for_route_c_case(query_text)
    if not query_tokens:
        return []

    tokenized_records = [tokenize_for_route_c_case(record.indexed_text) for record in records]
    if not tokenized_records:
        return []

    doc_count = len(tokenized_records)
    lengths = [len(tokens) for tokens in tokenized_records]
    avg_len = sum(lengths) / doc_count if doc_count else 0.0
    if avg_len <= 0:
        return []

    doc_freq: Counter[str] = Counter()
    for tokens in tokenized_records:
        doc_freq.update(set(tokens))

    query_counter = Counter(query_tokens)
    hits: list[RouteCCaseSearchHit] = []
    for record, tokens, length in zip(records, tokenized_records, lengths):
        if not tokens:
            continue
        token_counts = Counter(tokens)
        score = 0.0
        for token, query_weight in query_counter.items():
            term_freq = token_counts.get(token, 0)
            if not term_freq:
                continue
            idf = math.log(1 + (doc_count - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
            denominator = term_freq + k1 * (1 - b + b * length / avg_len)
            score += query_weight * idf * (term_freq * (k1 + 1)) / denominator
        if score >= min_score:
            hits.append(RouteCCaseSearchHit(record=record, score=score))

    hits.sort(key=lambda hit: (-hit.score, hit.record.case_id))
    return hits[:top_k]


def assemble_case_index_text(record: Mapping[str, Any]) -> str:
    """Assemble retrieval text from the TASK-005 case-candidate allowlist only."""
    parts = [
        record.get("field_fp_variants"),
        record.get("field_fp_normalized"),
        record.get("RC"),
        record.get("PA"),
        _evidence_text(record.get("evidence")),
        record.get("filter_basis", {}).get("reason") if isinstance(record.get("filter_basis"), Mapping) else None,
    ]
    return " ".join(_stringify(part) for part in parts if part not in (None, "", [], {})).strip()


def tokenize_for_route_c_case(value: Any) -> list[str]:
    text = str(value or "").lower()
    tokens: list[str] = []

    for match in _ASCII_TOKEN_RE.finditer(text):
        raw = match.group(0).strip("._/-")
        if len(raw) >= 2:
            tokens.append(raw)
        for part in re.split(r"[._/-]+", raw):
            if len(part) >= 2:
                tokens.append(part)

    for match in _CJK_RE.finditer(text):
        tokens.extend(_cjk_ngrams(match.group(0), 2))
        tokens.extend(_cjk_ngrams(match.group(0), 3))

    return tokens


def _evidence_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    fields = [
        value.get("count"),
        value.get("total_dt_mins"),
        value.get("risk_counts"),
        value.get("status_counts"),
        value.get("qpl_values"),
        value.get("date_range"),
    ]
    return " ".join(_stringify(field) for field in fields if field not in (None, "", [], {}))


def _stringify(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_stringify(item) for item in value)
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_stringify(item)}" for key, item in value.items())
    return str(value)


def _cjk_ngrams(value: str, size: int) -> list[str]:
    if len(value) < size:
        return [value] if len(value) >= 2 else []
    return [value[index : index + size] for index in range(0, len(value) - size + 1)]
