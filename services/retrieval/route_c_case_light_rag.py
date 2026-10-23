"""Controlled light-RAG adapter for Route C related-case candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from services.providers.llm import (
    BaseProvider,
    CompanyApiProvider,
    OllamaProvider,
    ProviderRequest,
    StubProvider,
)
from services.retrieval.route_c_case_index import (
    CASE_RETRIEVAL_SOURCE_ID,
    RouteCCaseSearchHit,
)


DEFAULT_LIGHT_RAG_PROVIDER_TYPE = "stub"
DEFAULT_LIGHT_RAG_MAX_SUMMARY_CHARS = 220
_ALLOWED_PROMPT_FIELDS = {
    "rag_candidate_id",
    "source_type",
    "relation_type",
    "route_target",
    "field_fp_variants",
    "field_fp_normalized",
    "RC",
    "PA",
    "evidence",
    "filter_basis",
}
_ALLOWED_EVIDENCE_FIELDS = {
    "count",
    "total_dt_mins",
    "risk_counts",
    "status_counts",
    "qpl_values",
    "date_range",
}
_BANNED_SUMMARY_TERMS = (
    "confirmed",
    "confirmed diagnosis",
    "confirmed_diagnosis",
    "reviewed",
    "reviewed diagnosis",
    "reviewed_structured_chain",
    '"status": "reviewed"',
    "'status': 'reviewed'",
)


@dataclass(frozen=True)
class RouteCCaseLightRagConfig:
    """Explicit opt-in settings for Route C case light RAG."""

    enabled: bool = False
    provider_type: str = DEFAULT_LIGHT_RAG_PROVIDER_TYPE
    model: str | None = None
    endpoint: str | None = None
    timeout_seconds: int = 30
    apply_summaries: bool = True


@dataclass(frozen=True)
class RouteCCaseLightRagResult:
    """Reranked hits plus optional candidate-only summaries."""

    hits: tuple[RouteCCaseSearchHit, ...]
    summaries: Mapping[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def route_c_case_light_rag(
    query_text: str,
    hits: Sequence[RouteCCaseSearchHit],
    *,
    config: RouteCCaseLightRagConfig | Mapping[str, Any] | None = None,
    provider: BaseProvider | None = None,
) -> RouteCCaseLightRagResult:
    """Rerank lexical top-k hits with a controlled provider projection.

    The provider never receives source paths, raw records, blocked aggregate
    material, or candidates outside the lexical first-stage hit set.
    """
    resolved_config = resolve_light_rag_config(config)
    original_hits = tuple(hits)
    if not original_hits:
        return RouteCCaseLightRagResult(hits=original_hits)
    if not resolved_config.enabled:
        return RouteCCaseLightRagResult(hits=original_hits)

    request = build_light_rag_request(query_text, original_hits)
    try:
        response = (provider or _build_explicit_provider(resolved_config)).generate(request)
    except Exception as exc:  # pragma: no cover - exact provider failures vary.
        return RouteCCaseLightRagResult(
            hits=original_hits,
            warnings=(f"Route C light RAG provider unavailable; lexical ranking retained: {exc}",),
        )

    parsed = _parse_provider_payload(response.text)
    if not parsed:
        return RouteCCaseLightRagResult(
            hits=original_hits,
            warnings=("Route C light RAG provider returned no valid rerank JSON; lexical ranking retained.",),
        )

    reranked_hits = _rerank_hits(original_hits, parsed)
    summaries = _summaries(parsed, original_hits, resolved_config)
    return RouteCCaseLightRagResult(hits=tuple(reranked_hits), summaries=summaries)


def resolve_light_rag_config(config: RouteCCaseLightRagConfig | Mapping[str, Any] | None) -> RouteCCaseLightRagConfig:
    if isinstance(config, RouteCCaseLightRagConfig):
        return config
    raw = dict(config or {})
    provider_type = str(raw.get("provider_type") or raw.get("type") or DEFAULT_LIGHT_RAG_PROVIDER_TYPE).strip().lower()
    return RouteCCaseLightRagConfig(
        enabled=bool(raw.get("enabled", False)),
        provider_type=provider_type,
        model=str(raw["model"]) if raw.get("model") not in (None, "") else None,
        endpoint=str(raw["endpoint"]) if raw.get("endpoint") not in (None, "") else None,
        timeout_seconds=int(raw.get("timeout_seconds") or 30),
        apply_summaries=bool(raw.get("apply_summaries", True)),
    )


def build_light_rag_request(query_text: str, hits: Sequence[RouteCCaseSearchHit]) -> ProviderRequest:
    payload = {
        "task": "route_c_case_candidate_rerank",
        "rules": [
            "Only rank the provided lexical candidates.",
            "Do not add new RC, PA, evidence, source, or diagnosis facts.",
            "Keep every result candidate-only; do not claim confirmation.",
            "Return JSON only with ranking and optional summaries.",
        ],
        "output_contract": {
            "ranking": [{"rag_candidate_id": "string", "relevance_reason": "string"}],
            "summaries": {"RAG_candidate_id": "candidate-only relevance summary"},
        },
        "query": str(query_text or ""),
        "source_boundary": {
            "source_id": CASE_RETRIEVAL_SOURCE_ID,
            "first_stage": "lexical_bm25",
            "projection": "TASK-005/TASK-017 allowlisted candidate fields only",
        },
        "candidates": [
            _candidate_projection(hit, lexical_rank=index)
            for index, hit in enumerate(hits, start=1)
        ],
    }
    return ProviderRequest(
        prompt=json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        system_prompt=(
            "You are a constrained reranker for FaultDx Route C related-case "
            "candidates. Use only the provided JSON candidate projection. "
            "Return JSON only."
        ),
        metadata={
            "route": "case_retrieval",
            "source_id": CASE_RETRIEVAL_SOURCE_ID,
            "candidate_count": len(hits),
        },
    )


def _candidate_projection(hit: RouteCCaseSearchHit, *, lexical_rank: int) -> dict[str, Any]:
    record = hit.record.source_record
    projected: dict[str, Any] = {
        "lexical_rank": lexical_rank,
        "lexical_score": round(float(hit.score), 6),
    }
    for field_name in _ALLOWED_PROMPT_FIELDS:
        value = _safe_prompt_value(field_name, record.get(field_name))
        if value not in (None, "", [], {}):
            projected[field_name] = value
    projected["rag_candidate_id"] = hit.record.case_id
    return projected


def _safe_prompt_value(field_name: str, value: Any) -> Any:
    if field_name == "filter_basis":
        return {"reason": value.get("reason")} if isinstance(value, Mapping) and value.get("reason") else None
    if field_name == "evidence":
        if not isinstance(value, Mapping):
            return None
        return {
            key: value.get(key)
            for key in sorted(_ALLOWED_EVIDENCE_FIELDS)
            if value.get(key) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [_safe_scalar(item) for item in value if _safe_scalar(item) not in (None, "")]
    if isinstance(value, Mapping):
        return None
    return _safe_scalar(value)


def _safe_scalar(value: Any) -> str | int | float | bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool | int | float):
        return value
    return str(value)


def _build_explicit_provider(config: RouteCCaseLightRagConfig) -> BaseProvider:
    if config.provider_type == "stub":
        return StubProvider()
    if config.provider_type == "ollama":
        if not config.model or not config.endpoint:
            raise ValueError("Route C light RAG ollama provider requires explicit model and endpoint.")
        return OllamaProvider(
            model=config.model,
            endpoint=config.endpoint,
            timeout_seconds=config.timeout_seconds,
        )
    if config.provider_type == "company_api":
        if not config.model:
            raise ValueError("Route C light RAG company_api provider requires an explicit model.")
        return CompanyApiProvider(model=config.model)
    raise ValueError(f"Unsupported Route C light RAG provider type: {config.provider_type}")


def _parse_provider_payload(text: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, Mapping) else {}


def _rerank_hits(
    hits: Sequence[RouteCCaseSearchHit],
    payload: Mapping[str, Any],
) -> list[RouteCCaseSearchHit]:
    by_id = {hit.record.case_id: hit for hit in hits}
    ranking = payload.get("ranking", [])
    ordered: list[RouteCCaseSearchHit] = []
    seen: set[str] = set()
    if isinstance(ranking, list):
        for item in ranking:
            candidate_id = _candidate_id_from_ranking_item(item)
            if candidate_id and candidate_id in by_id and candidate_id not in seen:
                ordered.append(by_id[candidate_id])
                seen.add(candidate_id)
    ordered.extend(hit for hit in hits if hit.record.case_id not in seen)
    return ordered


def _candidate_id_from_ranking_item(item: Any) -> str | None:
    if isinstance(item, Mapping):
        value = item.get("rag_candidate_id")
    else:
        value = item
    candidate_id = str(value or "").strip()
    return candidate_id or None


def _summaries(
    payload: Mapping[str, Any],
    hits: Sequence[RouteCCaseSearchHit],
    config: RouteCCaseLightRagConfig,
) -> dict[str, str]:
    if not config.apply_summaries:
        return {}
    allowed_ids = {hit.record.case_id for hit in hits}
    raw = payload.get("summaries", {})
    if not isinstance(raw, Mapping):
        return {}
    summaries: dict[str, str] = {}
    for candidate_id, summary in raw.items():
        key = str(candidate_id)
        if key not in allowed_ids:
            continue
        sanitized = _sanitize_summary(summary)
        if sanitized:
            summaries[key] = sanitized
    return summaries


def _sanitize_summary(value: Any) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    lowered = text.lower()
    if any(term in lowered for term in _BANNED_SUMMARY_TERMS):
        return None
    if len(text) > DEFAULT_LIGHT_RAG_MAX_SUMMARY_CHARS:
        return f"{text[: DEFAULT_LIGHT_RAG_MAX_SUMMARY_CHARS - 3]}..."
    return text
