from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "configs" / "route_c_source_boundary_v1.json"


@lru_cache(maxsize=1)
def load_route_c_source_boundary() -> dict[str, Any]:
    with _CONTRACT_PATH.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("Route C source boundary contract must be a JSON object.")
    return payload


def route_c_contract_version() -> str:
    return str(load_route_c_source_boundary().get("schema_version", "unknown"))


def route_c_policy() -> dict[str, Any]:
    policy = load_route_c_source_boundary().get("policy", {})
    return dict(policy) if isinstance(policy, Mapping) else {}


def route_c_source_entry(source_id: str) -> dict[str, Any] | None:
    sources = load_route_c_source_boundary().get("sources", {})
    if not isinstance(sources, Mapping):
        return None
    entry = sources.get(source_id)
    return dict(entry) if isinstance(entry, Mapping) else None


def allowed_route_c_sources() -> tuple[str, ...]:
    sources = load_route_c_source_boundary().get("sources", {})
    if not isinstance(sources, Mapping):
        return ()
    return tuple(str(source_id) for source_id in sources.keys())


def blocked_route_c_material() -> dict[str, str]:
    blocked = load_route_c_source_boundary().get("blocked_material", {})
    if not isinstance(blocked, Mapping):
        return {}
    return {str(key): str(value) for key, value in blocked.items()}


def route_c_target_for_source(source_id: str) -> str | None:
    entry = route_c_source_entry(source_id)
    if not entry:
        return None
    mapping = entry.get("route_target_mapping", {})
    if not isinstance(mapping, Mapping):
        return None
    value = mapping.get("route_target")
    return str(value) if value not in (None, "") else None


def route_c_route_marker(source_id: str) -> dict[str, str | None]:
    entry = route_c_source_entry(source_id)
    if not entry:
        return {"route_marker_field": None, "route_marker_value": None}
    mapping = entry.get("route_target_mapping", {})
    if not isinstance(mapping, Mapping):
        return {"route_marker_field": None, "route_marker_value": None}
    field = mapping.get("route_marker_field")
    value = mapping.get("route_marker_value")
    return {
        "route_marker_field": str(field) if field not in (None, "") else None,
        "route_marker_value": str(value) if value not in (None, "") else None,
    }


def allowed_fields_for_source(source_id: str) -> tuple[str, ...]:
    entry = route_c_source_entry(source_id)
    if not entry:
        return ()
    allowlist = entry.get("field_allowlist", ())
    if not isinstance(allowlist, list):
        return ()
    return tuple(str(field) for field in allowlist)


def publication_status_for_source(source_id: str) -> str | None:
    entry = route_c_source_entry(source_id)
    if not entry:
        return None
    status = entry.get("publication_status")
    return str(status) if status not in (None, "") else None


def route_c_source_metadata(source_id: str) -> dict[str, Any]:
    entry = route_c_source_entry(source_id)
    if not entry:
        return {}
    return {
        "contract_scope": route_c_contract_version(),
        "publication_status": publication_status_for_source(source_id),
        "route_target": route_c_target_for_source(source_id),
        "field_allowlist": list(allowed_fields_for_source(source_id)),
        "promotion_rules": dict(entry.get("promotion_rules", {}))
        if isinstance(entry.get("promotion_rules"), Mapping)
        else {},
    }


def project_route_c_record(source_id: str, record: Mapping[str, Any]) -> dict[str, Any]:
    projection: dict[str, Any] = {}
    for field_path in allowed_fields_for_source(source_id):
        _copy_allowed_field(projection, record, field_path)
    return projection


def _copy_allowed_field(target: dict[str, Any], record: Mapping[str, Any], field_path: str) -> None:
    parts = field_path.split(".")
    current: Any = record
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return
        current = current[part]
    _write_nested_value(target, parts, current)


def _write_nested_value(target: dict[str, Any], parts: list[str], value: Any) -> None:
    cursor = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value
