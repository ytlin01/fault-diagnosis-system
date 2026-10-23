"""Contract-valid, idempotent import boundary for Schema 4.2 candidates.

The boundary prepares graph operations and an in-memory application helper. It
does not connect to Neo4j or mutate a runtime graph.  A production importer can
consume the plan only after its own activation and rollback gates are approved.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping

from services.governance.tpdx_schema_v4_2 import (
    SchemaV42SemanticError,
    validate_v4_2_semantics,
)
from services.ingestion.tpdx_schema_v4_2_migration import canonical_json_bytes


class GraphImportError(ValueError):
    """Raised when a candidate cannot be safely prepared for import."""


@dataclass(frozen=True)
class ImportPlan:
    """Idempotent graph operations after validation and conflict checks."""

    nodes_to_create: tuple[dict[str, Any], ...]
    edges_to_create: tuple[dict[str, Any], ...]
    nodes_already_present: int
    edges_already_present: int

    @property
    def operation_count(self) -> int:
        return len(self.nodes_to_create) + len(self.edges_to_create)


def _canonical(value: Any) -> bytes:
    return canonical_json_bytes(value)


def _edge_identity(edge: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(edge.get("type")), str(edge.get("from")), str(edge.get("to")))


def _edge_storage_key(edge: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (*_edge_identity(edge), _assertion_id(edge) or "")


def _assertion_id(edge: Mapping[str, Any]) -> str | None:
    value = edge.get("properties", {}).get("assertion_edge_id")
    return value if isinstance(value, str) else None


def validate_candidate(
    candidate: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> None:
    """Validate one frozen Schema 4.2 candidate and its semantic graph rules."""

    if schema.get("$id") != "tpdx_kg_schema_v4_2":
        raise GraphImportError("import schema must be tpdx_kg_schema_v4_2")
    if schema.get("x-contract-status") != "FROZEN":
        raise GraphImportError("import requires the FROZEN Schema 4.2 contract")
    if candidate.get("schema_version") != "4.2":
        raise GraphImportError("candidate must declare Schema 4.2")
    if any(edge.get("type") == "HAS_STEP" for edge in candidate.get("edges", ())):
        raise GraphImportError("candidate cannot publish HAS_STEP alongside HAS_STEPS")
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise GraphImportError("jsonschema is required for the import boundary") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(candidate), key=str)
    if errors:
        raise GraphImportError("candidate failed JSON Schema validation: " + str(errors[0]))
    try:
        validate_v4_2_semantics(candidate)
    except SchemaV42SemanticError as exc:
        raise GraphImportError(f"candidate failed semantic validation: {exc}") from exc


def build_import_plan(
    candidate: Mapping[str, Any],
    *,
    schema: Mapping[str, Any],
    existing_nodes: Iterable[Mapping[str, Any]] = (),
    existing_edges: Iterable[Mapping[str, Any]] = (),
) -> ImportPlan:
    """Build an idempotent plan without overwriting independent assertions."""

    validate_candidate(candidate, schema)
    existing_nodes = list(existing_nodes)
    current_nodes = {str(node["id"]): node for node in existing_nodes}
    if len(current_nodes) != len(existing_nodes):
        raise GraphImportError("existing graph contains duplicate node IDs")
    current_edges = list(existing_edges)
    exact_edges = {_canonical(edge): edge for edge in current_edges}
    identity_edges: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for edge in current_edges:
        identity_edges.setdefault(_edge_identity(edge), []).append(edge)

    nodes_to_create: list[dict[str, Any]] = []
    nodes_already_present = 0
    for node in candidate.get("nodes", []):
        node_id = str(node["id"])
        existing = current_nodes.get(node_id)
        if existing is None:
            nodes_to_create.append(copy.deepcopy(dict(node)))
        elif _canonical(existing) == _canonical(node):
            nodes_already_present += 1
        else:
            raise GraphImportError(f"node ID conflict for {node_id}")

    edges_to_create: list[dict[str, Any]] = []
    edges_already_present = 0
    seen_candidate_edges: set[bytes] = set()
    for edge in candidate.get("edges", []):
        canonical_edge = _canonical(edge)
        if canonical_edge in seen_candidate_edges:
            raise GraphImportError("candidate contains duplicate edge payloads")
        seen_candidate_edges.add(canonical_edge)
        if canonical_edge in exact_edges:
            edges_already_present += 1
            continue
        identity = _edge_identity(edge)
        for existing in identity_edges.get(identity, []):
            if _assertion_id(edge) or _assertion_id(existing):
                incoming_mapping = edge.get("properties", {}).get("mapping_record_id")
                existing_mapping = existing.get("properties", {}).get("mapping_record_id")
                if incoming_mapping != existing_mapping:
                    raise GraphImportError(
                        "independent MappingRecord-backed assertions share an endpoint pair"
                    )
            raise GraphImportError(
                f"edge conflict for {identity[0]} {identity[1]}->{identity[2]}"
            )
        edges_to_create.append(copy.deepcopy(dict(edge)))

    nodes_to_create.sort(key=lambda node: (str(node.get("label")), str(node.get("id"))))
    edges_to_create.sort(key=lambda edge: _canonical(edge))
    return ImportPlan(
        nodes_to_create=tuple(nodes_to_create),
        edges_to_create=tuple(edges_to_create),
        nodes_already_present=nodes_already_present,
        edges_already_present=edges_already_present,
    )


def apply_import_plan(
    plan: ImportPlan,
    *,
    node_store: MutableMapping[str, dict[str, Any]],
    edge_store: MutableMapping[tuple[str, str, str, str], dict[str, Any]],
) -> None:
    """Apply a previously validated plan to a caller-owned in-memory store."""

    for node in plan.nodes_to_create:
        node_store[str(node["id"])] = copy.deepcopy(node)
    for edge in plan.edges_to_create:
        edge_store[_edge_storage_key(edge)] = copy.deepcopy(edge)
