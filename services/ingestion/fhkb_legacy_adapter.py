"""Deterministic offline adapter for governed legacy FHKB candidates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
import re
from typing import Any

_IDENTITY_VERSION = "fhkb_case_identity_v1"
_ALLOWED_LEGACY_FIELDS = {
    "rag_candidate_id",
    "source_id",
    "source_version",
    "source_record_id",
    "source_type",
    "relation_type",
    "route_target",
    "publication_status",
    "serving_safe",
    "review_maturity",
    "field_fp_variants",
    "field_fp_normalized",
    "RC",
    "PA",
    "event_time",
    "event_time_precision",
    "timezone",
    "device_scope",
    "station_id",
    "module_id",
    "component_id",
    "subcomponent_id",
    "evidence",
    "source_refs",
    "filter_basis",
}
_BLOCKED_FIELDS = {
    "confirmed_diagnosis",
    "reviewed_mapping_record",
    "promotion_decision_id",
    "raw_work_order",
    "raw_customer_text",
    "secret",
    "credential",
    "absolute_path",
    "debug_payload",
}
_CASE_TYPE_MAP = {
    "structured_case_candidate": "structured_case_candidate",
    "field_history_case_candidate": "field_history_case_candidate",
    "field_case_without_standard_fp": "field_history_case_candidate",
    "nomic_semantic_related_candidate": "structured_case_candidate",
}


class FHKBLegacyAdapterError(ValueError):
    """Raised when a legacy candidate cannot be mapped without ambiguity."""


def adapt_fhkb_legacy_records(
    records: Sequence[Mapping[str, Any]],
    *,
    release_id: str,
    source_id: str,
    source_version: str,
    manifest_digest: str,
    lineage_ref: str,
    masking_status: str,
    producer_commit: str | None = None,
) -> dict[str, Any]:
    """Map a governed Route C legacy projection to canonical FHKB cases.

    This function performs no file I/O and does not mutate its inputs.
    """

    _require_nonempty("release_id", release_id)
    _require_nonempty("source_id", source_id)
    _require_nonempty("source_version", source_version)
    _require_nonempty("manifest_digest", manifest_digest)
    _require_nonempty("lineage_ref", lineage_ref)
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise FHKBLegacyAdapterError("records must be a sequence of mappings")

    canonical_records: list[dict[str, Any]] = []
    by_case_id: dict[str, str] = {}
    for index, legacy in enumerate(records):
        if not isinstance(legacy, Mapping):
            raise FHKBLegacyAdapterError(f"records[{index}] must be a mapping")
        canonical = _adapt_record(
            legacy,
            source_id=source_id,
            source_version=source_version,
            record_index=index,
        )
        serialized = _canonical_json(canonical)
        previous = by_case_id.get(canonical["case_id"])
        if previous is not None:
            if previous != serialized:
                raise FHKBLegacyAdapterError(
                    f"conflicting canonical content for {canonical['case_id']}"
                )
            continue
        by_case_id[canonical["case_id"]] = serialized
        canonical_records.append(canonical)

    package = {
        "schema_version": "fhkb_case_v1",
        "release_id": release_id.strip(),
        "source_id": source_id.strip(),
        "source_version": source_version.strip(),
        "manifest_digest": manifest_digest.strip(),
        "lineage_ref": lineage_ref.strip(),
        "masking_status": masking_status,
        "serving_safe": True,
        "producer_commit": producer_commit.strip() if producer_commit else None,
        "records": canonical_records,
    }
    _validate_package(package)
    return package


def _adapt_record(
    legacy: Mapping[str, Any],
    *,
    source_id: str,
    source_version: str,
    record_index: int,
) -> dict[str, Any]:
    _reject_blocked_fields(legacy, path=f"records[{record_index}]")
    unknown = set(legacy) - _ALLOWED_LEGACY_FIELDS
    if unknown:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}] contains fields outside the approved "
            f"legacy projection: {sorted(unknown)}"
        )
    if legacy.get("route_target") != "rag_case_pool":
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].route_target must be rag_case_pool"
        )
    if legacy.get("publication_status") not in (None, "candidate_only"):
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].publication_status must be candidate_only"
        )
    if legacy.get("serving_safe") is False:
        raise FHKBLegacyAdapterError(f"records[{record_index}] is not serving-safe")
    if legacy.get("source_id") not in (None, source_id):
        raise FHKBLegacyAdapterError(f"records[{record_index}].source_id conflicts")
    if legacy.get("source_version") not in (None, source_version):
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].source_version conflicts"
        )

    legacy_source_type = _nullable_text(legacy.get("source_type"))
    case_type = _CASE_TYPE_MAP.get(legacy_source_type or "")
    if case_type is None:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].source_type is not an FHKB candidate type"
        )

    source_refs = _normalize_source_refs(
        legacy.get("source_refs"),
        explicit_record_id=legacy.get("source_record_id"),
        source_id=source_id,
        source_version=source_version,
        record_index=record_index,
    )
    source_record_ids = sorted({ref["source_record_id"] for ref in source_refs})
    case_id = _case_id(source_id, source_version, source_record_ids)

    observed_texts = _text_list(
        legacy.get("field_fp_variants"),
        f"records[{record_index}].field_fp_variants",
    )
    normalized_text = _nullable_text(legacy.get("field_fp_normalized"))
    candidate_causes = _text_list(legacy.get("RC"), f"records[{record_index}].RC")
    candidate_actions = _text_list(legacy.get("PA"), f"records[{record_index}].PA")
    if not (observed_texts or normalized_text or candidate_causes or candidate_actions):
        raise FHKBLegacyAdapterError(
            f"records[{record_index}] has no approved retrieval text"
        )

    filter_basis = legacy.get("filter_basis")
    if filter_basis is None:
        filter_reason = None
    elif isinstance(filter_basis, Mapping) and set(filter_basis) <= {
        "reason",
        "not_for_kg_text2cypher",
    }:
        filter_reason = _nullable_text(filter_basis.get("reason"))
    else:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].filter_basis must contain only reason"
        )

    event_time = _nullable_text(legacy.get("event_time"))
    precision = legacy.get("event_time_precision", "unknown")
    if precision not in {"unknown", "date", "datetime", "range"}:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].event_time_precision is invalid"
        )
    review_maturity = legacy.get("review_maturity", "unreviewed")
    if review_maturity not in {"unreviewed", "source_reviewed", "domain_reviewed"}:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].review_maturity is invalid"
        )
    not_for_kg = (
        filter_basis.get("not_for_kg_text2cypher")
        if isinstance(filter_basis, Mapping)
        else None
    )
    if not_for_kg is not None and not isinstance(not_for_kg, bool):
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].filter_basis.not_for_kg_text2cypher "
            "must be boolean or null"
        )

    return {
        "case_id": case_id,
        "case_version": 1,
        "derivation_rule_version": _IDENTITY_VERSION,
        "source_id": source_id,
        "source_version": source_version,
        "source_record_ids": source_record_ids,
        "source_refs": source_refs,
        "case_type": case_type,
        "case_status": "candidate",
        "publication_status": "candidate_only",
        "route_target": "rag_case_pool",
        "serving_safe": True,
        "review_maturity": review_maturity,
        "phenomenon": {
            "observed_texts": observed_texts,
            "normalized_text": normalized_text,
        },
        "candidate_causes": candidate_causes,
        "candidate_actions": candidate_actions,
        "temporal_context": {
            "event_time": event_time,
            "precision": precision,
            "timezone": _nullable_text(legacy.get("timezone")),
        },
        "equipment_context": {
            "device_scope": _nullable_text(legacy.get("device_scope")),
            "station_id": _nullable_text(legacy.get("station_id")),
            "module_id": _nullable_text(legacy.get("module_id")),
            "component_id": _nullable_text(legacy.get("component_id")),
            "subcomponent_id": _nullable_text(legacy.get("subcomponent_id")),
        },
        "evidence_summary": _evidence_summary(
            legacy.get("evidence"), record_index=record_index
        ),
        "field_authority": {
            "phenomenon_observed": "source_observed",
            "phenomenon_normalized": "normalized_candidate",
            "candidate_causes": "historical_candidate",
            "candidate_actions": "historical_candidate",
            "temporal_context": "source_observed_or_normalized",
            "equipment_context": "source_observed_or_normalized",
            "evidence_summary": "source_aggregate",
        },
        "legacy_context": {
            "legacy_source_type": legacy_source_type,
            "relation_type": _nullable_text(legacy.get("relation_type")),
            "filter_basis_reason": filter_reason,
            "not_for_kg_text2cypher": not_for_kg,
        },
        "warnings": [],
    }


def _normalize_source_refs(
    value: Any,
    *,
    explicit_record_id: Any,
    source_id: str,
    source_version: str,
    record_index: int,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].source_refs must be a non-empty list"
        )
    refs: list[dict[str, Any]] = []
    explicit = _nullable_text(explicit_record_id)
    for ref_index, raw_ref in enumerate(value):
        if not isinstance(raw_ref, Mapping):
            raise FHKBLegacyAdapterError(
                f"records[{record_index}].source_refs[{ref_index}] must be a mapping"
            )
        canonical_fields = {
            "source_id",
            "source_version",
            "source_record_id",
            "anchor",
        }
        legacy_fields = {
            "source",
            "record_index",
            "record_number",
            "record_id_field",
            "record_id_value",
        }
        ref_fields = set(raw_ref)
        if ref_fields <= canonical_fields:
            ref_source_id = _nullable_text(raw_ref.get("source_id")) or source_id
            ref_source_version = (
                _nullable_text(raw_ref.get("source_version")) or source_version
            )
            record_id = _nullable_text(raw_ref.get("source_record_id")) or explicit
            if record_id is None:
                raise FHKBLegacyAdapterError(
                    f"records[{record_index}].source_refs[{ref_index}] lacks "
                    "source_record_id"
                )
            refs.append(
                {
                    "source_id": ref_source_id,
                    "source_version": ref_source_version,
                    "source_record_id": record_id,
                    "anchor": _nullable_text(raw_ref.get("anchor")),
                    "legacy_source": None,
                    "legacy_record_index": None,
                    "legacy_record_number": None,
                    "legacy_record_id_field": None,
                    "legacy_record_id_value": None,
                }
            )
            continue
        if not ref_fields <= legacy_fields:
            raise FHKBLegacyAdapterError(
                f"records[{record_index}].source_refs[{ref_index}] has "
                f"unsupported fields: {sorted(ref_fields - legacy_fields)}"
            )
        legacy_source = _nullable_text(raw_ref.get("source"))
        legacy_index = raw_ref.get("record_index")
        legacy_number = raw_ref.get("record_number")
        if legacy_source is None:
            raise FHKBLegacyAdapterError(
                f"records[{record_index}].source_refs[{ref_index}] lacks source"
            )
        if isinstance(legacy_index, bool) or not isinstance(legacy_index, int) or legacy_index < 0:
            raise FHKBLegacyAdapterError(
                f"records[{record_index}].source_refs[{ref_index}] has invalid record_index"
            )
        if isinstance(legacy_number, bool) or not isinstance(legacy_number, int) or legacy_number < 1:
            raise FHKBLegacyAdapterError(
                f"records[{record_index}].source_refs[{ref_index}] has invalid record_number"
            )
        legacy_id_field = _nullable_text(raw_ref.get("record_id_field"))
        legacy_id_value = raw_ref.get("record_id_value")
        if not isinstance(legacy_id_value, (str, int, float, bool, type(None))):
            raise FHKBLegacyAdapterError(
                f"records[{record_index}].source_refs[{ref_index}] has unsupported record_id_value"
            )
        identity_material = {
            "source": legacy_source,
            "record_index": legacy_index,
            "record_number": legacy_number,
            "record_id_field": legacy_id_field,
            "record_id_value": legacy_id_value,
        }
        record_id = "FHS_" + hashlib.sha256(
            _canonical_json(identity_material).encode("utf-8")
        ).hexdigest()
        refs.append(
            {
                "source_id": source_id,
                "source_version": source_version,
                "source_record_id": record_id,
                "anchor": f"{legacy_source}:record:{legacy_number}",
                "legacy_source": legacy_source,
                "legacy_record_index": legacy_index,
                "legacy_record_number": legacy_number,
                "legacy_record_id_field": legacy_id_field,
                "legacy_record_id_value": legacy_id_value,
            }
        )
    return refs


def _evidence_summary(value: Any, *, record_index: int) -> dict[str, Any] | None:
    if value in (None, {}):
        return None
    if not isinstance(value, Mapping):
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].evidence must be a mapping or null"
        )
    allowed = {
        "count",
        "event_count",
        "total_dt_mins",
        "risk_counts",
        "status_counts",
        "qpl_values",
        "date_range",
    }
    unknown = set(value) - allowed
    if unknown:
        raise FHKBLegacyAdapterError(
            f"records[{record_index}].evidence has unsupported fields: "
            f"{sorted(unknown)}"
        )
    count = value.get("event_count", value.get("count"))
    _require_optional_number(count, integer=True, path="evidence.event_count")
    total_dt = value.get("total_dt_mins")
    _require_optional_number(total_dt, integer=False, path="evidence.total_dt_mins")
    risk_counts = _count_map(value.get("risk_counts"), "evidence.risk_counts")
    status_counts = _count_map(value.get("status_counts"), "evidence.status_counts")
    qpl_values = value.get("qpl_values", [])
    if qpl_values is None:
        qpl_values = []
    if not isinstance(qpl_values, list):
        raise FHKBLegacyAdapterError("evidence.qpl_values must be a list")
    date_range = _date_range(value.get("date_range"))
    return {
        "event_count": count,
        "total_dt_mins": total_dt,
        "risk_counts": risk_counts,
        "status_counts": status_counts,
        "qpl_values": list(qpl_values),
        "date_range": date_range,
    }


def _count_map(value: Any, path: str) -> dict[str, int]:
    if value in (None, {}):
        return {}
    if not isinstance(value, Mapping):
        raise FHKBLegacyAdapterError(f"{path} must be a mapping")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key.strip():
            raise FHKBLegacyAdapterError(f"{path} contains an invalid key")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise FHKBLegacyAdapterError(f"{path}.{key} must be a non-negative integer")
        result[key.strip()] = count
    return result


def _date_range(value: Any) -> dict[str, str | None]:
    if value in (None, {}, []):
        return {"start": None, "end": None}
    if isinstance(value, Mapping) and set(value) <= {"start", "end"}:
        return {
            "start": _nullable_text(value.get("start")),
            "end": _nullable_text(value.get("end")),
        }
    if isinstance(value, Mapping) and set(value) <= {"min", "max"}:
        return {
            "start": _nullable_text(value.get("min")),
            "end": _nullable_text(value.get("max")),
        }
    if isinstance(value, list) and len(value) == 2:
        return {"start": _nullable_text(value[0]), "end": _nullable_text(value[1])}
    raise FHKBLegacyAdapterError(
        "evidence.date_range must be {start, end}, {min, max}, a two-item list, or null"
    )


def _case_id(source_id: str, source_version: str, record_ids: list[str]) -> str:
    material = [_IDENTITY_VERSION, source_id, source_version, record_ids]
    return "FHC_" + hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _text_list(value: Any, path: str) -> list[str]:
    if value in (None, "", []):
        return []
    raw_values = value if isinstance(value, list) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        if not isinstance(item, (str, int, float)) or isinstance(item, bool):
            raise FHKBLegacyAdapterError(f"{path} contains unsupported text")
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise FHKBLegacyAdapterError("expected a scalar text value or null")
    text = str(value).strip()
    return text or None


def _require_optional_number(
    value: Any, *, integer: bool, path: str
) -> None:
    if value is None:
        return
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected) or value < 0:
        kind = "integer" if integer else "number"
        raise FHKBLegacyAdapterError(f"{path} must be a non-negative {kind} or null")


def _reject_blocked_fields(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in _BLOCKED_FIELDS:
                raise FHKBLegacyAdapterError(f"{path}.{key} is blocked")
            _reject_blocked_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_blocked_fields(child, path=f"{path}[{index}]")


def _require_nonempty(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FHKBLegacyAdapterError(f"{name} must be a non-empty string")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_package(package: Mapping[str, Any]) -> None:
    if package.get("schema_version") != "fhkb_case_v1":
        raise FHKBLegacyAdapterError("canonical FHKB schema_version is invalid")
    if package.get("serving_safe") is not True:
        raise FHKBLegacyAdapterError("canonical FHKB package is not serving-safe")
    digest = package.get("manifest_digest")
    if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        raise FHKBLegacyAdapterError("manifest_digest must be sha256 plus 64 lowercase hex characters")
    if package.get("masking_status") not in {
        "masked",
        "not_required",
        "reviewed_masked",
    }:
        raise FHKBLegacyAdapterError("masking_status is invalid")
    records = package.get("records")
    if not isinstance(records, list) or not records:
        raise FHKBLegacyAdapterError("canonical FHKB package must contain records")
