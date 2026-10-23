"""Route C candidate/catalog/governance executor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from services.routing.query_router import CASE_RETRIEVAL, FP_REVIEW_GOVERNANCE, STRUCTURED_CATALOG
from services.routing.route_c_source_boundary import (
    blocked_route_c_material,
    project_route_c_record,
    route_c_policy,
    route_c_source_metadata,
    route_c_target_for_source,
)
from services.retrieval.route_c_case_index import (
    DEFAULT_CASE_MIN_SCORE,
    search_route_c_cases,
)
from services.retrieval.route_c_case_hybrid import (
    search_route_c_cases_hybrid,
    search_route_c_cases_vector,
)
from services.retrieval.route_c_case_light_rag import route_c_case_light_rag
from services.retrieval.route_c_qwen_vector import (
    DEFAULT_INDEX_DIR as DEFAULT_QWEN_INDEX_DIR,
    DEFAULT_MODEL as DEFAULT_QWEN_MODEL,
    DEFAULT_VECTOR_MIN_SCORE as DEFAULT_QWEN_MIN_SCORE,
    search_route_c_qwen_cases,
)
from services.providers.llm import BaseProvider


DEFAULT_SOURCE_PATHS = {
    "rag_fp_case_candidates_v1": Path("data/processed/aggregates/rag_fp_case_candidates_v1.json"),
    "structured_fp_join_v1_baseline": Path("data/processed/aggregates/structured_fp_join_v1_baseline.json"),
    "error_codes_standardized_serving": Path("data/serving_structured/error_codes_standardized_serving.json"),
}
DEFAULT_TOP_K = 3


def execute_route_c(
    query_text: str,
    *,
    route: str,
    allowed_sources: Iterable[str],
    source_paths: Mapping[str, str | Path] | None = None,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_CASE_MIN_SCORE,
    case_ranking_strategy: str = "lexical_bm25",
    case_hybrid_config: Mapping[str, Any] | None = None,
    vector_index_path: str | Path = DEFAULT_QWEN_INDEX_DIR,
    vector_ollama_url: str = "http://127.0.0.1:11434",
    vector_model: str = DEFAULT_QWEN_MODEL,
    vector_min_score: float = DEFAULT_QWEN_MIN_SCORE,
    enable_light_rag: bool = False,
    light_rag_config: Mapping[str, Any] | None = None,
    light_rag_provider: BaseProvider | None = None,
) -> dict[str, Any]:
    policy = route_c_policy()
    if bool(policy.get("route_c_may_emit_confirmed_diagnosis", True)):
        return _empty_output("Route C policy is unsafe: confirmed diagnosis emission must be disabled.")

    path_map = dict(DEFAULT_SOURCE_PATHS)
    for source_id, path in dict(source_paths or {}).items():
        path_map[str(source_id)] = Path(path)

    warnings: list[str] = []
    results: list[tuple[float, dict[str, Any]]] = []
    used_sources: list[dict[str, Any]] = []
    source_metadata: list[dict[str, Any]] = []
    blocked_material = blocked_route_c_material()

    for source_id in allowed_sources:
        source_id = str(source_id)
        if source_id in blocked_material:
            warnings.append(f"Blocked Route C source `{source_id}`: {blocked_material[source_id]}")
            continue
        if route_c_target_for_source(source_id) != route:
            continue
        path = path_map.get(source_id)
        if path is None:
            warnings.append(f"Route C source `{source_id}` has no configured artifact path.")
            continue
        used_sources.append(_knowledge_source(source_id, route))
        source_metadata.append({"source_id": source_id, **route_c_source_metadata(source_id)})
        records = _load_records(source_id, path, warnings)
        if not records:
            continue
        if route == CASE_RETRIEVAL:
            hits = _search_case_records(
                query_text,
                records,
                source_id=source_id,
                top_k=top_k,
                min_score=min_score,
                strategy=case_ranking_strategy,
                hybrid_config=case_hybrid_config,
                vector_index_path=vector_index_path,
                vector_ollama_url=vector_ollama_url,
                vector_model=vector_model,
                vector_min_score=vector_min_score,
                warnings=warnings,
            )
            resolved_light_rag_config = dict(light_rag_config or {})
            resolved_light_rag_config["enabled"] = enable_light_rag or bool(
                resolved_light_rag_config.get("enabled", False)
            )
            light_rag = route_c_case_light_rag(
                query_text,
                hits,
                config=resolved_light_rag_config,
                provider=light_rag_provider,
            )
            warnings.extend(light_rag.warnings)
            summaries = dict(light_rag.summaries)
            for rank_boost, hit in enumerate(light_rag.hits):
                summary = summaries.get(hit.record.case_id)
                rerank_score = float(len(light_rag.hits) - rank_boost)
                results.append(
                    (
                        rerank_score if enable_light_rag else hit.score,
                        _result_for_record(
                            route,
                            source_id,
                            hit.record.source_record,
                            candidate_summary=summary,
                        ),
                    )
                )
            continue
        for record in records:
            projected = project_route_c_record(source_id, record)
            score = _score_record(query_text, projected)
            if score <= 0:
                continue
            results.append((score, _result_for_record(route, source_id, projected)))

    results.sort(key=lambda item: item[0], reverse=True)
    items = [item for _, item in results[: max(0, top_k)]]
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank

    if not items and not warnings:
        warnings.append("No matching Route C candidate/catalog record was found.")

    return {
        "items": items,
        "used_sources": used_sources,
        "source_metadata": source_metadata,
        "warnings": warnings,
    }


def _search_case_records(
    query_text: str,
    records: list[Mapping[str, Any]],
    *,
    source_id: str,
    top_k: int,
    min_score: float,
    strategy: str,
    hybrid_config: Mapping[str, Any] | None,
    vector_index_path: str | Path,
    vector_ollama_url: str,
    vector_model: str,
    vector_min_score: float,
    warnings: list[str],
):
    strategy_key = str(strategy or "lexical_bm25").strip().lower()
    if strategy_key == "lexical_bm25":
        return search_route_c_cases(
            query_text,
            records,
            source_id=source_id,
            top_k=top_k,
            min_score=min_score,
            warnings=warnings,
        )
    if strategy_key == "local_sparse_vector":
        return search_route_c_cases_vector(
            query_text,
            records,
            source_id=source_id,
            top_k=top_k,
            min_score=min_score,
            warnings=warnings,
        )
    if strategy_key == "hybrid_bm25_local_sparse_vector":
        config = dict(hybrid_config or {})
        return search_route_c_cases_hybrid(
            query_text,
            records,
            source_id=source_id,
            top_k=top_k,
            min_score=min_score,
            lexical_weight=float(config.get("lexical_weight", 0.7)),
            vector_weight=float(config.get("vector_weight", 0.3)),
            warnings=warnings,
        )
    if strategy_key in {"ollama_vector", "qwen3_embedding"}:
        try:
            return search_route_c_qwen_cases(
                query_text,
                index_dir=vector_index_path,
                source_id=source_id,
                top_k=top_k,
                min_score=vector_min_score,
                ollama_url=vector_ollama_url,
                model=vector_model,
                warnings=warnings,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            warnings.append(f"Route C Qwen vector retrieval unavailable; lexical BM25 retained: {exc}")
            return search_route_c_cases(
                query_text,
                records,
                source_id=source_id,
                top_k=top_k,
                min_score=min_score,
                warnings=warnings,
            )
    warnings.append(f"Unsupported Route C case ranking strategy `{strategy}`; lexical BM25 retained.")
    return search_route_c_cases(
        query_text,
        records,
        source_id=source_id,
        top_k=top_k,
        min_score=min_score,
        warnings=warnings,
    )


def _load_records(source_id: str, path: Path, warnings: list[str]) -> list[Mapping[str, Any]]:
    if not path.exists():
        warnings.append(f"Route C source `{source_id}` is unavailable: {path}")
        return []
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Skipped unreadable Route C source `{source_id}`: {exc}")
        return []

    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    if source_id == "rag_fp_case_candidates_v1":
        records = payload.get("candidates", [])
    elif source_id == "structured_fp_join_v1_baseline":
        records = payload.get("records", [])
    else:
        records = payload.get("records", payload.get("items", []))
    return [record for record in records if isinstance(record, Mapping)] if isinstance(records, list) else []


def _result_for_record(
    route: str,
    source_id: str,
    record: Mapping[str, Any],
    *,
    candidate_summary: str | None = None,
) -> dict[str, Any]:
    source_type = _source_type(route)
    evidence_type = _evidence_type(route)
    record_id = _record_id(source_id, record)
    title = _title(route, record)
    description = _description(record)
    if candidate_summary:
        description = _truncate(f"{description} | Candidate-only relevance note: {candidate_summary}", 420)
    result_type = "case_reference" if route == CASE_RETRIEVAL else "diagnostic_hypothesis"
    evidence = {
        "evidence_type": evidence_type,
        "source_type": source_type,
        "source_name": source_id,
        "source_id": record_id,
        "anchor": record_id,
        "reviewed": False,
        "serving_safe": True,
        "summary": description,
    }
    result: dict[str, Any] = {
        "rank": 0,
        "title": title,
        "result_type": result_type,
        "status": "candidate",
        "confidence": "low" if route == FP_REVIEW_GOVERNANCE else "medium",
        "description": description,
        "evidence": [evidence],
    }
    actions = _actions(record, source_id)
    if actions:
        result["actions"] = actions
    return result


def _score_record(query_text: str, record: Mapping[str, Any]) -> int:
    query = _normalize(query_text)
    text = _normalize(_flatten(record))
    if not query or not text:
        return 0
    score = 0
    if query in text:
        score += 8
    for token in _tokens(query):
        if token in text:
            score += 4 if _looks_like_code(token) else 2
    return score


def _flatten(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return "" if value is None else str(value)


def _actions(record: Mapping[str, Any], source_id: str) -> list[dict[str, Any]]:
    raw_actions = record.get("PA") or record.get("RA") or record.get("action")
    if raw_actions in (None, ""):
        return []
    values = raw_actions if isinstance(raw_actions, list) else [raw_actions]
    actions: list[dict[str, Any]] = []
    for index, value in enumerate(values, start=1):
        if value in (None, ""):
            continue
        actions.append(
            {
                "step": index,
                "action": str(value),
                "expected_time": None,
                "tool_required": None,
                "source_status": "candidate_supported",
                "reference": {"source_name": source_id, "anchor": _record_id(source_id, record)},
            }
        )
    return actions


def _knowledge_source(source_id: str, route: str) -> dict[str, Any]:
    return {
        "source_type": _source_type(route),
        "source_id": source_id,
        "snapshot_id": None,
        "updated_at": None,
    }


def _source_type(route: str) -> str:
    if route == STRUCTURED_CATALOG:
        return "structured_catalog"
    if route == CASE_RETRIEVAL:
        return "structured_case_candidate"
    return "governance_candidate"


def _evidence_type(route: str) -> str:
    if route == STRUCTURED_CATALOG:
        return "structured_catalog"
    return "related_case"


def _title(route: str, record: Mapping[str, Any]) -> str:
    if route == STRUCTURED_CATALOG:
        code = record.get("Error code") or record.get("EC") or "catalog item"
        return f"结构化目录候选：{code}"
    if route == CASE_RETRIEVAL:
        return "相似案例候选"
    return "FP 复核治理候选"


def _description(record: Mapping[str, Any]) -> str:
    fields = (
        record.get("Description"),
        record.get("standard_fp"),
        record.get("FP"),
        record.get("field_fp_variants"),
        record.get("RC"),
        record.get("PA"),
        record.get("filter_basis", {}).get("reason") if isinstance(record.get("filter_basis"), Mapping) else None,
    )
    parts = [_stringify(field) for field in fields if field not in (None, "", [], {})]
    return _truncate(" | ".join(parts), 420) if parts else "Candidate record from governed Route C source."


def _record_id(source_id: str, record: Mapping[str, Any]) -> str:
    for field in ("rag_candidate_id", "mapping_id", "Index", "id", "record_id"):
        if record.get(field) not in (None, ""):
            return f"{source_id}:{record[field]}"
    return source_id


def _stringify(value: Any) -> str:
    if isinstance(value, list):
        return " ; ".join(_stringify(item) for item in value)
    if isinstance(value, Mapping):
        return " ".join(f"{key}={_stringify(item)}" for key, item in value.items())
    return str(value)


def _tokens(value: str) -> list[str]:
    return [token for token in value.replace("_", " ").replace("-", " ").split() if len(token) >= 2]


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _looks_like_code(token: str) -> bool:
    return any(char.isdigit() for char in token) and any(char.isalpha() for char in token)


def _truncate(value: str, limit: int) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _empty_output(warning: str) -> dict[str, Any]:
    return {"items": [], "used_sources": [], "source_metadata": [], "warnings": [warning]}
