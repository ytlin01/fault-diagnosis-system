"""Deterministic bridge builder between diagnostic records and asset KG nodes.

This module intentionally does not write Neo4j edges. It generates a reviewable
bridge artifact first, so `TRIGGERS` edges can be loaded only after inspection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
import unicodedata
import yaml

from services.aggregation.structured_fp_join_semantic import OllamaEmbeddingProvider

_MATCH_SOURCE = "diagnostic_asset_bridge_v1"
_SEPARATOR_RE = re.compile(r"[\s_\-:：,，.。/\\()\[\]{}]+")
_PURE_DIGITS_RE = re.compile(r"^\d+$")


def stable_fault_id(standard_fp: str) -> str:
    digest = hashlib.sha1(standard_fp.encode("utf-8")).hexdigest()[:16]
    return f"fault:{digest}"


def normalize_for_match(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = _SEPARATOR_RE.sub("", text)
    return text


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_alias_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"module_aliases": {}, "component_aliases": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "module_aliases": data.get("module_aliases", {}) or {},
        "component_aliases": data.get("component_aliases", {}) or {},
    }


def load_embedding_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "enabled": False,
            "provider": {"type": "huggingface", "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"},
            "candidate_generation": {"top_k": 3, "min_similarity": 0.35},
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def build_asset_catalog(
    index_data: dict[str, Any],
    triples_data: dict[str, Any],
    alias_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    component_to_module: dict[str, str] = {}
    module_to_components: dict[str, list[str]] = {}

    for node in triples_data.get("nodes", []):
        node_id = node.get("id")
        if not node_id:
            continue
        nodes_by_id[node_id] = node

    for edge in triples_data.get("edges", []):
        if edge.get("type") != "HAS_COMPONENT":
            continue
        module_id = edge.get("from")
        component_id = edge.get("to")
        if not module_id or not component_id:
            continue
        component_to_module[component_id] = module_id
        module_to_components.setdefault(module_id, []).append(component_id)

    alias_entries = {
        "module": _build_alias_entries(index_data.get("module", {}), nodes_by_id, "module_id"),
        "component": _build_alias_entries(index_data.get("component", {}), nodes_by_id, "component_id"),
        "subcomponent": _build_alias_entries(index_data.get("subcomponent", {}), nodes_by_id, "subcomponent_id"),
    }

    _apply_manual_aliases(alias_entries["module"], alias_config.get("module_aliases", {}), nodes_by_id, "module_id")
    _apply_manual_aliases(alias_entries["component"], alias_config.get("component_aliases", {}), nodes_by_id, "component_id")
    for bucket in alias_entries.values():
        bucket.sort(key=lambda item: len(item["alias_normalized"]), reverse=True)

    return {
        "nodes_by_id": nodes_by_id,
        "component_to_module": component_to_module,
        "module_to_components": module_to_components,
        "aliases": alias_entries,
    }


def _apply_manual_aliases(
    entries: list[dict[str, Any]],
    alias_groups: dict[str, list[str]],
    nodes_by_id: dict[str, dict[str, Any]],
    id_field: str,
) -> None:
    existing = {(item["node_id"], item["alias_normalized"]) for item in entries}
    for node_id, aliases in alias_groups.items():
        node = nodes_by_id.get(node_id, {})
        props = node.get("properties", {}) if isinstance(node, dict) else {}
        display_name = props.get("name") or node_id
        resolved_id = props.get(id_field) or node_id
        for alias in aliases or []:
            normalized = normalize_for_match(alias)
            if not normalized:
                continue
            key = (resolved_id, normalized)
            if key in existing:
                continue
            existing.add(key)
            entries.append(
                {
                    "alias": alias,
                    "alias_normalized": normalized,
                    "node_id": resolved_id,
                    "display_name": display_name,
                }
            )


def _build_alias_entries(
    alias_map: dict[str, str],
    nodes_by_id: dict[str, dict[str, Any]],
    id_field: str,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for alias, node_id in alias_map.items():
        normalized = normalize_for_match(alias)
        if not normalized or _PURE_DIGITS_RE.fullmatch(normalized):
            continue
        node = nodes_by_id.get(node_id, {})
        props = node.get("properties", {}) if isinstance(node, dict) else {}
        entries.append(
            {
                "alias": alias,
                "alias_normalized": normalized,
                "node_id": props.get(id_field) or node_id,
                "display_name": props.get("name") or alias,
            }
        )
    entries.sort(key=lambda item: len(item["alias_normalized"]), reverse=True)
    return entries


def build_bridge_artifact(
    diagnostic_data: dict[str, Any],
    catalog: dict[str, Any],
    *,
    diagnostic_input: str,
    asset_index_input: str,
    triples_input: str,
    alias_config_input: str | None = None,
    embedding_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = [
        build_bridge_record(record, catalog)
        for record in diagnostic_data.get("records", [])
    ]
    if embedding_config and embedding_config.get("enabled"):
        _apply_embedding_candidates(records, catalog, embedding_config)
    summary = _summarize(records)
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": _MATCH_SOURCE,
            "diagnostic_input": diagnostic_input,
            "asset_index_input": asset_index_input,
            "triples_input": triples_input,
            "alias_config_input": alias_config_input,
            "method": {
                "stage": "deterministic_review_first",
                "embedding_enabled": bool(embedding_config and embedding_config.get("enabled")),
                "rules": [
                    "component_alias_contains",
                    "module_alias_contains",
                    "manual_alias_config",
                    "module_context_only_no_auto_component_promotion",
                    "embedding_candidate_retrieval_for_unresolved_only",
                ],
            },
        },
        "summary": summary,
        "records": records,
    }


def build_bridge_record(record: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    standard_fp = str(record.get("standard_fp") or "")
    field_fp_variants = [str(item) for item in (record.get("field_fp_variants") or []) if item]
    texts = [{"field": "standard_fp", "text": standard_fp}] + [
        {"field": "field_fp_variant", "text": item} for item in field_fp_variants
    ]

    text_hits = [_match_text(entry["field"], entry["text"], catalog) for entry in texts if entry["text"]]
    component_hits = _dedupe_hits(text_hits, "component_hits")
    module_hits = _dedupe_hits(text_hits, "module_hits")

    status = "unmapped"
    rule = "no_asset_signal"
    component_id: str | None = None
    module_id: str | None = None

    best_component = _pick_best_hit(component_hits)
    best_module = _pick_best_hit(module_hits)

    if len(component_hits) == 1:
        status = "mapped"
        rule = "component_alias_contains"
        component_id = component_hits[0]["node_id"]
        module_id = catalog["component_to_module"].get(component_id)
    elif best_component is not None:
        status = "mapped"
        rule = "weighted_component_alias_contains"
        component_id = best_component["node_id"]
        module_id = catalog["component_to_module"].get(component_id)
    elif len(component_hits) > 1:
        status = "ambiguous"
        rule = "multiple_component_candidates"
    elif len(module_hits) == 1:
        status = "module_only"
        rule = "module_alias_contains_without_unique_component"
        module_id = module_hits[0]["node_id"]
    elif best_module is not None:
        status = "module_only"
        rule = "weighted_module_alias_contains_without_unique_component"
        module_id = best_module["node_id"]
    elif len(module_hits) > 1:
        status = "ambiguous"
        rule = "multiple_module_candidates"

    candidate_component_ids = sorted({hit["node_id"] for hit in component_hits})
    candidate_module_ids = sorted({hit["node_id"] for hit in module_hits})

    return {
        "mapping_id": record.get("mapping_id"),
        "fault_id": stable_fault_id(standard_fp),
        "EC": record.get("EC"),
        "standard_fp": standard_fp,
        "field_fp_variants": field_fp_variants,
        "mapping_status": status,
        "component_id": component_id,
        "module_id": module_id,
        "candidate_component_ids": candidate_component_ids,
        "candidate_module_ids": candidate_module_ids,
        "evidence": {
            "rule": rule,
            "texts": text_hits,
            "component_hits": component_hits,
            "module_hits": module_hits,
            "module_component_count": len(catalog["module_to_components"].get(module_id or "", [])) if module_id else 0,
            "embedding_candidates": [],
        },
        "source": _MATCH_SOURCE,
    }


def _match_text(field: str, text: str, catalog: dict[str, Any]) -> dict[str, Any]:
    normalized_text = normalize_for_match(text)
    return {
        "field": field,
        "text": text,
        "normalized_text": normalized_text,
        "component_hits": _find_hits(normalized_text, catalog["aliases"]["component"]),
        "module_hits": _find_hits(normalized_text, catalog["aliases"]["module"]),
    }


def _find_hits(normalized_text: str, alias_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in alias_entries:
        alias_normalized = entry["alias_normalized"]
        if alias_normalized not in normalized_text:
            continue
        key = (entry["node_id"], entry["alias"])
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            {
                "node_id": entry["node_id"],
                "matched_alias": entry["alias"],
                "display_name": entry["display_name"],
            }
        )
    return hits


def _dedupe_hits(text_hits: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for text_hit in text_hits:
        for hit in text_hit.get(key, []):
            item = merged.setdefault(
                hit["node_id"],
                {
                    "node_id": hit["node_id"],
                    "display_name": hit["display_name"],
                    "matched_aliases": [],
                    "matched_fields": [],
                    "max_alias_length": 0,
                },
            )
            if hit["matched_alias"] not in item["matched_aliases"]:
                item["matched_aliases"].append(hit["matched_alias"])
            if text_hit["field"] not in item["matched_fields"]:
                item["matched_fields"].append(text_hit["field"])
            item["max_alias_length"] = max(item["max_alias_length"], len(hit["matched_alias"]))
    return sorted(merged.values(), key=lambda item: (item["display_name"], item["node_id"]))


def _pick_best_hit(hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(hits) <= 1:
        return None
    ranked = sorted(
        hits,
        key=lambda item: (
            item.get("max_alias_length", 0),
            len(item.get("matched_aliases", [])),
            len(item.get("matched_fields", [])),
        ),
        reverse=True,
    )
    best = ranked[0]
    second = ranked[1]
    best_score = (
        best.get("max_alias_length", 0),
        len(best.get("matched_aliases", [])),
        len(best.get("matched_fields", [])),
    )
    second_score = (
        second.get("max_alias_length", 0),
        len(second.get("matched_aliases", [])),
        len(second.get("matched_fields", [])),
    )
    return best if best_score > second_score else None


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "mapped": 0,
        "module_only": 0,
        "ambiguous": 0,
        "unmapped": 0,
        "embedding_candidate": 0,
    }
    for record in records:
        counts[record["mapping_status"]] = counts.get(record["mapping_status"], 0) + 1
    return {
        "record_count": len(records),
        "status_counts": counts,
    }


class SentenceTransformerEmbeddingProvider:
    """Small sentence-transformers embedding provider with on-disk cache."""

    def __init__(
        self,
        *,
        model: str,
        cache_path: Path | None = None,
        hf_home: Path | None = None,
    ) -> None:
        if hf_home:
            import os

            os.environ.setdefault("HF_HOME", str(hf_home))
            os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "hub"))
        from sentence_transformers import SentenceTransformer

        self.model_name = model
        self.model = SentenceTransformer(model, device="cpu")
        self.cache_path = cache_path
        self.cache: dict[str, list[float]] = {}
        if cache_path and cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.cache = payload.get("embeddings") or {}

    def save_cache(self) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "sentence_transformer_embedding_cache_v1",
            "model": self.model_name,
            "embedding_count": len(self.cache),
            "embeddings": self.cache,
        }
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def embed_texts(self, texts: list[str]) -> dict[str, list[float]]:
        unique_texts = [text for text in dict.fromkeys(texts) if text]
        missing = [text for text in unique_texts if self._cache_key(text) not in self.cache]
        if missing:
            vectors = self.model.encode(missing, normalize_embeddings=True)
            for text, vector in zip(missing, vectors):
                self.cache[self._cache_key(text)] = [float(v) for v in vector]
            self.save_cache()
        return {text: self.cache[self._cache_key(text)] for text in unique_texts}

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self.model_name}\n{text}".encode("utf-8")).hexdigest()
        return digest


def _embedding_provider_from_config(config: dict[str, Any]) -> Any:
    provider = (config.get("provider") or {}).get("type") or "huggingface"
    provider_cfg = config.get("provider") or {}
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            host=str(provider_cfg.get("host") or "http://localhost:11434"),
            model=str(provider_cfg.get("model") or "nomic-embed-text:latest"),
            batch_size=int(provider_cfg.get("batch_size") or 64),
            timeout_sec=int(provider_cfg.get("timeout_sec") or 120),
            cache_path=Path(str(provider_cfg.get("cache_path"))) if provider_cfg.get("cache_path") else None,
        )
    if provider == "huggingface":
        return SentenceTransformerEmbeddingProvider(
            model=str(provider_cfg.get("model") or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            cache_path=Path(str(provider_cfg.get("cache_path"))) if provider_cfg.get("cache_path") else None,
            hf_home=Path(str(provider_cfg.get("hf_home"))) if provider_cfg.get("hf_home") else None,
        )
    raise ValueError(f"Unsupported embedding provider: {provider}")


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right)))


def _apply_embedding_candidates(records: list[dict[str, Any]], catalog: dict[str, Any], config: dict[str, Any]) -> None:
    unresolved = [record for record in records if record["mapping_status"] == "unmapped"]
    if not unresolved:
        return
    provider = _embedding_provider_from_config(config)
    top_k = int((config.get("candidate_generation") or {}).get("top_k") or 3)
    min_similarity = float((config.get("candidate_generation") or {}).get("min_similarity") or 0.35)

    asset_texts: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for bucket_name in ("component", "module"):
        for entry in catalog["aliases"][bucket_name]:
            key = (entry["node_id"], entry["alias"])
            if key in seen:
                continue
            seen.add(key)
            asset_texts.append((bucket_name, entry["node_id"], entry["alias"], entry["display_name"]))

    query_texts: list[str] = []
    for record in unresolved:
        query_texts.append(str(record["standard_fp"] or ""))
        for variant in record.get("field_fp_variants") or []:
            query_texts.append(str(variant))

    query_embeddings = provider.embed_texts(query_texts)
    asset_embeddings = provider.embed_texts([item[2] for item in asset_texts])

    for record in unresolved:
        candidates: list[dict[str, Any]] = []
        for text in [str(record["standard_fp"] or "")] + [str(v) for v in (record.get("field_fp_variants") or [])]:
            query_vec = query_embeddings.get(text, [])
            if not query_vec:
                continue
            for bucket_name, node_id, alias, display_name in asset_texts:
                sim = _cosine(query_vec, asset_embeddings.get(alias, []))
                if sim < min_similarity:
                    continue
                candidates.append(
                    {
                        "bucket": bucket_name,
                        "node_id": node_id,
                        "alias": alias,
                        "display_name": display_name,
                        "query_text": text,
                        "similarity": round(sim, 6),
                    }
                )
        candidates.sort(key=lambda item: (-item["similarity"], item["bucket"], item["node_id"]))
        deduped: list[dict[str, Any]] = []
        seen_nodes: set[tuple[str, str]] = set()
        for item in candidates:
            key = (item["bucket"], item["node_id"])
            if key in seen_nodes:
                continue
            seen_nodes.add(key)
            deduped.append(item)
            if len(deduped) >= top_k:
                break
        record["evidence"]["embedding_candidates"] = deduped
        if deduped:
            record["mapping_status"] = "embedding_candidate"
            record["evidence"]["rule"] = "embedding_candidate_retrieval"
