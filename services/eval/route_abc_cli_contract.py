"""Shared path contract for the Route A/B/C CLI smoke harness.

This module only exposes local debug/smoke paths. UI and API code should
consume service-layer functions or result-design JSON, not this CLI harness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "configs" / "route_abc_cli_contract_v1.json"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid Route ABC CLI contract manifest: {path}")
    return payload


def repo_path(relative_path: str | Path) -> Path:
    path = Path(relative_path)
    return path if path.is_absolute() else REPO_ROOT / path


def route_config(route: str, manifest: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    payload = manifest or ROUTE_ABC_CLI_CONTRACT
    routes = payload.get("routes", {})
    if not isinstance(routes, Mapping) or route not in routes:
        raise KeyError(f"Unknown Route ABC CLI route: {route}")
    config = routes[route]
    if not isinstance(config, Mapping):
        raise ValueError(f"Invalid Route ABC CLI route config: {route}")
    return config


def route_default_sources(route: str) -> tuple[str, ...]:
    config = route_config(route)
    value = config.get("default_available_sources", ())
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _named_path_map(kind: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    routes = ROUTE_ABC_CLI_CONTRACT.get("routes", {})
    if not isinstance(routes, Mapping):
        return paths
    for config in routes.values():
        if not isinstance(config, Mapping):
            continue
        spec = config.get(kind)
        if not isinstance(spec, Mapping):
            continue
        name = str(spec.get("name") or "")
        path = str(spec.get("path") or "")
        if name and path:
            paths[name] = repo_path(path)
    return paths


def _route_to_named_path(kind: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    routes = ROUTE_ABC_CLI_CONTRACT.get("routes", {})
    if not isinstance(routes, Mapping):
        return mapping
    for route, config in routes.items():
        if not isinstance(config, Mapping):
            continue
        spec = config.get(kind)
        if not isinstance(spec, Mapping):
            continue
        name = str(spec.get("name") or "")
        if name:
            mapping[str(route)] = name
    return mapping


ROUTE_ABC_CLI_CONTRACT = load_manifest()
DEFAULT_JSON_OUTPUT_PATH = repo_path(str(ROUTE_ABC_CLI_CONTRACT["default_outputs"]["json"]))
FIXTURE_PATHS = _named_path_map("fixture")
QUERY_BANK_PATHS = _named_path_map("query_bank")
ROUTE_TO_FIXTURE = _route_to_named_path("fixture")
ROUTE_TO_QUERY_BANK = _route_to_named_path("query_bank")
