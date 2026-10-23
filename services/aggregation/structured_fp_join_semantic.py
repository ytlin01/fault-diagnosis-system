"""Semantic FP join candidate aggregation for TASK-005 v1.

This module intentionally does not replace the deterministic v0 aggregate.  It
uses local embedding similarity to generate high-recall review candidates while
keeping all semantic matches review-only until a human confirms them.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any

from services.aggregation.structured_fp_join import (
    extract_fp_features,
    load_inputs,
    load_json,
    load_rules,
    make_source_ref,
    normalize_fp_with_rules,
    stable_id,
    summarize_downtime,
    write_json,
    _feature_overlap,
    _unique_non_empty,
)

SCHEMA_VERSION = "structured_fp_join_v1_semantic"
REVIEW_SCHEMA_VERSION = "structured_fp_join_v1_semantic_review"
REVIEW_DECISIONS_SCHEMA_VERSION = "structured_fp_join_v1_semantic_review_decisions"

FIELD_FP = "\u7570\u5e38\u63cf\u6558"
CAUSE = "\u539f\u56e0"
ACTION = "\u7dad\u4fee\u52d5\u4f5c"


def default_config() -> dict[str, Any]:
    return {
        "version": 1,
        "provider": {
            "type": "ollama",
            "host": "http://localhost:11434",
            "model": "nomic-embed-text:latest",
            "batch_size": 64,
            "timeout_sec": 120,
        },
        "candidate_generation": {
            "top_k_per_downtime_fp": 5,
            "min_embedding_similarity": 0.50,
            "min_final_score": 0.52,
            "weights": {
                "embedding_similarity": 0.86,
                "feature_similarity": 0.14,
            },
            "require_any_feature_overlap": False,
            "feature_bonus_per_shared_group": 0.015,
            "max_candidate_records": 2000,
        },
        "routing": {
            "semantic_candidates_are_review_only": True,
        },
    }


def load_semantic_config(path: Path | None) -> dict[str, Any]:
    config = default_config()
    if path is None or not path.exists():
        return config
    loaded = load_rules(path)
    return _deep_merge(config, loaded)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_review_decisions_template() -> dict[str, Any]:
    return {
        "schema_version": REVIEW_DECISIONS_SCHEMA_VERSION,
        "metadata": {
            "purpose": "Human review decisions for TASK-005 v1 semantic FP candidates.",
            "allowed_decisions": ["candidate_only", "confirmed", "rejected"],
            "note": "Only confirmed decisions should later be promoted into governed mappings.",
        },
        "decisions": [],
        "examples": [
            {
                "decision_id": "example-confirm-semantic-candidate",
                "decision": "confirmed",
                "EC": "M07LOM1-01-03",
                "field_fp": "\u4e0a\u6599\u4ed3Z\u8f74\u5f02\u5e38",
                "field_fp_normalized": "\u4e0a\u6599\u4ed3z\u8f74\u5f02\u5e38",
                "reviewer": "",
                "reviewed_at": "",
                "note": "Example only. Move to decisions[] after human review if correct.",
            }
        ],
    }


def load_review_decisions(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return build_review_decisions_template()
    return load_json(path)


def _decision_index(review_decisions: dict[str, Any] | None, rules: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for decision in (review_decisions or {}).get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        status = str(decision.get("decision") or "").strip().lower()
        if status not in {"confirmed", "candidate_only", "rejected"}:
            continue
        ec = str(decision.get("EC") or "").strip()
        fp_norm = decision.get("field_fp_normalized") or normalize_fp_with_rules(decision.get("field_fp"), rules)
        fp_norm = normalize_fp_with_rules(fp_norm, rules)
        if ec and fp_norm:
            index[(ec, fp_norm)] = decision
    return index


class OllamaEmbeddingProvider:
    """Local Ollama embedding client with an on-disk cache.

    The caller passes processed/canonical FP strings, not raw logs. Cache
    files are generated artifacts and should be regenerated when the model
    or semantic config changes.
    """
    def __init__(
        self,
        *,
        host: str,
        model: str,
        batch_size: int = 64,
        timeout_sec: int = 120,
        cache_path: Path | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.batch_size = batch_size
        self.timeout_sec = timeout_sec
        self.cache_path = cache_path
        self.cache: dict[str, list[float]] = {}
        if cache_path and cache_path.exists():
            with open(cache_path, "r", encoding="utf-8-sig") as f:
                payload = json.load(f)
            self.cache = payload.get("embeddings") or {}

    def save_cache(self) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "ollama_embedding_cache_v1",
            "model": self.model,
            "embedding_count": len(self.cache),
            "embeddings": self.cache,
        }
        write_json(self.cache_path, payload, pretty=False)

    def embed_texts(self, texts: list[str]) -> dict[str, list[float]]:
        unique_texts = [text for text in dict.fromkeys(texts) if text]
        missing = [text for text in unique_texts if self._cache_key(text) not in self.cache]
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start:start + self.batch_size]
            embeddings = self._embed_batch(batch)
            for text, vector in zip(batch, embeddings):
                self.cache[self._cache_key(text)] = _normalize_vector(vector)
        self.save_cache()
        return {text: self.cache[self._cache_key(text)] for text in unique_texts}

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self.model}\n{text}".encode("utf-8")).hexdigest()
        return digest

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama embedding request failed at {self.host}. Start Ollama with OLLAMA_MODELS set correctly."
            ) from exc
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError(f"Unexpected Ollama embedding response shape: {payload.keys()}")
        return embeddings


def _normalize_vector(vector: list[Any]) -> list[float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        return values
    return [value / norm for value in values]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _feature_similarity(left: dict[str, list[str]], right: dict[str, list[str]]) -> float:
    groups = ("modules", "axes", "components", "fault_modes")
    left_values = sum(len(left.get(group, [])) for group in groups)
    right_values = sum(len(right.get(group, [])) for group in groups)
    denominator = min(left_values, right_values)
    if denominator <= 0:
        return 0.0
    overlap = _feature_overlap(left, right)
    numerator = sum(len(values) for values in overlap.values())
    return min(1.0, numerator / denominator)


def _decision_payload(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": decision.get("decision_id"),
        "decision": decision.get("decision"),
        "reviewer": decision.get("reviewer"),
        "reviewed_at": decision.get("reviewed_at"),
        "note": decision.get("note"),
    }


def _group_downtime_records(downtime_records: list[dict[str, Any]], rules: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(downtime_records):
        normalized = normalize_fp_with_rules(record.get(FIELD_FP), rules)
        if not normalized:
            continue
        enriched = dict(record)
        enriched["_source_ref"] = make_source_ref("y25_downtime", record, index).as_dict()
        enriched["_normalized_fp"] = normalized
        groups[normalized].append(enriched)
    return dict(groups)


def _ec_index(error_code_records: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    indexed = []
    for index, record in enumerate(error_code_records):
        fp = record.get("Description")
        normalized = normalize_fp_with_rules(fp, rules)
        if not normalized:
            continue
        indexed.append({
            "record": record,
            "index": index,
            "EC": record.get("Error code"),
            "standard_fp": fp,
            "normalized_fp": normalized,
            "features": extract_fp_features(fp, rules),
            "source_ref": make_source_ref("error_codes_standardized", record, index).as_dict(),
        })
    return indexed


def _route_for_review_candidate(review_status: str) -> dict[str, Any]:
    if review_status == "confirmed":
        return {
            "kg_diagnosis_eligible": True,
            "chain_status": "complete_confirmed_semantic",
            "route_target": "text2cypher_diagnosis",
            "route_reason": "Human-confirmed semantic candidate with complete EC/FP/RC/PA evidence.",
        }
    return {
        "kg_diagnosis_eligible": False,
        "chain_status": "semantic_candidate_review_required",
        "route_target": "fp_review_governance",
        "route_reason": "Embedding-based FP link requires human review before KG/text2cypher diagnosis.",
    }


def build_semantic_fp_join(
    error_code_records: list[dict[str, Any]],
    downtime_records: list[dict[str, Any]],
    *,
    rules: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    embedding_provider: Any,
    review_decisions: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build review-only semantic FP candidates from canonical inputs.

    Embedding similarity broadens recall, but raw scores do not create KG
    diagnosis facts. Only explicit review decisions may change routing from
    fp_review_governance to text2cypher_diagnosis.
    """
    rules = rules or {}
    config = config or default_config()
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    candidate_config = config.get("candidate_generation") or {}
    top_k = int(candidate_config.get("top_k_per_downtime_fp", 5))
    min_embedding = float(candidate_config.get("min_embedding_similarity", 0.50))
    min_final = float(candidate_config.get("min_final_score", 0.52))
    weights = candidate_config.get("weights") or {}
    embedding_weight = float(weights.get("embedding_similarity", 0.86))
    feature_weight = float(weights.get("feature_similarity", 0.14))
    require_feature_overlap = bool(candidate_config.get("require_any_feature_overlap", False))
    feature_bonus = float(candidate_config.get("feature_bonus_per_shared_group", 0.015))
    max_records = int(candidate_config.get("max_candidate_records", 2000))

    ec_records = _ec_index(error_code_records, rules)
    downtime_groups = _group_downtime_records(downtime_records, rules)
    dt_items = []
    for normalized_fp, group in sorted(downtime_groups.items()):
        field_fps = _unique_non_empty([record.get(FIELD_FP) for record in group])
        display_fp = field_fps[0] if field_fps else normalized_fp
        dt_items.append({
            "normalized_fp": normalized_fp,
            "display_fp": display_fp,
            "field_fp_variants": field_fps,
            "features": extract_fp_features(display_fp, rules),
            "records": group,
        })

    texts = [ec["standard_fp"] for ec in ec_records if ec.get("standard_fp")]
    texts.extend(item["display_fp"] for item in dt_items if item.get("display_fp"))
    embeddings = embedding_provider.embed_texts(texts)
    decision_lookup = _decision_index(review_decisions, rules)

    records: list[dict[str, Any]] = []
    downtime_with_candidates: set[str] = set()
    ec_with_candidates: set[str] = set()
    for item in dt_items:
        dt_vector = embeddings.get(item["display_fp"], [])
        scored: list[dict[str, Any]] = []
        for ec in ec_records:
            ec_vector = embeddings.get(ec["standard_fp"], [])
            embedding_similarity = _cosine(ec_vector, dt_vector)
            if embedding_similarity < min_embedding:
                continue
            overlap = _feature_overlap(ec["features"], item["features"])
            if require_feature_overlap and not overlap:
                continue
            feature_similarity = _feature_similarity(ec["features"], item["features"])
            final_score = (embedding_similarity * embedding_weight) + (feature_similarity * feature_weight)
            final_score += feature_bonus * len(overlap)
            if final_score < min_final:
                continue
            scored.append({
                "ec": ec,
                "embedding_similarity": embedding_similarity,
                "feature_similarity": feature_similarity,
                "final_score": final_score,
                "shared_features": overlap,
            })
        scored.sort(key=lambda value: (-value["final_score"], str(value["ec"].get("EC"))))
        for rank, candidate in enumerate(scored[:top_k], start=1):
            ec = candidate["ec"]
            possible_causes = _unique_non_empty([record.get(CAUSE) for record in item["records"]])
            repair_actions = _unique_non_empty([record.get(ACTION) for record in item["records"]])
            decision = decision_lookup.get((str(ec.get("EC")), item["normalized_fp"]))
            review_status = str((decision or {}).get("decision") or "needs_review")
            route = _route_for_review_candidate(review_status)
            record = {
                "mapping_id": stable_id(ec.get("EC"), ec.get("normalized_fp"), item["normalized_fp"], "semantic", prefix="SEM"),
                "EC": ec.get("EC"),
                "FP": ec.get("standard_fp"),
                "standard_fp": ec.get("standard_fp"),
                "standard_fp_source": "error_codes_standardized.Description",
                "field_fp_variants": item["field_fp_variants"],
                "field_fp_source": "y25_downtime.\u7570\u5e38\u63cf\u6558",
                "RC": possible_causes,
                "PA": repair_actions,
                "match_type": "human_confirmed_semantic_candidate" if review_status == "confirmed" else "semantic_embedding_candidate",
                "review_status": review_status,
                "kg_diagnosis_eligible": route["kg_diagnosis_eligible"],
                "chain_status": route["chain_status"],
                "route_target": route["route_target"],
                "route_reason": route["route_reason"],
                "semantic_rank": rank,
                "semantic_score": round(candidate["final_score"], 6),
                "embedding_similarity": round(candidate["embedding_similarity"], 6),
                "feature_similarity": round(candidate["feature_similarity"], 6),
                "match_basis": {
                    "method": "local_ollama_embedding",
                    "embedding_model": (config.get("provider") or {}).get("model"),
                    "embedding_provider": (config.get("provider") or {}).get("type"),
                    "field_fp_normalized": item["normalized_fp"],
                    "standard_fp_normalized": ec.get("normalized_fp"),
                    "shared_features": candidate["shared_features"],
                    "score_breakdown": {
                        "embedding_similarity": round(candidate["embedding_similarity"], 6),
                        "feature_similarity": round(candidate["feature_similarity"], 6),
                        "final_score": round(candidate["final_score"], 6),
                    },
                },
                "review_decision": _decision_payload(decision) if decision else None,
                "source_refs": {
                    "error_code": [ec["source_ref"]],
                    "downtime": [record["_source_ref"] for record in item["records"]],
                },
                "evidence": summarize_downtime(item["records"]),
            }
            records.append(record)
            downtime_with_candidates.add(item["normalized_fp"])
            ec_with_candidates.add(str(ec.get("EC")))
            if len(records) >= max_records:
                break
        if len(records) >= max_records:
            break

    unmatched_downtime = [
        {
            "FP": item["field_fp_variants"],
            "field_fp_variants": item["field_fp_variants"],
            "normalized_fp": item["normalized_fp"],
            "reason": "no_semantic_candidate_above_threshold",
            "route_target": "case_retrieval",
            "kg_diagnosis_eligible": False,
            "source_refs": [record["_source_ref"] for record in item["records"]],
            "evidence": summarize_downtime(item["records"]),
        }
        for item in dt_items
        if item["normalized_fp"] not in downtime_with_candidates
    ]
    unmatched_ec = [
        {
            "EC": ec.get("EC"),
            "FP": ec.get("standard_fp"),
            "normalized_fp": ec.get("normalized_fp"),
            "reason": "no_semantic_candidate_above_threshold",
            "route_target": "structured_catalog",
            "kg_diagnosis_eligible": False,
            "source_ref": ec["source_ref"],
        }
        for ec in ec_records
        if str(ec.get("EC")) not in ec_with_candidates
    ]

    route_counts = Counter(record["route_target"] for record in records)
    review_counts = Counter(record["review_status"] for record in records)
    payload = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "purpose": "High-recall semantic FP candidate aggregate. Does not replace v0 baseline.",
            "input_sources": {
                "error_codes_standardized": {"record_count": len(error_code_records)},
                "y25_downtime": {"record_count": len(downtime_records)},
            },
            "provider": config.get("provider"),
            "candidate_generation": candidate_config,
            "summary": {
                "candidate_records": len(records),
                "kg_diagnosis_eligible_records": sum(1 for record in records if record.get("kg_diagnosis_eligible")),
                "downtime_fp_groups_with_candidates": len(downtime_with_candidates),
                "total_downtime_fp_groups": len(dt_items),
                "error_codes_with_candidates": len(ec_with_candidates),
                "total_error_codes": len(ec_records),
                "unmatched_downtime_fp_groups": len(unmatched_downtime),
                "unmatched_error_codes": len(unmatched_ec),
                "route_target_counts": dict(sorted(route_counts.items())),
                "review_status_counts": dict(sorted(review_counts.items())),
            },
        },
        "records": records,
        "unmatched": {
            "error_code_fps": unmatched_ec,
            "downtime_fps": unmatched_downtime,
        },
    }
    return payload


def build_summary(payload: dict[str, Any], *, sample_size: int = 10) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    return {
        "schema_version": metadata.get("schema_version"),
        "generated_at": metadata.get("generated_at"),
        "provider": metadata.get("provider"),
        "candidate_generation": metadata.get("candidate_generation"),
        "summary": metadata.get("summary"),
        "sample_records": payload.get("records", [])[:sample_size],
        "sample_unmatched_error_code_fps": (payload.get("unmatched") or {}).get("error_code_fps", [])[:sample_size],
        "sample_unmatched_downtime_fps": (payload.get("unmatched") or {}).get("downtime_fps", [])[:sample_size],
    }


def build_standard_fp_review(payload: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for record in payload.get("records") or []:
        key = f"{record.get('EC')}||{record.get('standard_fp')}"
        group = groups.setdefault(key, {
            "EC": record.get("EC"),
            "standard_fp": record.get("standard_fp"),
            "standard_fp_source": record.get("standard_fp_source"),
            "summary": {
                "candidate_field_fp_count": 0,
                "candidate_record_count": 0,
                "confirmed_count": 0,
                "candidate_only_count": 0,
                "rejected_count": 0,
                "needs_review_count": 0,
                "max_semantic_score": 0.0,
                "total_evidence_count": 0,
                "total_dt_mins": 0.0,
            },
            "candidate_field_fps": [],
        })
        evidence = record.get("evidence") or {}
        review_status = str(record.get("review_status") or "needs_review")
        candidate = {
            "field_fp_variants": record.get("field_fp_variants"),
            "field_fp_normalized": (record.get("match_basis") or {}).get("field_fp_normalized"),
            "semantic_score": record.get("semantic_score"),
            "embedding_similarity": record.get("embedding_similarity"),
            "feature_similarity": record.get("feature_similarity"),
            "semantic_rank": record.get("semantic_rank"),
            "review_status": review_status,
            "route_target": record.get("route_target"),
            "shared_features": (record.get("match_basis") or {}).get("shared_features"),
            "RC": record.get("RC"),
            "PA": record.get("PA"),
            "evidence": evidence,
            "source_refs": record.get("source_refs"),
        }
        group["candidate_field_fps"].append(candidate)
        summary = group["summary"]
        summary["candidate_record_count"] += 1
        summary[f"{review_status}_count"] = int(summary.get(f"{review_status}_count") or 0) + 1
        summary["max_semantic_score"] = max(float(summary["max_semantic_score"]), float(record.get("semantic_score") or 0.0))
        summary["total_evidence_count"] += int(evidence.get("count") or 0)
        summary["total_dt_mins"] += float(evidence.get("total_dt_mins") or 0.0)

    standard_fp_groups = list(groups.values())
    for group in standard_fp_groups:
        group["candidate_field_fps"].sort(key=lambda item: (-float(item.get("semantic_score") or 0), str(item.get("field_fp_normalized"))))
        unique_field_fps = {candidate.get("field_fp_normalized") for candidate in group["candidate_field_fps"] if candidate.get("field_fp_normalized")}
        group["summary"]["candidate_field_fp_count"] = len(unique_field_fps)
        group["summary"]["max_semantic_score"] = round(float(group["summary"]["max_semantic_score"]), 6)
        group["summary"]["total_dt_mins"] = round(float(group["summary"]["total_dt_mins"]), 3)
    standard_fp_groups.sort(
        key=lambda item: (
            -int(item["summary"].get("candidate_field_fp_count") or 0),
            -float(item["summary"].get("max_semantic_score") or 0),
            str(item.get("EC")),
        )
    )
    return {
        "metadata": {
            "schema_version": "structured_fp_join_v1_semantic_standard_fp_review",
            "generated_at": (payload.get("metadata") or {}).get("generated_at"),
            "summary": {
                "standard_fp_count": len(standard_fp_groups),
                "candidate_records": len(payload.get("records") or []),
                "standard_fps_with_multiple_field_fps": sum(
                    1 for group in standard_fp_groups if int(group["summary"].get("candidate_field_fp_count") or 0) > 1
                ),
                "confirmed_records": sum(1 for record in payload.get("records") or [] if record.get("review_status") == "confirmed"),
            },
        },
        "standard_fp_groups": standard_fp_groups,
    }


def build_standard_fp_review_summary(report: dict[str, Any], *, sample_size: int = 30, candidate_sample_size: int = 8) -> dict[str, Any]:
    metadata = report.get("metadata") or {}
    groups = report.get("standard_fp_groups") or []
    sample_groups = []
    for group in groups[:sample_size]:
        sample_groups.append({
            "EC": group.get("EC"),
            "standard_fp": group.get("standard_fp"),
            "summary": group.get("summary"),
            "sample_field_fp_candidates": [
                {
                    "field_fp_variants": candidate.get("field_fp_variants"),
                    "field_fp_normalized": candidate.get("field_fp_normalized"),
                    "semantic_score": candidate.get("semantic_score"),
                    "embedding_similarity": candidate.get("embedding_similarity"),
                    "feature_similarity": candidate.get("feature_similarity"),
                    "review_status": candidate.get("review_status"),
                    "shared_features": candidate.get("shared_features"),
                    "evidence": candidate.get("evidence"),
                }
                for candidate in (group.get("candidate_field_fps") or [])[:candidate_sample_size]
            ],
        })
    return {
        "schema_version": metadata.get("schema_version"),
        "generated_at": metadata.get("generated_at"),
        "summary": metadata.get("summary"),
        "sample_standard_fp_groups": sample_groups,
    }


def build_review_report(payload: dict[str, Any]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for record in payload.get("records") or []:
        shared = ((record.get("match_basis") or {}).get("shared_features") or {})
        bucket_id = _bucket_id(shared, record)
        bucket = buckets.setdefault(bucket_id, {
            "bucket_id": bucket_id,
            "summary": {"candidate_count": 0, "confirmed_count": 0},
            "candidate_records": [],
        })
        bucket["summary"]["candidate_count"] += 1
        if record.get("review_status") == "confirmed":
            bucket["summary"]["confirmed_count"] += 1
        bucket["candidate_records"].append(record)
    bucket_list = list(buckets.values())
    for bucket in bucket_list:
        bucket["candidate_records"].sort(key=lambda item: (-float(item.get("semantic_score") or 0), str(item.get("EC"))))
    bucket_list.sort(key=lambda item: (-item["summary"]["candidate_count"], item["bucket_id"]))
    return {
        "metadata": {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "generated_at": (payload.get("metadata") or {}).get("generated_at"),
            "summary": {
                "bucket_count": len(bucket_list),
                "candidate_records": len(payload.get("records") or []),
                "confirmed_records": sum(1 for record in payload.get("records") or [] if record.get("review_status") == "confirmed"),
            },
        },
        "buckets": bucket_list,
    }


def _bucket_id(shared_features: dict[str, list[str]], record: dict[str, Any]) -> str:
    parts = []
    for key in ("modules", "axes", "components", "fault_modes"):
        values = shared_features.get(key) or []
        if values:
            parts.append(f"{key}={'+'.join(values)}")
    if parts:
        return "|".join(parts[:3])
    return "semantic_unclassified"


def build_review_summary(report: dict[str, Any], *, sample_size: int = 12, candidate_sample_size: int = 5) -> dict[str, Any]:
    metadata = report.get("metadata") or {}
    buckets = report.get("buckets") or []
    sample_buckets = []
    for bucket in buckets[:sample_size]:
        sample_buckets.append({
            "bucket_id": bucket.get("bucket_id"),
            "summary": bucket.get("summary"),
            "sample_candidates": [
                {
                    "EC": record.get("EC"),
                    "standard_fp": record.get("standard_fp"),
                    "field_fp_variants": record.get("field_fp_variants"),
                    "semantic_score": record.get("semantic_score"),
                    "embedding_similarity": record.get("embedding_similarity"),
                    "feature_similarity": record.get("feature_similarity"),
                    "review_status": record.get("review_status"),
                    "route_target": record.get("route_target"),
                    "shared_features": (record.get("match_basis") or {}).get("shared_features"),
                }
                for record in (bucket.get("candidate_records") or [])[:candidate_sample_size]
            ],
        })
    return {
        "schema_version": metadata.get("schema_version"),
        "generated_at": metadata.get("generated_at"),
        "summary": metadata.get("summary"),
        "sample_buckets": sample_buckets,
    }
