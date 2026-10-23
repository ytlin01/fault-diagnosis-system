"""Route B document evidence executor for serving-safe unstructured sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from services.retrieval.route_b_index import RouteBDocumentChunk, search_route_b_documents

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is part of base requirements.
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_CONFIG_PATH = REPO_ROOT / "configs" / "base.yaml"
ROUTE_B_SOURCE_ID = "data/serving_unstructured_vlm"
DEFAULT_TOP_K = 3
DEFAULT_MAX_CHUNK_CHARS = 800
_BLOCKED_SOURCE_MARKERS = (
    "data/raw",
    "data\\raw",
    "data/processed/unstructured",
    "data\\processed\\unstructured",
    "data/processed/unstructured_vlm",
    "data\\processed\\unstructured_vlm",
    "data/processed/unstructured_masked_vlm",
    "data\\processed\\unstructured_masked_vlm",
    "response_text",
    "raw_response",
)


def execute_route_b_document(
    query_text: str,
    *,
    allowed_sources: Iterable[str],
    source_dir: str | Path = ROUTE_B_SOURCE_ID,
    top_k: int | None = None,
) -> dict[str, Any]:
    settings = _route_b_settings()
    source_id = str(settings.get("source_id", ROUTE_B_SOURCE_ID))
    resolved_top_k = top_k if top_k is not None else int(settings.get("top_k", DEFAULT_TOP_K))
    max_chunk_chars = int(settings.get("max_chunk_chars", DEFAULT_MAX_CHUNK_CHARS))

    allowed = set(str(source) for source in allowed_sources)
    if source_id not in allowed and "serving_unstructured_vlm" not in allowed:
        return _empty_output("Route B did not receive the serving-safe document source.")

    source_path = Path(source_dir)
    if _is_blocked_source_path(source_path):
        return _empty_output(f"Route B blocked a non-serving-safe document source: {source_path}")
    if not source_path.exists() or not source_path.is_dir():
        return _empty_output(f"Route B serving source is unavailable: {source_path}")

    warnings: list[str] = []
    hits = search_route_b_documents(
        query_text,
        source_dir=source_path,
        source_id=source_id,
        top_k=max(0, resolved_top_k),
        warnings=warnings,
        max_chunk_chars=max_chunk_chars,
    )
    items = [_document_result(rank=0, chunk=hit.chunk) for hit in hits]
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank

    if not items and not warnings:
        warnings.append("No matching serving-safe document evidence was found.")

    return {
        "items": items,
        "used_sources": [_knowledge_source(source_id)],
        "warnings": warnings,
    }


def _document_result(
    *,
    rank: int,
    chunk: RouteBDocumentChunk,
) -> dict[str, Any]:
    summary = chunk.summary
    return {
        "rank": rank,
        "title": f"文档证据（{chunk.block_type}）",
        "result_type": "document_evidence",
        "status": "evidence_only",
        "confidence": "medium",
        "description": summary,
        "evidence": [
            {
                "evidence_type": chunk.evidence_type,
                "source_type": chunk.source_type,
                "source_name": chunk.source_name,
                "source_id": chunk.source_id,
                "anchor": chunk.anchor,
                "reviewed": chunk.reviewed,
                "serving_safe": chunk.serving_safe,
                "summary": summary,
            }
        ],
    }


def _is_blocked_source_path(source_path: Path) -> bool:
    normalized = str(source_path).replace("\\", "/").lower()
    return any(marker.replace("\\", "/") in normalized for marker in _BLOCKED_SOURCE_MARKERS)


def _route_b_settings() -> dict[str, Any]:
    settings: dict[str, Any] = {
        "source_id": ROUTE_B_SOURCE_ID,
        "top_k": DEFAULT_TOP_K,
        "max_chunk_chars": DEFAULT_MAX_CHUNK_CHARS,
    }
    if yaml is not None and BASE_CONFIG_PATH.exists():
        with BASE_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        route_b = payload.get("retrieval", {}).get("route_b", {})
        if isinstance(route_b, dict):
            settings.update({key: value for key, value in route_b.items() if value is not None})

    if os.environ.get("FAULTDX_ROUTE_B_SOURCE_ID"):
        settings["source_id"] = os.environ["FAULTDX_ROUTE_B_SOURCE_ID"]
    if os.environ.get("FAULTDX_ROUTE_B_TOP_K"):
        settings["top_k"] = _env_int("FAULTDX_ROUTE_B_TOP_K", int(settings["top_k"]))
    if os.environ.get("FAULTDX_ROUTE_B_MAX_CHUNK_CHARS"):
        settings["max_chunk_chars"] = _env_int(
            "FAULTDX_ROUTE_B_MAX_CHUNK_CHARS",
            int(settings["max_chunk_chars"]),
        )
    return settings


def _env_int(name: str, fallback: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, TypeError, ValueError):
        return fallback


def _knowledge_source(source_id: str) -> dict[str, Any]:
    return {
        "source_type": "serving_document",
        "source_id": source_id,
        "snapshot_id": None,
        "updated_at": None,
    }


def _empty_output(warning: str) -> dict[str, Any]:
    return {"items": [], "used_sources": [], "warnings": [warning]}
