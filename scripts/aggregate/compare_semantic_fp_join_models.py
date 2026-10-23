"""Compare two TASK-005 v1 semantic FP join model outputs.

The comparison is intentionally review-oriented: aggregate metrics are useful,
but the final model choice should be based on a small human-labeled sample of
where the models agree, disagree, or produce model-only candidates.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.aggregation.structured_fp_join import write_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare semantic FP join model outputs.")
    parser.add_argument("--aggregates-dir", default=str(PROJECT_ROOT / "data" / "processed" / "aggregates"))
    parser.add_argument("--left-name", default="nomic")
    parser.add_argument("--left-file", default="structured_fp_join_v1_semantic.json")
    parser.add_argument("--right-name", default="bge_m3")
    parser.add_argument("--right-file", default="structured_fp_join_v1_semantic_bge_m3.json")
    parser.add_argument("--output-file", default="structured_fp_join_v1_model_compare_nomic_vs_bge_m3.json")
    parser.add_argument("--review-pack-file", default="structured_fp_join_v1_model_compare_review_pack.json")
    parser.add_argument("--sample-size-per-category", type=int, default=12)
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    aggregates_dir = Path(args.aggregates_dir)
    left_path = _resolve_path(aggregates_dir, args.left_file)
    right_path = _resolve_path(aggregates_dir, args.right_file)
    left_payload = load_json(left_path)
    right_payload = load_json(right_path)

    comparison = build_comparison(
        left_payload,
        right_payload,
        left_name=args.left_name,
        right_name=args.right_name,
        left_path=left_path,
        right_path=right_path,
        sample_size=args.sample_size_per_category,
    )
    review_pack = build_review_pack(comparison)

    output_path = _resolve_path(aggregates_dir, args.output_file)
    review_pack_path = _resolve_path(aggregates_dir, args.review_pack_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, comparison, pretty=not args.compact)
    write_json(review_pack_path, review_pack, pretty=not args.compact)

    summary = comparison["summary"]
    print("TASK-005 v1 semantic model comparison")
    print(f"  {args.left_name} candidates: {summary['models'][args.left_name]['candidate_records']}")
    print(f"  {args.right_name} candidates: {summary['models'][args.right_name]['candidate_records']}")
    print(f"  overlap candidate pairs: {summary['candidate_pair_overlap']['both']}")
    print(f"  {args.left_name}-only candidate pairs: {summary['candidate_pair_overlap']['left_only']}")
    print(f"  {args.right_name}-only candidate pairs: {summary['candidate_pair_overlap']['right_only']}")
    print(f"  top1 same field FP agreement: {summary['top1_by_field_fp']['same_top1']}")
    print(f"  top1 same field FP disagreement: {summary['top1_by_field_fp']['different_top1']}")
    print(f"Wrote comparison: {output_path}")
    print(f"Wrote review pack: {review_pack_path}")


def _resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return base_dir / path


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def build_comparison(
    left_payload: dict[str, Any],
    right_payload: dict[str, Any],
    *,
    left_name: str,
    right_name: str,
    left_path: Path,
    right_path: Path,
    sample_size: int,
) -> dict[str, Any]:
    left_records = list(left_payload.get("records") or [])
    right_records = list(right_payload.get("records") or [])
    left_by_pair = {_candidate_pair_key(record): record for record in left_records}
    right_by_pair = {_candidate_pair_key(record): record for record in right_records}
    left_pairs = set(left_by_pair)
    right_pairs = set(right_by_pair)

    left_top1 = _top1_by_field_fp(left_records)
    right_top1 = _top1_by_field_fp(right_records)
    shared_field_fps = set(left_top1) & set(right_top1)
    same_top1 = [
        field_fp
        for field_fp in shared_field_fps
        if _candidate_pair_key(left_top1[field_fp]) == _candidate_pair_key(right_top1[field_fp])
    ]
    different_top1 = sorted(set(shared_field_fps) - set(same_top1))

    samples = {
        "both_agree": _sample_both(
            left_by_pair,
            right_by_pair,
            sorted(left_pairs & right_pairs),
            left_name=left_name,
            right_name=right_name,
            limit=sample_size,
        ),
        f"{left_name}_only": _sample_one_sided(
            [left_by_pair[key] for key in sorted(left_pairs - right_pairs)],
            model_name=left_name,
            limit=sample_size,
        ),
        f"{right_name}_only": _sample_one_sided(
            [right_by_pair[key] for key in sorted(right_pairs - left_pairs)],
            model_name=right_name,
            limit=sample_size,
        ),
        "top1_disagree": _sample_top1_disagree(
            different_top1,
            left_top1,
            right_top1,
            left_name=left_name,
            right_name=right_name,
            limit=sample_size,
        ),
        f"{left_name}_high_score_no_shared_features": _sample_one_sided(
            [record for record in left_records if _has_no_shared_features(record)],
            model_name=left_name,
            limit=sample_size,
        ),
    }

    return {
        "schema_version": "structured_fp_join_v1_semantic_model_compare",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "purpose": "Compare two semantic FP join outputs before choosing the TASK-005 v1 baseline model.",
            "left": {
                "name": left_name,
                "path": str(left_path),
                "provider": (left_payload.get("metadata") or {}).get("provider"),
                "candidate_generation": (left_payload.get("metadata") or {}).get("candidate_generation"),
            },
            "right": {
                "name": right_name,
                "path": str(right_path),
                "provider": (right_payload.get("metadata") or {}).get("provider"),
                "candidate_generation": (right_payload.get("metadata") or {}).get("candidate_generation"),
            },
            "human_review_guidance": {
                "recommended_labels": ["prefer_left", "prefer_right", "both_valid", "neither", "needs_more_context"],
                "decision_rule": "Use this file to choose a default model only after reviewing sampled disagreements and model-only candidates.",
            },
        },
        "summary": {
            "models": {
                left_name: _model_metrics(left_payload),
                right_name: _model_metrics(right_payload),
            },
            "candidate_pair_overlap": {
                "both": len(left_pairs & right_pairs),
                "left_only": len(left_pairs - right_pairs),
                "right_only": len(right_pairs - left_pairs),
                "left_only_ratio": _safe_ratio(len(left_pairs - right_pairs), len(left_pairs)),
                "right_only_ratio": _safe_ratio(len(right_pairs - left_pairs), len(right_pairs)),
            },
            "top1_by_field_fp": {
                "left_field_fp_count": len(left_top1),
                "right_field_fp_count": len(right_top1),
                "shared_field_fp_count": len(shared_field_fps),
                "same_top1": len(same_top1),
                "different_top1": len(different_top1),
                "left_only_field_fp_count": len(set(left_top1) - set(right_top1)),
                "right_only_field_fp_count": len(set(right_top1) - set(left_top1)),
                "agreement_ratio_on_shared_field_fps": _safe_ratio(len(same_top1), len(shared_field_fps)),
            },
        },
        "samples": samples,
    }


def build_review_pack(comparison: dict[str, Any]) -> dict[str, Any]:
    """Create a blank human-labeling pack for model selection.

    The pack is evidence for choosing a baseline model; it is not a governed
    mapping source and should not be imported as confirmed FP links.
    """
    items: list[dict[str, Any]] = []
    for category, samples in (comparison.get("samples") or {}).items():
        for sample in samples:
            item = dict(sample)
            item["review_decision"] = ""
            item["reviewer_note"] = ""
            item["allowed_review_decisions"] = ["prefer_left", "prefer_right", "both_valid", "neither", "needs_more_context"]
            item["review_question"] = "Which model candidate is more correct for this field FP?"
            item["review_item_id"] = f"CMP-{len(items) + 1:04d}"
            item["category"] = category
            items.append(item)
    return {
        "schema_version": "structured_fp_join_v1_semantic_model_review_pack",
        "generated_at": comparison.get("generated_at"),
        "metadata": {
            "source_compare_schema_version": comparison.get("schema_version"),
            "purpose": "Small human review pack for selecting the TASK-005 v1 semantic baseline model.",
            "review_workflow": "Fill review_decision and reviewer_note for a small subset, then choose the baseline model by precision/recall tradeoff.",
        },
        "summary": {
            "review_item_count": len(items),
            "category_counts": dict(Counter(item["category"] for item in items)),
        },
        "review_items": items,
    }


def _model_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    records = list(payload.get("records") or [])
    metadata_summary = (payload.get("metadata") or {}).get("summary") or {}
    field_fps = {_field_fp_normalized(record) for record in records if _field_fp_normalized(record)}
    standard_fps = {_standard_fp_normalized(record) for record in records if _standard_fp_normalized(record)}
    error_codes = {str(record.get("EC")) for record in records if record.get("EC")}
    rank_counts = Counter(str(record.get("semantic_rank")) for record in records)
    candidate_counts_by_field_fp = Counter(_field_fp_normalized(record) for record in records if _field_fp_normalized(record))
    any_shared = sum(1 for record in records if not _has_no_shared_features(record))
    no_shared = sum(1 for record in records if _has_no_shared_features(record))
    return {
        "candidate_records": len(records),
        "downtime_fp_groups_with_candidates": metadata_summary.get("downtime_fp_groups_with_candidates", len(field_fps)),
        "total_downtime_fp_groups": metadata_summary.get("total_downtime_fp_groups"),
        "error_codes_with_candidates": metadata_summary.get("error_codes_with_candidates", len(error_codes)),
        "total_error_codes": metadata_summary.get("total_error_codes"),
        "unmatched_downtime_fp_groups": metadata_summary.get("unmatched_downtime_fp_groups"),
        "unmatched_error_codes": metadata_summary.get("unmatched_error_codes"),
        "standard_fps_with_candidates": len(standard_fps),
        "records_with_any_shared_features": any_shared,
        "records_with_no_shared_features": no_shared,
        "no_shared_feature_ratio": _safe_ratio(no_shared, len(records)),
        "semantic_score_stats": _score_stats([record.get("semantic_score") for record in records]),
        "embedding_similarity_stats": _score_stats([record.get("embedding_similarity") for record in records]),
        "feature_similarity_stats": _score_stats([record.get("feature_similarity") for record in records]),
        "semantic_rank_counts": dict(sorted(rank_counts.items())),
        "candidate_count_per_field_fp": dict(sorted(Counter(candidate_counts_by_field_fp.values()).items())),
    }


def _sample_both(
    left_by_pair: dict[tuple[str, str, str], dict[str, Any]],
    right_by_pair: dict[tuple[str, str, str], dict[str, Any]],
    keys: list[tuple[str, str, str]],
    *,
    left_name: str,
    right_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    scored = sorted(
        keys,
        key=lambda key: (
            -((_score(left_by_pair[key]) + _score(right_by_pair[key])) / 2),
            _field_fp_normalized(left_by_pair[key]),
            str(left_by_pair[key].get("EC")),
        ),
    )
    samples = []
    seen_field_fps: set[str] = set()
    for key in scored:
        left_record = left_by_pair[key]
        field_fp = _field_fp_normalized(left_record)
        if field_fp in seen_field_fps:
            continue
        seen_field_fps.add(field_fp)
        samples.append({
            "field_fp_normalized": field_fp,
            "field_fp_variants": left_record.get("field_fp_variants"),
            "candidate_pair_status": "present_in_both_models",
            "left_model": left_name,
            "right_model": right_name,
            "left_candidate": _compact_candidate(left_record),
            "right_candidate": _compact_candidate(right_by_pair[key]),
        })
        if len(samples) >= limit:
            break
    return samples


def _sample_one_sided(records: list[dict[str, Any]], *, model_name: str, limit: int) -> list[dict[str, Any]]:
    sorted_records = sorted(
        records,
        key=lambda record: (
            _has_no_shared_features(record),
            -_score(record),
            _field_fp_normalized(record),
            str(record.get("EC")),
        ),
    )
    samples = []
    seen_field_fps: set[str] = set()
    for record in sorted_records:
        field_fp = _field_fp_normalized(record)
        if field_fp in seen_field_fps:
            continue
        seen_field_fps.add(field_fp)
        samples.append({
            "field_fp_normalized": field_fp,
            "field_fp_variants": record.get("field_fp_variants"),
            "candidate_pair_status": "present_in_one_model_only",
            "model": model_name,
            "candidate": _compact_candidate(record),
        })
        if len(samples) >= limit:
            break
    return samples


def _sample_top1_disagree(
    field_fps: list[str],
    left_top1: dict[str, dict[str, Any]],
    right_top1: dict[str, dict[str, Any]],
    *,
    left_name: str,
    right_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    sorted_field_fps = sorted(
        field_fps,
        key=lambda field_fp: (
            -max(_score(left_top1[field_fp]), _score(right_top1[field_fp])),
            field_fp,
        ),
    )
    samples = []
    for field_fp in sorted_field_fps[:limit]:
        left_record = left_top1[field_fp]
        right_record = right_top1[field_fp]
        samples.append({
            "field_fp_normalized": field_fp,
            "field_fp_variants": left_record.get("field_fp_variants") or right_record.get("field_fp_variants"),
            "candidate_pair_status": "top1_disagreement_for_same_field_fp",
            "left_model": left_name,
            "right_model": right_name,
            "left_top1_candidate": _compact_candidate(left_record),
            "right_top1_candidate": _compact_candidate(right_record),
        })
    return samples


def _compact_candidate(record: dict[str, Any]) -> dict[str, Any]:
    evidence = record.get("evidence") or {}
    match_basis = record.get("match_basis") or {}
    return {
        "EC": record.get("EC"),
        "standard_fp": record.get("standard_fp"),
        "standard_fp_normalized": match_basis.get("standard_fp_normalized"),
        "semantic_rank": record.get("semantic_rank"),
        "semantic_score": record.get("semantic_score"),
        "embedding_similarity": record.get("embedding_similarity"),
        "feature_similarity": record.get("feature_similarity"),
        "shared_features": match_basis.get("shared_features"),
        "review_status": record.get("review_status"),
        "route_target": record.get("route_target"),
        "evidence_count": evidence.get("count"),
        "total_dt_mins": evidence.get("total_dt_mins"),
        "RC": record.get("RC"),
        "PA": record.get("PA"),
    }


def _top1_by_field_fp(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        field_fp = _field_fp_normalized(record)
        if field_fp:
            grouped[field_fp].append(record)
    result = {}
    for field_fp, group in grouped.items():
        result[field_fp] = sorted(group, key=lambda record: (int(record.get("semantic_rank") or 999), -_score(record), str(record.get("EC"))))[0]
    return result


def _candidate_pair_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("EC") or ""),
        _standard_fp_normalized(record),
        _field_fp_normalized(record),
    )


def _field_fp_normalized(record: dict[str, Any]) -> str:
    return str(((record.get("match_basis") or {}).get("field_fp_normalized") or "")).strip()


def _standard_fp_normalized(record: dict[str, Any]) -> str:
    return str(((record.get("match_basis") or {}).get("standard_fp_normalized") or "")).strip()


def _has_no_shared_features(record: dict[str, Any]) -> bool:
    shared = ((record.get("match_basis") or {}).get("shared_features") or {})
    return not any(shared.get(key) for key in ("modules", "axes", "components", "fault_modes"))


def _score(record: dict[str, Any]) -> float:
    return float(record.get("semantic_score") or 0.0)


def _score_stats(values: list[Any]) -> dict[str, float | int | None]:
    numeric = sorted(float(value) for value in values if value is not None)
    if not numeric:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    return {
        "count": len(numeric),
        "min": round(numeric[0], 6),
        "p25": round(_percentile(numeric, 0.25), 6),
        "median": round(_percentile(numeric, 0.50), 6),
        "p75": round(_percentile(numeric, 0.75), 6),
        "max": round(numeric[-1], 6),
    }


def _percentile(values: list[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, 6)


if __name__ == "__main__":
    main()
