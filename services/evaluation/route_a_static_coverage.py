"""Graph-independent static coverage evaluation for Route A snapshots."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


SCHEMA_VERSION = "route_a_static_coverage_input_v1"


class StaticCoverageInputError(ValueError):
    """Raised when a normalized static-coverage snapshot is malformed."""


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StaticCoverageInputError(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise StaticCoverageInputError(f"{name} must be an array of objects")
    return value


def validate_static_coverage_input(payload: Mapping[str, Any]) -> None:
    """Validate the contract invariants required by the scorer.

    JSON Schema validation remains a caller concern; this makes the executable
    boundary safe even when the optional ``jsonschema`` package is unavailable.
    """
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise StaticCoverageInputError(f"schema_version must be {SCHEMA_VERSION}")
    candidate = _require_mapping(payload.get("candidate"), "candidate")
    for field in ("candidate_id", "graph_version", "snapshot_id", "data_maturity", "config_digest"):
        if not isinstance(candidate.get(field), str) or not candidate[field]:
            raise StaticCoverageInputError(f"candidate.{field} must be a non-empty string")
    if candidate["data_maturity"] not in {"assumed_label_provisional", "provisional", "reviewed"}:
        raise StaticCoverageInputError("candidate.data_maturity is invalid")
    for name in ("nodes", "relations"):
        _require_list(payload.get(name), name)
    targets = _require_mapping(payload.get("coverage_targets"), "coverage_targets")
    for name in ("expected_entities", "expected_relations", "expected_paths"):
        _require_list(targets.get(name), f"coverage_targets.{name}")


def _triple(item: Mapping[str, Any]) -> tuple[str, str, str]:
    values = (item.get("subject_id"), item.get("relation"), item.get("object_id"))
    if not all(isinstance(value, str) and value for value in values):
        raise StaticCoverageInputError("relations and target relations require non-empty subject_id, relation, and object_id")
    return values  # type: ignore[return-value]


def evaluate_static_coverage(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return coverage, integrity, provenance, and review-state evidence."""
    validate_static_coverage_input(payload)
    candidate = payload["candidate"]
    nodes = _require_list(payload["nodes"], "nodes")
    relations = _require_list(payload["relations"], "relations")
    targets = _require_mapping(payload["coverage_targets"], "coverage_targets")

    node_keys = []
    node_ids: set[str] = set()
    review_states: Counter[str] = Counter()
    for node in nodes:
        concept_id, concept_type = node.get("concept_id"), node.get("concept_type")
        if not isinstance(concept_id, str) or not concept_id or not isinstance(concept_type, str) or not concept_type:
            raise StaticCoverageInputError("nodes require non-empty concept_id and concept_type")
        node_keys.append((concept_id, concept_type))
        node_ids.add(concept_id)
        review_states[str(node.get("review_state", "unknown"))] += 1

    relation_triples = [_triple(relation) for relation in relations]
    relation_set = set(relation_triples)
    dangling = [triple for triple in relation_triples if triple[0] not in node_ids or triple[2] not in node_ids]

    expected_nodes = _require_list(targets["expected_entities"], "coverage_targets.expected_entities")
    expected_node_keys = set()
    for node in expected_nodes:
        concept_id, concept_type = node.get("concept_id"), node.get("concept_type")
        if not isinstance(concept_id, str) or not isinstance(concept_type, str):
            raise StaticCoverageInputError("expected entities require concept_id and concept_type")
        expected_node_keys.add((concept_id, concept_type))
    expected_relations = {_triple(item) for item in _require_list(targets["expected_relations"], "coverage_targets.expected_relations")}

    path_results = []
    for path in _require_list(targets["expected_paths"], "coverage_targets.expected_paths"):
        path_id, kind = path.get("path_id"), path.get("kind")
        edges = _require_list(path.get("edges"), "coverage_targets.expected_paths[].edges")
        if not isinstance(path_id, str) or not path_id or kind not in {"topology", "diagnostic", "bridge"} or not edges:
            raise StaticCoverageInputError("each expected path needs path_id, valid kind, and at least one edge")
        path_results.append({"path_id": path_id, "kind": kind, "covered": all(_triple(edge) in relation_set for edge in edges)})

    bridge = targets.get("bridge", {})
    if bridge is None:
        bridge = {}
    bridge = _require_mapping(bridge, "coverage_targets.bridge")
    bridge_relations = set(bridge.get("relation_types", []))
    bridge_sources = set(bridge.get("source_types", []))
    eligible_bridge_ids = {node["concept_id"] for node in nodes if node.get("concept_type") in bridge_sources}
    bridged_ids = {subject for subject, relation, _ in relation_triples if subject in eligible_bridge_ids and relation in bridge_relations}

    required_provenance = set(targets.get("provenance_required_relations", []))
    provenance_relations = [relation for relation in relations if relation.get("relation") in required_provenance]
    provenance_complete = 0
    for relation in provenance_relations:
        provenance = relation.get("provenance")
        if isinstance(provenance, Mapping) and isinstance(provenance.get("source_id"), str) and provenance.get("source_id") and isinstance(provenance.get("anchor"), str) and provenance.get("anchor"):
            provenance_complete += 1

    blockers = []
    if dangling:
        blockers.append("dangling_relations")
    if provenance_complete != len(provenance_relations):
        blockers.append("missing_required_provenance")

    return {
        "report_schema_version": "route_a_static_coverage_report_v1",
        "candidate": dict(candidate),
        "maturity": candidate["data_maturity"],
        "coverage": {
            "entity_recall": _ratio(len(expected_node_keys & set(node_keys)), len(expected_node_keys)),
            "relation_recall": _ratio(len(expected_relations & relation_set), len(expected_relations)),
            "path_recall": _ratio(sum(item["covered"] for item in path_results), len(path_results)),
            "paths": path_results,
            "bridge_source_coverage": _ratio(len(bridged_ids), len(eligible_bridge_ids)),
        },
        "provenance": {"required_relation_count": len(provenance_relations), "complete_relation_count": provenance_complete, "completeness": _ratio(provenance_complete, len(provenance_relations))},
        "integrity": {"node_count": len(nodes), "relation_count": len(relations), "duplicate_nodes": len(node_keys) - len(set(node_keys)), "duplicate_relations": len(relation_triples) - len(relation_set), "dangling_relations": len(dangling)},
        "review_state_counts": dict(sorted(review_states.items())),
        "blockers": blockers,
    }
