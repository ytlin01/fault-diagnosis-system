"""Structured FP join aggregation for TASK-005.

The first aggregation MVP joins standardized error codes with downtime records
through FP (Fault Phenomenon). RC is intentionally modeled as possible causes,
not as a verified single root cause. PA/RA is modeled as repair action.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal environments
    yaml = None

SCHEMA_VERSION = "structured_fp_join_v0"
DEFAULT_MIN_CONTAINS_LENGTH = 6
REVIEW_SCHEMA_VERSION = "structured_fp_join_review_v0"
REVIEW_DECISIONS_SCHEMA_VERSION = "structured_fp_join_review_decisions_v0"
VALID_REVIEW_DECISIONS = {"confirmed", "candidate_only", "rejected"}
TEXT2CYPHER_CONFIRMED_MATCH_TYPES = {"normalized_exact", "human_confirmed_review_candidate"}
# Only deterministic joins or explicit human confirmations can enter the
# text2cypher diagnosis route. Candidate or semantic hints stay in governance.

PUNCTUATION_RE = re.compile(r"[\s\u3000,，.。;；:：、/\\|()（）\[\]【】{}<>《》\-—_~～!！?？\"'`]+")
LEADING_MARKER_RE = re.compile(r"^(?:[0-9]+|[一二三四五六七八九十]+)[、.)）．.\-]+")


@dataclass(frozen=True)
class SourceRef:
    source: str
    record_index: int
    record_number: int
    record_id_field: str | None
    record_id_value: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "record_index": self.record_index,
            "record_number": self.record_number,
            "record_id_field": self.record_id_field,
            "record_id_value": self.record_id_value,
        }


def normalize_fp(value: Any) -> str:
    """Normalize a phenomenon string for auditable non-LLM joins."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = LEADING_MARKER_RE.sub("", text).strip()
    return PUNCTUATION_RE.sub("", text)

def load_rules(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    if yaml is None:
        raise RuntimeError("pyyaml is required to load fp_join_rules.yaml")
    with open(path, "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f) or {}


def build_review_decisions_template() -> dict[str, Any]:
    return {
        "schema_version": REVIEW_DECISIONS_SCHEMA_VERSION,
        "metadata": {
            "purpose": "Human review decisions for TASK-005 FP join candidates.",
            "allowed_decisions": sorted(VALID_REVIEW_DECISIONS),
            "decision_semantics": {
                "confirmed": "Promote this reviewed candidate into the join output as a human-confirmed FP link.",
                "candidate_only": "Keep this as a useful candidate, but do not promote it into the join output.",
                "rejected": "Reject this candidate for the specified field FP or review bucket.",
            },
            "minimal_required_fields": ["decision", "EC", "field_fp_normalized"],
            "optional_targeting_fields": ["primary_bucket", "sub_bucket_id", "reviewer", "reviewed_at", "note"],
        },
        "decisions": [],
        "examples": [
            {
                "decision_id": "example-confirm-upstream-z-axis",
                "decision": "confirmed",
                "EC": "M07LOM1-01-03",
                "field_fp": "上料仓Z轴异常",
                "field_fp_normalized": "上料仓z轴异常",
                "primary_bucket": "上料仓",
                "sub_bucket_id": "axes=Z轴|fault_modes=异常",
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


def _iter_review_decisions(review_decisions: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not review_decisions:
        return []
    decisions = review_decisions.get("decisions") or []
    if not isinstance(decisions, list):
        return []
    return [decision for decision in decisions if isinstance(decision, dict)]


def _decision_status(decision: dict[str, Any]) -> str | None:
    value = str(decision.get("decision") or "").strip().lower()
    return value if value in VALID_REVIEW_DECISIONS else None


def _decision_field_norm(decision: dict[str, Any], rules: dict[str, Any] | None = None) -> str:
    explicit = decision.get("field_fp_normalized")
    if explicit not in (None, ""):
        return normalize_fp_with_rules(explicit, rules)
    return normalize_fp_with_rules(decision.get("field_fp") or decision.get("FP"), rules)


def _decision_matches_sub_bucket(decision: dict[str, Any], primary_bucket: dict[str, Any], sub_bucket: dict[str, Any]) -> bool:
    primary = decision.get("primary_bucket")
    if primary not in (None, "") and str(primary) != str(primary_bucket.get("primary_bucket")):
        return False
    sub_bucket_id = decision.get("sub_bucket_id")
    if sub_bucket_id not in (None, "") and str(sub_bucket_id) != str(sub_bucket.get("sub_bucket_id")):
        return False
    field_norm = decision.get("field_fp_normalized")
    if field_norm in (None, ""):
        return True
    target_norm = normalize_fp(field_norm)
    for group in sub_bucket.get("downtime_fp_groups") or []:
        if normalize_fp(group.get("normalized_fp")) == target_norm:
            return True
    return False


def _candidate_decision_payload(decision: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "decision_id": decision.get("decision_id"),
        "decision": status,
        "reviewer": decision.get("reviewer"),
        "reviewed_at": decision.get("reviewed_at"),
        "note": decision.get("note"),
    }


def _roll_up_candidate_status(statuses: list[str]) -> str:
    if "confirmed" in statuses:
        return "confirmed"
    if "candidate_only" in statuses:
        return "candidate_only"
    if statuses and all(status == "rejected" for status in statuses):
        return "rejected"
    return "needs_review"


def _candidate_decision_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(candidate.get("review_status") or "needs_review") for candidate in candidates)
    return {status: counts.get(status, 0) for status in ["confirmed", "candidate_only", "rejected", "needs_review"]}


def apply_review_decisions_to_report(report: dict[str, Any], review_decisions: dict[str, Any] | None) -> dict[str, Any]:
    decisions = _iter_review_decisions(review_decisions)
    summary: dict[str, Any] = {
        "schema_version": (review_decisions or {}).get("schema_version"),
        "decision_count": len(decisions),
        "applied_count": 0,
        "ignored_count": 0,
        "decision_counts": {status: 0 for status in sorted(VALID_REVIEW_DECISIONS)},
        "ignored_decisions": [],
    }
    if not decisions:
        return summary

    applied_decision_ids: set[int] = set()
    for primary_bucket in report.get("primary_buckets") or []:
        primary_status_by_ec: dict[str, list[str]] = defaultdict(list)
        primary_decision_by_ec: dict[str, dict[str, Any]] = {}
        for sub_bucket in primary_bucket.get("sub_buckets") or []:
            sub_candidates = sub_bucket.get("candidate_error_codes") or []
            for candidate in sub_candidates:
                candidate.setdefault("review_status", "needs_review")
                ec = str(candidate.get("EC"))
                for index, decision in enumerate(decisions):
                    status = _decision_status(decision)
                    if status is None:
                        continue
                    if str(decision.get("EC") or "") != ec:
                        continue
                    if not _decision_matches_sub_bucket(decision, primary_bucket, sub_bucket):
                        continue
                    candidate["review_status"] = status
                    candidate["review_decision"] = _candidate_decision_payload(decision, status)
                    applied_decision_ids.add(index)
                    summary["decision_counts"][status] += 1
                    primary_status_by_ec[ec].append(status)
                    primary_decision_by_ec[ec] = candidate["review_decision"]
            sub_bucket["candidate_decision_counts"] = _candidate_decision_counts(sub_candidates)

        for candidate in primary_bucket.get("candidate_error_codes") or []:
            ec = str(candidate.get("EC"))
            candidate["review_status"] = _roll_up_candidate_status(primary_status_by_ec.get(ec, []))
            if ec in primary_decision_by_ec:
                candidate["review_decision"] = primary_decision_by_ec[ec]
        primary_bucket["candidate_decision_counts"] = _candidate_decision_counts(primary_bucket.get("candidate_error_codes") or [])

    for index, decision in enumerate(decisions):
        status = _decision_status(decision)
        if status is None:
            summary["ignored_decisions"].append({
                "decision_id": decision.get("decision_id"),
                "reason": "invalid_decision",
                "decision": decision.get("decision"),
            })
        elif index not in applied_decision_ids:
            summary["ignored_decisions"].append({
                "decision_id": decision.get("decision_id"),
                "reason": "no_matching_review_candidate",
                "EC": decision.get("EC"),
                "field_fp_normalized": decision.get("field_fp_normalized"),
            })

    summary["applied_count"] = len(applied_decision_ids)
    summary["ignored_count"] = len(summary["ignored_decisions"])
    summary["ignored_decisions"] = summary["ignored_decisions"][:20]
    return summary


def apply_text_replacements(text: str, rules: dict[str, Any] | None) -> str:
    result = text
    replacements = ((rules or {}).get("normalization") or {}).get("replacements") or {}
    for old, new in replacements.items():
        result = result.replace(str(old), str(new))
    return result


def normalize_fp_with_rules(value: Any, rules: dict[str, Any] | None = None) -> str:
    return normalize_fp(apply_text_replacements("" if value is None else str(value), rules))


def _aliases_for(term_config: Any) -> list[str]:
    if isinstance(term_config, dict):
        aliases = term_config.get("aliases") or []
        return [str(alias) for alias in aliases]
    if isinstance(term_config, list):
        return [str(alias) for alias in term_config]
    return []


def extract_fp_features(value: Any, rules: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Extract governed, auditable FP features from a phenomenon string."""
    rules = rules or {}
    normalized = normalize_fp_with_rules(value, rules)
    features: dict[str, list[str]] = {
        "modules": [],
        "axes": [],
        "components": [],
        "fault_modes": [],
    }
    term_groups = (rules.get("feature_terms") or {})
    for group_name in features:
        for canonical, term_config in (term_groups.get(group_name) or {}).items():
            aliases = [canonical] + _aliases_for(term_config)
            if any(normalize_fp_with_rules(alias, rules) in normalized for alias in aliases):
                features[group_name].append(str(canonical))
    features = {key: sorted(set(values)) for key, values in features.items()}
    if features.get("fault_modes"):
        parents = _fault_mode_parent_map(rules)
        child_parents = {parents[value] for value in features["fault_modes"] if parents.get(value)}
        features["fault_modes"] = [value for value in features["fault_modes"] if value not in child_parents]
    return features


def _feature_overlap(left: dict[str, list[str]], right: dict[str, list[str]]) -> dict[str, list[str]]:
    overlap: dict[str, list[str]] = {}
    for key in ("modules", "axes", "components", "fault_modes"):
        values = sorted(set(left.get(key, [])) & set(right.get(key, [])))
        if values:
            overlap[key] = values
    return overlap


def _fault_mode_parent_map(rules: dict[str, Any]) -> dict[str, str]:
    modes = ((rules.get("feature_terms") or {}).get("fault_modes") or {})
    return {
        str(name): str(config.get("parent"))
        for name, config in modes.items()
        if isinstance(config, dict) and config.get("parent")
    }


def _fault_mode_relation(ec_modes: list[str], downtime_modes: list[str], rules: dict[str, Any]) -> dict[str, Any] | None:
    if not ec_modes or not downtime_modes:
        return None
    shared = sorted(set(ec_modes) & set(downtime_modes))
    if shared:
        return {"type": "same_fault_mode", "values": shared}
    parents = _fault_mode_parent_map(rules)
    related: list[dict[str, str]] = []
    for ec_mode in ec_modes:
        for dt_mode in downtime_modes:
            if parents.get(ec_mode) == dt_mode:
                related.append({"ec_fault_mode": ec_mode, "downtime_fault_mode": dt_mode, "relation": "downtime_generic_to_ec_specific"})
            elif parents.get(dt_mode) == ec_mode:
                related.append({"ec_fault_mode": ec_mode, "downtime_fault_mode": dt_mode, "relation": "ec_generic_to_downtime_specific"})
    if related:
        return {"type": "parent_child_fault_mode", "values": related}
    return None


def _feature_score(overlap: dict[str, list[str]], rules: dict[str, Any]) -> int:
    weights = ((rules.get("review") or {}).get("feature_weights") or {})
    return sum(int(weights.get(key, 1)) * len(values) for key, values in overlap.items())


def _char_ngram_counter(text: str, n_values: list[int]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for n in n_values:
        if n <= 0:
            continue
        if len(text) < n:
            if text:
                counter[text] += 1
            continue
        for index in range(0, len(text) - n + 1):
            counter[text[index:index + n]] += 1
    return counter


def _counter_cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in shared)
    left_norm = sum(value * value for value in left.values()) ** 0.5
    right_norm = sum(value * value for value in right.values()) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _feature_similarity(left: dict[str, list[str]], right: dict[str, list[str]], overlap: dict[str, list[str]], rules: dict[str, Any]) -> float:
    weights = ((rules.get("review") or {}).get("feature_weights") or {})

    def weighted_total(features: dict[str, list[str]]) -> int:
        return sum(int(weights.get(key, 1)) * len(values) for key, values in features.items())

    denominator = min(weighted_total(left), weighted_total(right))
    if denominator <= 0:
        return 0.0
    return min(1.0, _feature_score({k: v for k, v in overlap.items() if k != "fault_mode_relation"}, rules) / denominator)


def _semantic_candidate_settings(rules: dict[str, Any]) -> dict[str, Any]:
    settings = ((rules.get("review") or {}).get("semantic_candidates") or {})
    return {
        "enabled": bool(settings.get("enabled", False)),
        "min_score": float(settings.get("min_score", 0.58)),
        "require_any_feature_overlap": bool(settings.get("require_any_feature_overlap", True)),
        "require_shared_module": bool(settings.get("require_shared_module", False)),
        "char_ngram_n": [int(value) for value in (settings.get("char_ngram_n") or [2, 3])],
        "weights": settings.get("weights") or {"char_ngram": 0.72, "feature": 0.28},
    }


def _semantic_candidate_score(
    *,
    ec: dict[str, Any],
    downtime_norm: str,
    downtime_features: dict[str, list[str]],
    overlap: dict[str, list[str]],
    relation: dict[str, Any] | None,
    rules: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    n_values = settings["char_ngram_n"]
    char_score = _counter_cosine(
        _char_ngram_counter(ec.get("normalized_fp") or "", n_values),
        _char_ngram_counter(downtime_norm, n_values),
    )
    feature_score = _feature_similarity(ec.get("features") or {}, downtime_features, overlap, rules)
    weights = settings["weights"]
    semantic_score = (
        float(weights.get("char_ngram", 0.72)) * char_score
        + float(weights.get("feature", 0.28)) * feature_score
    )
    if relation:
        semantic_score = min(1.0, semantic_score + 0.04)
    return {
        "semantic_score": round(semantic_score, 4),
        "char_ngram_score": round(char_score, 4),
        "feature_score": round(feature_score, 4),
        "rank_score": round((semantic_score * 10) + (_feature_score({k: v for k, v in overlap.items() if k != "fault_mode_relation"}, rules) * 0.15), 4),
    }


def _passes_semantic_guardrails(
    *,
    ec: dict[str, Any],
    downtime_features: dict[str, list[str]],
    overlap: dict[str, list[str]],
    relation: dict[str, Any] | None,
    settings: dict[str, Any],
) -> bool:
    shared_non_relation = {key: value for key, value in overlap.items() if key != "fault_mode_relation"}
    if settings["require_any_feature_overlap"] and not shared_non_relation and not relation:
        return False
    if settings["require_shared_module"] and not (set((ec.get("features") or {}).get("modules", [])) & set(downtime_features.get("modules", []))):
        return False
    return True


def _candidate_rank_score(candidate: dict[str, Any]) -> float:
    return float(candidate.get("rank_score", candidate.get("score", 0)) or 0)


def _shared_feature_count(overlap: dict[str, list[str]]) -> int:
    return sum(len(values) for values in overlap.values())


def _make_bucket_id(features: dict[str, list[str]], rules: dict[str, Any]) -> str:
    priority = ((rules.get("review") or {}).get("bucket_priority_features") or ["modules", "axes", "components", "fault_modes"])
    parts: list[str] = []
    for key in priority:
        values = features.get(key) or []
        if values:
            parts.append(f"{key}={'+'.join(values)}")
    if not parts:
        return "unclassified"
    return "|".join(parts[:3])


def _primary_bucket_info(features: dict[str, list[str]], rules: dict[str, Any]) -> dict[str, str]:
    strategy = ((rules.get("review") or {}).get("primary_bucket_strategy") or {})
    default = str(strategy.get("default") or "unclassified")
    feature_priority = strategy.get("feature_priority") or {}
    for group_name, preferred_values in feature_priority.items():
        feature_values = set(features.get(group_name, []))
        for value in preferred_values or []:
            value = str(value)
            if value in feature_values:
                return {
                    "primary_bucket": value,
                    "primary_feature": str(group_name),
                    "primary_basis": "configured_feature_priority",
                }
    for group_name in ("modules", "axes", "components", "fault_modes"):
        values = features.get(group_name) or []
        if values:
            return {
                "primary_bucket": values[0],
                "primary_feature": group_name,
                "primary_basis": "fallback_first_feature",
            }
    return {
        "primary_bucket": default,
        "primary_feature": "none",
        "primary_basis": "no_feature_match",
    }


def _sub_bucket_info(features: dict[str, list[str]], primary: dict[str, str], rules: dict[str, Any]) -> dict[str, str]:
    strategy = ((rules.get("review") or {}).get("primary_bucket_strategy") or {})
    sub_features = strategy.get("sub_bucket_features") or ["axes", "components", "fault_modes", "modules"]
    parts: list[str] = []
    labels: list[str] = []
    for group_name in sub_features:
        values = list(features.get(group_name, []))
        if group_name == primary.get("primary_feature"):
            values = [value for value in values if value != primary.get("primary_bucket")]
        if values:
            parts.append(f"{group_name}={'+'.join(values)}")
            labels.extend(values)
    if not parts:
        return {"sub_bucket_id": "general", "sub_bucket_label": "general"}
    return {"sub_bucket_id": "|".join(parts), "sub_bucket_label": " / ".join(labels)}


def _empty_review_summary() -> dict[str, float]:
    return {"fp_group_count": 0, "evidence_count": 0, "total_dt_mins": 0.0}


def _add_review_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["fp_group_count"] += int(source.get("fp_group_count") or 0)
    target["evidence_count"] += int(source.get("evidence_count") or 0)
    target["total_dt_mins"] += float(source.get("total_dt_mins") or 0.0)


def _merge_candidate(target: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> None:
    key = str(candidate.get("EC"))
    existing = target.get(key)
    if existing is None or float(candidate.get("score") or 0) > float(existing.get("score") or 0):
        target[key] = candidate


def _sorted_candidates(candidates: dict[str, dict[str, Any]], max_candidates: int) -> list[dict[str, Any]]:
    return sorted(
        candidates.values(),
        key=lambda item: (-_candidate_rank_score(item), str(item.get("EC"))),
    )[:max_candidates]


def _build_primary_buckets(
    flat_buckets: list[dict[str, Any]],
    rules: dict[str, Any],
    *,
    max_candidates: int,
) -> list[dict[str, Any]]:
    primary_map: dict[str, dict[str, Any]] = {}
    for flat_bucket in flat_buckets:
        primary = _primary_bucket_info(flat_bucket.get("features") or {}, rules)
        primary_id = primary["primary_bucket"]
        primary_bucket = primary_map.setdefault(primary_id, {
            "primary_bucket": primary_id,
            "primary_feature": primary["primary_feature"],
            "primary_basis": primary["primary_basis"],
            "review_status": "needs_review",
            "summary": _empty_review_summary(),
            "sub_buckets": {},
            "candidate_error_codes": {},
            "source_bucket_ids": [],
        })
        _add_review_summary(primary_bucket["summary"], flat_bucket.get("summary") or {})
        primary_bucket["source_bucket_ids"].append(flat_bucket.get("bucket_id"))

        sub = _sub_bucket_info(flat_bucket.get("features") or {}, primary, rules)
        sub_bucket = primary_bucket["sub_buckets"].setdefault(sub["sub_bucket_id"], {
            "sub_bucket_id": sub["sub_bucket_id"],
            "sub_bucket_label": sub["sub_bucket_label"],
            "features": flat_bucket.get("features") or {},
            "review_status": "needs_review",
            "summary": _empty_review_summary(),
            "downtime_fp_groups": [],
            "candidate_error_codes": {},
            "source_bucket_ids": [],
        })
        _add_review_summary(sub_bucket["summary"], flat_bucket.get("summary") or {})
        sub_bucket["downtime_fp_groups"].extend(flat_bucket.get("downtime_fp_groups") or [])
        sub_bucket["source_bucket_ids"].append(flat_bucket.get("bucket_id"))

        for candidate in flat_bucket.get("candidate_error_codes") or []:
            _merge_candidate(primary_bucket["candidate_error_codes"], candidate)
            _merge_candidate(sub_bucket["candidate_error_codes"], candidate)

    primary_buckets: list[dict[str, Any]] = []
    for primary_bucket in primary_map.values():
        sub_buckets = list(primary_bucket["sub_buckets"].values())
        for sub_bucket in sub_buckets:
            sub_bucket["candidate_error_codes"] = _sorted_candidates(sub_bucket["candidate_error_codes"], max_candidates)
        sub_buckets.sort(key=lambda item: (-item["summary"]["total_dt_mins"], -item["summary"]["evidence_count"], item["sub_bucket_id"]))
        primary_bucket["sub_buckets"] = sub_buckets
        primary_bucket["candidate_error_codes"] = _sorted_candidates(primary_bucket["candidate_error_codes"], max_candidates)
        primary_buckets.append(primary_bucket)

    primary_buckets.sort(key=lambda item: (-item["summary"]["total_dt_mins"], -item["summary"]["evidence_count"], item["primary_bucket"]))
    return primary_buckets

def _indexed_ec_features(error_code_records: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    indexed = []
    for index, record in enumerate(error_code_records):
        fp = record.get("Description")
        indexed.append({
            "EC": record.get("Error code"),
            "FP": fp,
            "normalized_fp": normalize_fp_with_rules(fp, rules),
            "features": extract_fp_features(fp, rules),
            "source_ref": make_source_ref("error_codes_standardized", record, index).as_dict(),
        })
    return indexed


def build_review_report(
    error_code_records: list[dict[str, Any]],
    downtime_records: list[dict[str, Any]],
    rules: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
    review_decisions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build bucketed unmatched-review candidates for human governance."""
    rules = rules or {}
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    min_shared = int(((rules.get("review") or {}).get("min_shared_features") or 2))
    max_candidates = int(((rules.get("review") or {}).get("max_candidates_per_bucket") or 12))
    semantic_settings = _semantic_candidate_settings(rules)
    ec_index = _indexed_ec_features(error_code_records, rules)
    groups = group_downtime_by_fp(downtime_records)
    buckets: dict[str, dict[str, Any]] = {}

    for downtime_norm, downtime_group in sorted(groups.items()):
        downtime_fps = _unique_non_empty([record.get("異常描敘") for record in downtime_group])
        display_fp = downtime_fps[0] if downtime_fps else downtime_norm
        features = extract_fp_features(display_fp, rules)
        bucket_id = _make_bucket_id(features, rules)
        bucket = buckets.setdefault(bucket_id, {
            "bucket_id": bucket_id,
            "features": features,
            "downtime_fp_groups": [],
            "candidate_error_codes": {},
            "review_status": "needs_review",
        })
        bucket["downtime_fp_groups"].append({
            "FP": downtime_fps,
            "field_fp_variants": downtime_fps,
            "field_fp_source": "y25_downtime.異常描敘",
            "normalized_fp": normalize_fp_with_rules(display_fp, rules),
            "features": features,
            "source_refs": [record["_source_ref"] for record in downtime_group],
            "evidence": summarize_downtime(downtime_group),
        })
        for ec in ec_index:
            overlap = _feature_overlap(ec["features"], features)
            relation = _fault_mode_relation(ec["features"].get("fault_modes", []), features.get("fault_modes", []), rules)
            if relation and "fault_modes" not in overlap:
                overlap["fault_mode_relation"] = [relation["type"]]
            shared_non_relation = {key: value for key, value in overlap.items() if key != "fault_mode_relation"}
            key = ec["EC"]
            has_shared_module = bool(set(ec["features"].get("modules", [])) & set(features.get("modules", [])))
            feature_candidate_allowed = (
                (_shared_feature_count(shared_non_relation) >= min_shared or relation)
                and has_shared_module
            )

            if feature_candidate_allowed:
                score = _feature_score(shared_non_relation, rules)
                if relation:
                    score += 1
                existing = bucket["candidate_error_codes"].get(key)
                candidate = {
                    "EC": ec["EC"],
                    "FP": ec["FP"],
                    "standard_fp": ec["FP"],
                    "standard_fp_source": "error_codes_standardized.Description",
                    "normalized_fp": ec["normalized_fp"],
                    "features": ec["features"],
                    "score": score,
                    "rank_score": score,
                    "candidate_reason": {
                        "candidate_type": "feature_candidate",
                        "shared_features": overlap,
                        "fault_mode_relation": relation,
                        "rule": "same module plus shared feature or governed fault-mode relation",
                    },
                    "review_status": "needs_review",
                    "kg_diagnosis_eligible": False,
                    "chain_status": "review_candidate",
                    "route_target": "fp_review_governance",
                    "source_ref": ec["source_ref"],
                }
                if existing is None or _candidate_rank_score(candidate) > _candidate_rank_score(existing):
                    bucket["candidate_error_codes"][key] = candidate

            if not semantic_settings["enabled"]:
                continue
            if not _passes_semantic_guardrails(
                ec=ec,
                downtime_features=features,
                overlap=overlap,
                relation=relation,
                settings=semantic_settings,
            ):
                continue
            semantic_scores = _semantic_candidate_score(
                ec=ec,
                downtime_norm=normalize_fp_with_rules(display_fp, rules),
                downtime_features=features,
                overlap=overlap,
                relation=relation,
                rules=rules,
                settings=semantic_settings,
            )
            if semantic_scores["semantic_score"] < semantic_settings["min_score"]:
                continue
            semantic_candidate = {
                "EC": ec["EC"],
                "FP": ec["FP"],
                "standard_fp": ec["FP"],
                "standard_fp_source": "error_codes_standardized.Description",
                "normalized_fp": ec["normalized_fp"],
                "features": ec["features"],
                "score": semantic_scores["rank_score"],
                "rank_score": semantic_scores["rank_score"],
                "candidate_reason": {
                    "candidate_type": "semantic_candidate",
                    "semantic_method": "local_char_ngram_cosine_with_governed_feature_guardrails",
                    "semantic_score": semantic_scores["semantic_score"],
                    "char_ngram_score": semantic_scores["char_ngram_score"],
                    "feature_score": semantic_scores["feature_score"],
                    "shared_features": overlap,
                    "fault_mode_relation": relation,
                    "guardrails": {
                        "require_any_feature_overlap": semantic_settings["require_any_feature_overlap"],
                        "require_shared_module": semantic_settings["require_shared_module"],
                    },
                    "rule": "lightweight local semantic candidate; requires review before join promotion",
                },
                "review_status": "needs_review",
                "kg_diagnosis_eligible": False,
                "chain_status": "review_candidate",
                "route_target": "fp_review_governance",
                "source_ref": ec["source_ref"],
            }
            existing = bucket["candidate_error_codes"].get(key)
            if existing is None or _candidate_rank_score(semantic_candidate) > _candidate_rank_score(existing):
                bucket["candidate_error_codes"][key] = semantic_candidate


    bucket_list: list[dict[str, Any]] = []
    for bucket in buckets.values():
        candidates = sorted(
            bucket["candidate_error_codes"].values(),
            key=lambda item: (-_candidate_rank_score(item), str(item["EC"])),
        )[:max_candidates]
        downtime_summary = {
            "fp_group_count": len(bucket["downtime_fp_groups"]),
            "evidence_count": sum(group["evidence"]["count"] for group in bucket["downtime_fp_groups"]),
            "total_dt_mins": sum(group["evidence"]["total_dt_mins"] for group in bucket["downtime_fp_groups"]),
        }
        bucket["candidate_error_codes"] = candidates
        bucket["summary"] = downtime_summary
        bucket_list.append(bucket)

    bucket_list.sort(key=lambda item: (-item["summary"]["total_dt_mins"], -item["summary"]["evidence_count"], item["bucket_id"]))
    primary_buckets = _build_primary_buckets(bucket_list, rules, max_candidates=max_candidates)
    sub_bucket_count = sum(len(bucket.get("sub_buckets") or []) for bucket in primary_buckets)
    report = {
        "metadata": {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "generated_at": generated_at,
            "purpose": "Bucket unmatched FP groups and propose auditable candidate EC links for human review.",
            "rule_profile": {
                "config_driven": True,
                "hierarchical_review": True,
                "primary_bucket_strategy": ((rules.get("review") or {}).get("primary_bucket_strategy") or {}),
                "min_shared_features": min_shared,
                "max_candidates_per_bucket": max_candidates,
                "semantic_candidates": semantic_settings,
                "no_embedding_or_llm": True,
            },
            "summary": {
                "bucket_count": len(primary_buckets),
                "primary_bucket_count": len(primary_buckets),
                "sub_bucket_count": sub_bucket_count,
                "flat_bucket_count": len(bucket_list),
                "downtime_fp_groups": len(groups),
                "buckets_with_candidates": sum(1 for bucket in primary_buckets if bucket["candidate_error_codes"]),
                "flat_buckets_with_candidates": sum(1 for bucket in bucket_list if bucket["candidate_error_codes"]),
                "semantic_candidate_links": sum(
                    1
                    for bucket in bucket_list
                    for candidate in bucket["candidate_error_codes"]
                    if (candidate.get("candidate_reason") or {}).get("candidate_type") == "semantic_candidate"
                ),
            },
        },
        "primary_buckets": primary_buckets,
        "buckets": bucket_list,
    }
    report["metadata"]["review_decisions"] = apply_review_decisions_to_report(report, review_decisions)
    return report


def _review_action(candidate_count: int) -> str:
    if candidate_count > 0:
        return "review_candidates"
    return "classify_or_add_rule"


def _review_action_reason(candidate_count: int) -> str:
    if candidate_count > 0:
        return "Candidate EC links were proposed; reviewer should confirm, keep candidate-only, or reject them."
    return "No candidate EC links were proposed; reviewer should classify the field FP, add rules, or keep it unmatched."

def _candidate_digest(candidate: dict[str, Any]) -> dict[str, Any]:
    review_decision = candidate.get("review_decision") or {}
    return {
        "EC": candidate.get("EC"),
        "FP": candidate.get("FP"),
        "standard_fp": candidate.get("standard_fp") or candidate.get("FP"),
        "standard_fp_source": candidate.get("standard_fp_source"),
        "score": candidate.get("score"),
        "rank_score": candidate.get("rank_score", candidate.get("score")),
        "review_status": candidate.get("review_status") or "needs_review",
        "kg_diagnosis_eligible": candidate.get("kg_diagnosis_eligible", False),
        "chain_status": candidate.get("chain_status"),
        "route_target": candidate.get("route_target"),
        "review_decision": review_decision or None,
        "candidate_reason": candidate.get("candidate_reason"),
    }


def _sub_bucket_digest(sub_bucket: dict[str, Any], *, candidate_sample_size: int = 5, fp_sample_size: int = 5) -> dict[str, Any]:
    fp_samples: list[Any] = []
    for group in sub_bucket.get("downtime_fp_groups") or []:
        fp_samples.append(group.get("FP"))
        if len(fp_samples) >= fp_sample_size:
            break
    candidates = sub_bucket.get("candidate_error_codes") or []
    candidate_count = len(candidates)
    return {
        "sub_bucket_id": sub_bucket.get("sub_bucket_id"),
        "sub_bucket_label": sub_bucket.get("sub_bucket_label"),
        "review_status": sub_bucket.get("review_status") or "needs_review",
        "review_action": _review_action(candidate_count),
        "review_action_reason": _review_action_reason(candidate_count),
        "summary": sub_bucket.get("summary"),
        "candidate_count": candidate_count,
        "candidate_decision_counts": _candidate_decision_counts(candidates),
        "sample_downtime_fps": fp_samples,
        "sample_candidates": [_candidate_digest(candidate) for candidate in candidates[:candidate_sample_size]],
    }


def _primary_bucket_digest(bucket: dict[str, Any], *, sub_bucket_sample_size: int = 8, candidate_sample_size: int = 8) -> dict[str, Any]:
    candidates = bucket.get("candidate_error_codes") or []
    sub_buckets = bucket.get("sub_buckets") or []
    candidate_count = len(candidates)
    return {
        "primary_bucket": bucket.get("primary_bucket"),
        "primary_feature": bucket.get("primary_feature"),
        "primary_basis": bucket.get("primary_basis"),
        "review_status": bucket.get("review_status") or "needs_review",
        "review_action": _review_action(candidate_count),
        "review_action_reason": _review_action_reason(candidate_count),
        "summary": bucket.get("summary"),
        "sub_bucket_count": len(sub_buckets),
        "candidate_count": candidate_count,
        "candidate_decision_counts": _candidate_decision_counts(candidates),
        "sample_candidates": [_candidate_digest(candidate) for candidate in candidates[:candidate_sample_size]],
        "sample_sub_buckets": [_sub_bucket_digest(sub_bucket) for sub_bucket in sub_buckets[:sub_bucket_sample_size]],
    }


def build_review_summary(report: dict[str, Any], *, sample_size: int = 20) -> dict[str, Any]:
    metadata = report.get("metadata", {})
    primary_buckets = report.get("primary_buckets", [])
    flat_buckets = report.get("buckets", [])
    return {
        "schema_version": metadata.get("schema_version"),
        "generated_at": metadata.get("generated_at"),
        "summary": metadata.get("summary"),
        "review_decisions": metadata.get("review_decisions"),
        "sample_primary_buckets": [_primary_bucket_digest(bucket) for bucket in primary_buckets[:sample_size]],
        "sample_flat_bucket_ids": [bucket.get("bucket_id") for bucket in flat_buckets[:sample_size]],
    }

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, payload: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        else:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")


def make_source_ref(source: str, record: dict[str, Any], index: int) -> SourceRef:
    if source == "error_codes_standardized":
        id_field = "Index" if "Index" in record else None
    elif source == "y25_downtime":
        id_field = "序號" if "序號" in record else None
    else:
        id_field = None
    return SourceRef(
        source=source,
        record_index=index,
        record_number=index + 1,
        record_id_field=id_field,
        record_id_value=record.get(id_field) if id_field else None,
    )


def stable_id(*parts: Any, prefix: str = "MAP") -> str:
    raw = "||".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _as_number(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _unique_non_empty(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        if value is None or value == "":
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _flatten_qpl(values: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(value)
        elif value not in (None, ""):
            flattened.append(value)
    return _unique_non_empty(flattened)


def _date_range(values: list[Any]) -> dict[str, Any]:
    dates = sorted(str(value) for value in values if value not in (None, ""))
    if not dates:
        return {"min": None, "max": None}
    return {"min": dates[0], "max": dates[-1]}


def group_downtime_by_fp(downtime_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(downtime_records):
        normalized = normalize_fp(record.get("異常描敘"))
        if not normalized:
            continue
        enriched = dict(record)
        enriched["_source_ref"] = make_source_ref("y25_downtime", record, index).as_dict()
        enriched["_normalized_fp"] = normalized
        groups[normalized].append(enriched)
    return dict(groups)


def summarize_downtime(records: list[dict[str, Any]]) -> dict[str, Any]:
    risk_counts = Counter(str(record.get("Risk")) for record in records if record.get("Risk") not in (None, ""))
    status_counts = Counter(str(record.get("Status")) for record in records if record.get("Status") not in (None, ""))
    return {
        "count": len(records),
        "total_dt_mins": sum(_as_number(record.get("DT(Mins)")) for record in records),
        "risk_counts": dict(sorted(risk_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "qpl_values": _flatten_qpl([record.get("QPL") for record in records]),
        "date_range": _date_range([record.get("Date") for record in records]),
    }


def _missing_chain_fields(
    *,
    ec: Any = None,
    standard_fp: Any = None,
    field_fp_variants: list[Any] | None = None,
    possible_causes: list[Any] | None = None,
    repair_actions: list[Any] | None = None,
) -> list[str]:
    missing: list[str] = []
    if ec in (None, ""):
        missing.append("EC")
    if standard_fp in (None, ""):
        missing.append("standard_fp")
    if not field_fp_variants:
        missing.append("field_fp_variants")
    if not possible_causes:
        missing.append("RC")
    if not repair_actions:
        missing.append("PA")
    return missing


def build_join_route_status(
    *,
    match_type: str,
    ec: Any,
    standard_fp: Any,
    field_fp_variants: list[Any],
    possible_causes: list[Any],
    repair_actions: list[Any],
) -> dict[str, Any]:
    missing = _missing_chain_fields(
        ec=ec,
        standard_fp=standard_fp,
        field_fp_variants=field_fp_variants,
        possible_causes=possible_causes,
        repair_actions=repair_actions,
    )
    if match_type == "contains_candidate":
        return {
            "kg_diagnosis_eligible": False,
            "chain_status": "complete_candidate_review_required" if not missing else "incomplete_candidate_review_required",
            "route_target": "fp_review_governance",
            "route_reason": "Contains-based FP links are candidates and must be human-reviewed before text2cypher diagnosis.",
            "missing_chain_fields": missing,
        }
    if missing:
        return {
            "kg_diagnosis_eligible": False,
            "chain_status": "incomplete_confirmed_missing_chain_fields" if match_type in TEXT2CYPHER_CONFIRMED_MATCH_TYPES else "incomplete_unconfirmed_missing_chain_fields",
            "route_target": "case_retrieval",
            "route_reason": "The EC/FP link exists, but the EC/FP/RC/PA diagnosis chain is incomplete.",
            "missing_chain_fields": missing,
        }
    if match_type in TEXT2CYPHER_CONFIRMED_MATCH_TYPES:
        return {
            "kg_diagnosis_eligible": True,
            "chain_status": "complete_confirmed",
            "route_target": "text2cypher_diagnosis",
            "route_reason": "Complete EC/FP/RC/PA chain with a confirmed or deterministic FP link.",
            "missing_chain_fields": [],
        }
    return {
        "kg_diagnosis_eligible": False,
        "chain_status": "complete_unconfirmed",
        "route_target": "fp_review_governance",
        "route_reason": "Complete chain exists but the match type is not eligible for text2cypher diagnosis.",
        "missing_chain_fields": [],
    }


def build_ec_catalog_route_status(*, fp: Any, reason: str) -> dict[str, Any]:
    missing = ["field_fp_variants", "RC", "PA"]
    if fp in (None, ""):
        missing.insert(0, "standard_fp")
    return {
        "kg_diagnosis_eligible": False,
        "chain_status": "ec_catalog_invalid_fp" if reason == "empty_normalized_fp" else "ec_catalog_only",
        "route_target": "structured_catalog",
        "route_reason": "Error-code catalog entry lacks a confirmed downtime FP link and RC/PA evidence.",
        "missing_chain_fields": missing,
    }


def build_case_route_status(*, field_fp_variants: list[Any], possible_causes: list[Any], repair_actions: list[Any]) -> dict[str, Any]:
    missing = _missing_chain_fields(
        ec=None,
        standard_fp=None,
        field_fp_variants=field_fp_variants,
        possible_causes=possible_causes,
        repair_actions=repair_actions,
    )
    return {
        "kg_diagnosis_eligible": False,
        "chain_status": "case_only_without_ec" if missing == ["EC", "standard_fp"] else "case_only_without_ec_incomplete",
        "route_target": "case_retrieval",
        "route_reason": "Downtime case evidence lacks a confirmed EC/standard FP link, so it should be retrieved as case evidence instead of queried as a diagnosis chain.",
        "missing_chain_fields": missing,
    }


def _route_status_summary(records: list[dict[str, Any]], unmatched_ec: list[dict[str, Any]], unmatched_downtime: list[dict[str, Any]]) -> dict[str, Any]:
    all_items = [*records, *unmatched_ec, *unmatched_downtime]
    return {
        "kg_diagnosis_eligible_records": sum(1 for record in records if record.get("kg_diagnosis_eligible") is True),
        "chain_status_counts": dict(sorted(Counter(str(item.get("chain_status")) for item in all_items if item.get("chain_status")).items())),
        "route_target_counts": dict(sorted(Counter(str(item.get("route_target")) for item in all_items if item.get("route_target")).items())),
    }


def build_join_record(
    *,
    ec_record: dict[str, Any],
    ec_index: int,
    ec_norm: str,
    downtime_norm: str,
    downtime_records: list[dict[str, Any]],
    match_type: str,
    review_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ec = ec_record.get("Error code")
    ec_fp = ec_record.get("Description")
    downtime_fps = _unique_non_empty([record.get("異常描敘") for record in downtime_records])
    possible_causes = _unique_non_empty([record.get("原因") for record in downtime_records])
    repair_actions = _unique_non_empty([record.get("維修動作") for record in downtime_records])
    if match_type == "normalized_exact":
        rule = "normalized FP equality"
    elif match_type == "contains_candidate":
        rule = "one normalized FP contains the other"
    elif match_type == "human_confirmed_review_candidate":
        rule = "explicit human review decision"
    else:
        rule = "unknown match rule"
    match_basis = {
        "rule": rule,
        "ec_fp_normalized": ec_norm,
        "downtime_fp_normalized": downtime_norm,
        "downtime_fp_values": downtime_fps,
        "field_fp_variants": downtime_fps,
    }
    if review_decision:
        match_basis["review_decision"] = {
            "decision_id": review_decision.get("decision_id"),
            "decision": review_decision.get("decision"),
            "reviewer": review_decision.get("reviewer"),
            "reviewed_at": review_decision.get("reviewed_at"),
            "note": review_decision.get("note"),
        }
    route_status = build_join_route_status(
        match_type=match_type,
        ec=ec,
        standard_fp=ec_fp,
        field_fp_variants=downtime_fps,
        possible_causes=possible_causes,
        repair_actions=repair_actions,
    )
    return {
        "mapping_id": stable_id(ec, ec_norm, downtime_norm, match_type),
        "EC": ec,
        "FP": ec_fp,
        "standard_fp": ec_fp,
        "standard_fp_source": "error_codes_standardized.Description",
        "field_fp_variants": downtime_fps,
        "field_fp_source": "y25_downtime.異常描敘",
        "RC": possible_causes,
        "PA": repair_actions,
        "kg_diagnosis_eligible": route_status["kg_diagnosis_eligible"],
        "chain_status": route_status["chain_status"],
        "route_target": route_status["route_target"],
        "route_reason": route_status["route_reason"],
        "missing_chain_fields": route_status["missing_chain_fields"],
        "semantics": {
            "EC": "Error Code",
            "FP": "Backward-compatible alias of standard_fp",
            "standard_fp": "Standard Fault Phenomenon from error_codes_standardized.Description",
            "field_fp_variants": "Field Fault Phenomenon surface variants from y25_downtime.異常描敘",
            "RC": "Possible Causes / candidate causes; not a verified unique root cause",
            "PA": "Repair Action; equivalent to RA in this MVP",
        },
        "match_type": match_type,
        "match_basis": match_basis,
        "source_refs": {
            "error_code": [make_source_ref("error_codes_standardized", ec_record, ec_index).as_dict()],
            "downtime": [record["_source_ref"] for record in downtime_records],
        },
        "evidence": summarize_downtime(downtime_records),
    }


def _contains_match(left: str, right: str, min_length: int) -> bool:
    if not left or not right or left == right:
        return False
    shorter = min(len(left), len(right))
    longer = max(len(left), len(right))
    if shorter < min_length:
        return False
    # Avoid broad generic fragments such as "通讯异常" matching many detailed EC FPs.
    if shorter / longer < 0.45:
        return False
    return left in right or right in left


def _group_downtime_by_rules_fp(downtime_records: list[dict[str, Any]], rules: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, record in enumerate(downtime_records):
        normalized = normalize_fp_with_rules(record.get("異常描敘"), rules)
        if not normalized:
            continue
        enriched = dict(record)
        enriched["_source_ref"] = make_source_ref("y25_downtime", record, index).as_dict()
        enriched["_normalized_fp"] = normalize_fp(record.get("異常描敘"))
        enriched["_rules_normalized_fp"] = normalized
        groups[normalized].append(enriched)
    return dict(groups)


def apply_confirmed_review_decisions_to_join(
    *,
    records: list[dict[str, Any]],
    unmatched_ec: list[dict[str, Any]],
    matched_downtime_norms: set[str],
    error_code_records: list[dict[str, Any]],
    downtime_records: list[dict[str, Any]],
    rules: dict[str, Any] | None,
    review_decisions: dict[str, Any] | None,
) -> dict[str, Any]:
    """Promote only explicit confirmed review decisions into join records.

    Review candidates can be useful for recall, but they are not diagnosis
    facts. This function is the narrow gate where a human decision can convert
    a field FP candidate into a governed EC/standard-FP link.
    """
    decisions = [decision for decision in _iter_review_decisions(review_decisions) if _decision_status(decision) == "confirmed"]
    summary: dict[str, Any] = {
        "confirmed_decision_count": len(decisions),
        "promoted_join_records": 0,
        "ignored_confirmed_decisions": [],
    }
    if not decisions:
        return summary

    ec_index: dict[str, tuple[int, dict[str, Any]]] = {
        str(record.get("Error code")): (index, record)
        for index, record in enumerate(error_code_records)
        if record.get("Error code") not in (None, "")
    }
    downtime_by_rules_norm = _group_downtime_by_rules_fp(downtime_records, rules)
    existing_pairs = {
        (str(record.get("EC")), str((record.get("match_basis") or {}).get("downtime_fp_normalized")))
        for record in records
    }
    promoted_ecs: set[str] = set()

    for decision in decisions:
        ec = str(decision.get("EC") or "")
        decision_norm = _decision_field_norm(decision, rules)
        if not ec or not decision_norm:
            summary["ignored_confirmed_decisions"].append({
                "decision_id": decision.get("decision_id"),
                "reason": "missing_ec_or_field_fp",
            })
            continue
        ec_pair = ec_index.get(ec)
        downtime_group = downtime_by_rules_norm.get(decision_norm)
        if ec_pair is None or not downtime_group:
            summary["ignored_confirmed_decisions"].append({
                "decision_id": decision.get("decision_id"),
                "reason": "ec_or_downtime_fp_not_found",
                "EC": ec,
                "field_fp_normalized": decision_norm,
            })
            continue
        if (ec, decision_norm) in existing_pairs:
            continue
        ec_record_index, ec_record = ec_pair
        records.append(build_join_record(
            ec_record=ec_record,
            ec_index=ec_record_index,
            ec_norm=normalize_fp_with_rules(ec_record.get("Description"), rules),
            downtime_norm=decision_norm,
            downtime_records=downtime_group,
            match_type="human_confirmed_review_candidate",
            review_decision=decision,
        ))
        existing_pairs.add((ec, decision_norm))
        promoted_ecs.add(ec)
        summary["promoted_join_records"] += 1
        for record in downtime_group:
            if record.get("_normalized_fp"):
                matched_downtime_norms.add(str(record["_normalized_fp"]))

    if promoted_ecs:
        unmatched_ec[:] = [record for record in unmatched_ec if str(record.get("EC")) not in promoted_ecs]
    summary["ignored_confirmed_decisions"] = summary["ignored_confirmed_decisions"][:20]
    return summary


def build_structured_fp_join(
    error_code_records: list[dict[str, Any]],
    downtime_records: list[dict[str, Any]],
    *,
    error_code_governance: dict[str, Any] | None = None,
    downtime_governance: dict[str, Any] | None = None,
    min_contains_length: int = DEFAULT_MIN_CONTAINS_LENGTH,
    generated_at: str | None = None,
    rules: dict[str, Any] | None = None,
    review_decisions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the TASK-005 EC/FP/RC/PA join payload.

    This remains a structured aggregate, not a router or GraphRAG preprocessing
    shortcut. Unmatched EC catalog rows and downtime case evidence are retained
    so downstream consumers can route them without pretending they are complete
    KG diagnosis chains.
    """
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    downtime_groups = group_downtime_by_fp(downtime_records)
    records: list[dict[str, Any]] = []
    matched_downtime_norms: set[str] = set()
    unmatched_ec: list[dict[str, Any]] = []

    for ec_index, ec_record in enumerate(error_code_records):
        ec_norm = normalize_fp(ec_record.get("Description"))
        if not ec_norm:
            unmatched_entry = {
                "EC": ec_record.get("Error code"),
                "FP": ec_record.get("Description"),
                "reason": "empty_normalized_fp",
                "source_ref": make_source_ref("error_codes_standardized", ec_record, ec_index).as_dict(),
            }
            unmatched_entry.update(build_ec_catalog_route_status(fp=unmatched_entry.get("FP"), reason="empty_normalized_fp"))
            unmatched_ec.append(unmatched_entry)
            continue

        exact = downtime_groups.get(ec_norm)
        if exact:
            records.append(build_join_record(
                ec_record=ec_record,
                ec_index=ec_index,
                ec_norm=ec_norm,
                downtime_norm=ec_norm,
                downtime_records=exact,
                match_type="normalized_exact",
            ))
            matched_downtime_norms.add(ec_norm)
            continue

        candidate_norms = [
            downtime_norm
            for downtime_norm in downtime_groups
            if _contains_match(ec_norm, downtime_norm, min_contains_length)
        ]
        if candidate_norms:
            for downtime_norm in sorted(candidate_norms):
                records.append(build_join_record(
                    ec_record=ec_record,
                    ec_index=ec_index,
                    ec_norm=ec_norm,
                    downtime_norm=downtime_norm,
                    downtime_records=downtime_groups[downtime_norm],
                    match_type="contains_candidate",
                ))
                matched_downtime_norms.add(downtime_norm)
        else:
            unmatched_entry = {
                "EC": ec_record.get("Error code"),
                "FP": ec_record.get("Description"),
                "normalized_fp": ec_norm,
                "reason": "no_downtime_fp_match",
                "source_ref": make_source_ref("error_codes_standardized", ec_record, ec_index).as_dict(),
            }
            unmatched_entry.update(build_ec_catalog_route_status(fp=unmatched_entry.get("FP"), reason="no_downtime_fp_match"))
            unmatched_ec.append(unmatched_entry)

    review_decision_summary = apply_confirmed_review_decisions_to_join(
        records=records,
        unmatched_ec=unmatched_ec,
        matched_downtime_norms=matched_downtime_norms,
        error_code_records=error_code_records,
        downtime_records=downtime_records,
        rules=rules,
        review_decisions=review_decisions,
    )

    unmatched_downtime = []
    for downtime_norm, group in sorted(downtime_groups.items()):
        if downtime_norm in matched_downtime_norms:
            continue
        field_fp_variants = _unique_non_empty([record.get("異常描敘") for record in group])
        possible_causes = _unique_non_empty([record.get("原因") for record in group])
        repair_actions = _unique_non_empty([record.get("維修動作") for record in group])
        unmatched_entry = {
            "FP": field_fp_variants,
            "field_fp_variants": field_fp_variants,
            "field_fp_source": "y25_downtime.異常描敘",
            "normalized_fp": downtime_norm,
            "reason": "no_error_code_fp_match",
            "source_refs": [record["_source_ref"] for record in group],
            "evidence": summarize_downtime(group),
        }
        unmatched_entry.update(build_case_route_status(
            field_fp_variants=field_fp_variants,
            possible_causes=possible_causes,
            repair_actions=repair_actions,
        ))
        unmatched_downtime.append(unmatched_entry)

    match_counts = Counter(record["match_type"] for record in records)
    route_status_summary = _route_status_summary(records, unmatched_ec, unmatched_downtime)
    payload = {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "field_semantics": {
                "EC": "Error Code",
                "FP": "Backward-compatible alias of standard_fp",
                "standard_fp": "Standard Fault Phenomenon from error_codes_standardized.Description",
                "field_fp_variants": "Field Fault Phenomenon surface variants from y25_downtime.異常描敘",
                "RC": "Possible Causes / candidate causes; not a verified unique root cause",
                "PA": "Repair Action; equivalent to RA in this MVP",
                "kg_diagnosis_eligible": "True only for complete, confirmed EC/FP/RC/PA diagnosis chains eligible for KG text2cypher diagnosis.",
                "chain_status": "Router-facing chain completeness/status label.",
                "route_target": "Recommended Router target such as text2cypher_diagnosis, structured_catalog, case_retrieval, or fp_review_governance.",
                "missing_chain_fields": "Fields missing from the EC/FP/RC/PA diagnosis chain.",
            },
            "input_sources": {
                "error_codes_standardized": {
                    "canonical": "data/processed/error_codes_standardized_canonical.json",
                    "governance": "data/processed/_governance/error_codes_standardized_governance.json",
                    "record_count": len(error_code_records),
                    "governance_summary": (error_code_governance or {}).get("governance"),
                },
                "y25_downtime": {
                    "canonical": "data/processed/y25_downtime_canonical.json",
                    "governance": "data/processed/_governance/y25_downtime_governance.json",
                    "record_count": len(downtime_records),
                    "governance_summary": (downtime_governance or {}).get("governance"),
                },
            },
            "rule_profile": {
                "join_key": "FP",
                "normalization": ["unicode_nfkc", "trim", "lower", "leading_number_marker_strip", "punctuation_and_whitespace_strip"],
                "match_types": ["normalized_exact", "contains_candidate", "human_confirmed_review_candidate"],
                "min_contains_length": min_contains_length,
                "no_embedding_or_llm": True,
            },
            "review_decisions": review_decision_summary,
            "summary": {
                "join_records": len(records),
                "match_counts": dict(sorted(match_counts.items())),
                "unmatched_error_code_fps": len(unmatched_ec),
                "unmatched_downtime_fps": len(unmatched_downtime),
                "matched_downtime_fp_groups": len(matched_downtime_norms),
                "total_downtime_fp_groups": len(downtime_groups),
                "kg_diagnosis_eligible_records": route_status_summary["kg_diagnosis_eligible_records"],
                "chain_status_counts": route_status_summary["chain_status_counts"],
                "route_target_counts": route_status_summary["route_target_counts"],
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
    metadata = payload.get("metadata", {})
    return {
        "schema_version": metadata.get("schema_version"),
        "generated_at": metadata.get("generated_at"),
        "field_semantics": metadata.get("field_semantics"),
        "rule_profile": metadata.get("rule_profile"),
        "summary": metadata.get("summary"),
        "sample_records": payload.get("records", [])[:sample_size],
        "sample_unmatched_error_code_fps": payload.get("unmatched", {}).get("error_code_fps", [])[:sample_size],
        "sample_unmatched_downtime_fps": payload.get("unmatched", {}).get("downtime_fps", [])[:sample_size],
    }


def load_inputs(processed_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    error_codes = load_json(processed_dir / "error_codes_standardized_canonical.json")
    downtime = load_json(processed_dir / "y25_downtime_canonical.json")
    error_gov_path = processed_dir / "_governance" / "error_codes_standardized_governance.json"
    downtime_gov_path = processed_dir / "_governance" / "y25_downtime_governance.json"
    error_gov = load_json(error_gov_path) if error_gov_path.exists() else {}
    downtime_gov = load_json(downtime_gov_path) if downtime_gov_path.exists() else {}
    return error_codes, downtime, error_gov, downtime_gov
