"""Semantic validation helpers for the FROZEN TPDX Schema 4.2 contract.

JSON Schema validates record shapes and endpoint prefixes. This module validates
cross-edge invariants that require viewing the diagnostic bundle as a graph.
It is side-effect free and does not read governance or data files.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from hashlib import sha256
from typing import Any


ASSERTION_EDGE_IDENTITY_VERSION = "assertion_edge_identity_v1"
_DELIMITER = "\x1f"

_PROJECTION_RULES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "HAS_CODE": (
        ("OBSERVES", "mapping_record", "from"),
        ("USES_ERROR_CODE", "mapping_record", "to"),
    ),
    "HAS_CAUSE": (
        ("OBSERVES", "mapping_record", "from"),
        ("ASSERTS_CAUSE", "mapping_record", "to"),
    ),
    "HAS_ACTION": (
        ("ASSERTS_CAUSE", "mapping_record", "from"),
        ("RECOMMENDS_ACTION", "mapping_record", "to"),
    ),
    "HAS_STEPS": (
        ("RECOMMENDS_ACTION", "mapping_record", "from"),
    ),
}

_PROJECTION_ENDPOINT_LABELS = {
    "HAS_CODE": ("Phenomenon", "ErrorCode"),
    "HAS_CAUSE": ("Phenomenon", "Cause"),
    "HAS_ACTION": ("Cause", "Action"),
    "HAS_STEPS": ("Action", "ActionStep"),
}

_MAPPING_RECORD_CARDINALITIES = {
    "SCOPED_TO": (1, 1),
    "OBSERVES": (1, 1),
    "USES_ERROR_CODE": (0, 1),
}


class SchemaV42SemanticError(ValueError):
    """Raised when a structurally valid Schema 4.2 bundle is inconsistent."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def assertion_edge_id(
    relationship_type: str,
    from_id: str,
    to_id: str,
    mapping_record_id: str,
) -> str:
    """Return the deterministic Schema 4.2 assertion projection identifier."""

    identity = _DELIMITER.join(
        (relationship_type, from_id, to_id, mapping_record_id)
    )
    return "AE_" + sha256(identity.encode("utf-8")).hexdigest()


def _node_index(
    nodes: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    index: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str):
            errors.append("node without a string id")
            continue
        if node_id in index:
            errors.append(f"duplicate node id {node_id}")
            continue
        index[node_id] = node
    return index, errors


def validate_v4_2_semantics(
    payload: Mapping[str, Any],
    *,
    existing_nodes: Iterable[Mapping[str, Any]] = (),
    existing_edges: Iterable[Mapping[str, Any]] = (),
) -> None:
    """Validate cross-record invariants for one Schema 4.2 payload.

    ``existing_nodes`` and ``existing_edges`` are an explicitly governed graph
    context for payloads that reference pre-existing nodes. Callers must not use
    an ungoverned or partially filtered context to satisfy publication checks.
    """

    payload_nodes = payload.get("nodes", ())
    payload_edges = payload.get("edges", ())
    if not isinstance(payload_nodes, list) or not isinstance(payload_edges, list):
        raise SchemaV42SemanticError(
            ("payload nodes and edges must be arrays before semantic validation",)
        )

    existing_nodes = list(existing_nodes)
    existing_edges = list(existing_edges)
    all_nodes = [*existing_nodes, *payload_nodes]
    all_edges = [*existing_edges, *payload_edges]
    nodes, errors = _node_index(all_nodes)

    membership_edges: set[tuple[str, str, str]] = set()
    mapping_memberships: dict[str, Counter[str]] = defaultdict(Counter)
    for edge in all_edges:
        edge_type = edge.get("type")
        from_id = edge.get("from")
        to_id = edge.get("to")
        if all(isinstance(value, str) for value in (edge_type, from_id, to_id)):
            membership_edges.add((edge_type, from_id, to_id))
            if edge_type in _MAPPING_RECORD_CARDINALITIES:
                mapping_memberships[from_id][edge_type] += 1

    known_mapping_records = {
        node_id
        for node_id, node in nodes.items()
        if node.get("label") == "MappingRecord"
    }
    for mapping_record_id in sorted(known_mapping_records):
        properties = nodes[mapping_record_id].get("properties", {})
        if properties.get("mapping_record_id") != mapping_record_id:
            errors.append(
                f"MappingRecord {mapping_record_id} mapping_record_id must equal node id"
            )
        if properties.get("review_status") != "reviewed":
            errors.append(f"backing MappingRecord {mapping_record_id} is not reviewed")
        if properties.get("serving_safe") is not True:
            errors.append(
                f"backing MappingRecord {mapping_record_id} is not serving-safe"
            )
        if not properties.get("promotion_decision_id"):
            errors.append(
                f"backing MappingRecord {mapping_record_id} has no promotion decision"
            )

        for relationship_type, (minimum, maximum) in (
            _MAPPING_RECORD_CARDINALITIES.items()
        ):
            count = mapping_memberships[mapping_record_id][relationship_type]
            if count < minimum or count > maximum:
                expected = (
                    f"exactly {minimum}"
                    if minimum == maximum
                    else f"between {minimum} and {maximum}"
                )
                errors.append(
                    f"MappingRecord {mapping_record_id} requires {expected} "
                    f"{relationship_type} edge(s), found {count}"
                )

    projection_entries = [
        (f"existing_edges[{position}]", edge)
        for position, edge in enumerate(existing_edges)
        if edge.get("type") in _PROJECTION_RULES
    ] + [
        (f"edges[{position}]", edge)
        for position, edge in enumerate(payload_edges)
        if edge.get("type") in _PROJECTION_RULES
    ]
    assertion_id_counts = Counter(
        edge.get("properties", {}).get("assertion_edge_id")
        for _, edge in projection_entries
    )
    action_steps: dict[str, set[str]] = defaultdict(set)

    for edge_ref, edge in projection_entries:
        edge_type = edge.get("type")
        from_id = edge.get("from")
        to_id = edge.get("to")
        properties = edge.get("properties", {})
        mapping_record_id = properties.get("mapping_record_id")
        actual_assertion_id = properties.get("assertion_edge_id")
        edge_ref = f"{edge_ref} {edge_type}"

        expected_from_label, expected_to_label = _PROJECTION_ENDPOINT_LABELS[edge_type]
        for endpoint, expected_label, role in (
            (from_id, expected_from_label, "from"),
            (to_id, expected_to_label, "to"),
        ):
            node = nodes.get(endpoint)
            if node is None:
                errors.append(f"{edge_ref} has unresolved {role} endpoint {endpoint}")
            elif node.get("label") != expected_label:
                errors.append(
                    f"{edge_ref} {role} endpoint {endpoint} must be {expected_label}"
                )

        if mapping_record_id not in known_mapping_records:
            errors.append(
                f"{edge_ref} references unknown MappingRecord {mapping_record_id}"
            )
            continue

        if not all(
            isinstance(value, str)
            for value in (edge_type, from_id, to_id, mapping_record_id)
        ):
            errors.append(f"{edge_ref} has non-string assertion identity inputs")
        else:
            expected_assertion_id = assertion_edge_id(
                edge_type, from_id, to_id, mapping_record_id
            )
            if actual_assertion_id != expected_assertion_id:
                errors.append(
                    f"{edge_ref} assertion_edge_id must be {expected_assertion_id}"
                )
        if not isinstance(actual_assertion_id, str):
            errors.append(f"{edge_ref} has no string assertion_edge_id")
        elif assertion_id_counts[actual_assertion_id] > 1:
            errors.append(
                f"{edge_ref} duplicates assertion_edge_id {actual_assertion_id}"
            )
        if not isinstance(properties.get("source"), str) or not properties["source"]:
            errors.append(f"{edge_ref} has no non-empty source")
        if not isinstance(properties.get("extracted_from"), str) or not properties[
            "extracted_from"
        ]:
            errors.append(f"{edge_ref} has no non-empty extracted_from")
        if edge_type == "HAS_ACTION" and not properties.get(
            "cause_action_pair_id"
        ):
            errors.append(f"{edge_ref} has no explicit cause_action_pair_id")

        for membership_type, membership_from, membership_to in _PROJECTION_RULES[
            edge_type
        ]:
            required_from = (
                mapping_record_id if membership_from == "mapping_record" else from_id
            )
            required_to = (
                from_id
                if membership_to == "from"
                else to_id
                if membership_to == "to"
                else mapping_record_id
            )
            required = (membership_type, required_from, required_to)
            if required not in membership_edges:
                errors.append(
                    f"{edge_ref} lacks backing membership "
                    f"{required_from}-[:{membership_type}]->{required_to}"
                )

        if edge_type == "HAS_STEPS" and isinstance(from_id, str) and isinstance(
            to_id, str
        ):
            action_steps[from_id].add(to_id)

    for action_id, step_ids in sorted(action_steps.items()):
        orders: list[int] = []
        for step_id in sorted(step_ids):
            step = nodes.get(step_id)
            if step is None or step.get("label") != "ActionStep":
                errors.append(
                    f"Action {action_id} references unresolved ActionStep {step_id}"
                )
                continue
            order = step.get("properties", {}).get("order")
            if not isinstance(order, int):
                errors.append(f"ActionStep {step_id} has no integer order")
                continue
            orders.append(order)
        if sorted(orders) != list(range(1, len(step_ids) + 1)):
            errors.append(
                f"Action {action_id} step orders must be unique and contiguous from 1"
            )

    if errors:
        raise SchemaV42SemanticError(errors)
