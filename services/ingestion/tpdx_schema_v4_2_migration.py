"""Deterministic synthetic-only migration from TPDX Schema 4.1 to 4.2.

The adapter operates on already-governed Schema 4.1 bundles.  It preserves the
Schema 4.1 membership graph, removes ``HAS_STEP`` membership edges, and emits
MappingRecord-backed Schema 4.2 assertion projections.  Cause-to-Action
projections are accepted only from an explicit reviewed pairing input.

This module does not read governance or data files and does not import into a
runtime graph.  The command-line candidate builder owns file I/O and manifest
creation.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Mapping

from services.governance.tpdx_schema_v4_2 import (
    SchemaV42SemanticError,
    assertion_edge_id,
    validate_v4_2_semantics,
)


MIGRATION_VERSION = "tpdx_schema_v4_1_to_v4_2_migration_v1"
TARGET_SCHEMA_VERSION = "4.2"
SOURCE_SCHEMA_VERSION = "4.1"
_PROJECTION_TYPES = {"HAS_CODE", "HAS_CAUSE", "HAS_ACTION", "HAS_STEPS"}
_LEGACY_DIRECT_TYPES = _PROJECTION_TYPES | {"HAS_STEP"}
_EXCLUSION_REASONS = {
    "missing_stable_native_id",
    "duplicate_canonical_id",
    "missing_parent",
    "multiple_parents",
    "self_parent",
    "cycle",
    "parent_mismatch",
    "cross_namespace_without_merge",
    "invalid_type",
    "other",
}


class MigrationError(ValueError):
    """Raised when a Schema 4.1 bundle cannot safely enter the v2 path."""


@dataclass(frozen=True)
class MigrationResult:
    """Candidate and governed evidence produced by one deterministic run."""

    candidate: dict[str, Any]
    exclusions: tuple[dict[str, str], ...]
    lineage: tuple[dict[str, str], ...]

    @property
    def complete(self) -> bool:
        return not self.exclusions


def canonical_json_bytes(value: Any) -> bytes:
    """Return the stable JSON representation used for fingerprints."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    """Fingerprint a JSON value independently of whitespace/key ordering."""

    return "sha256:" + sha256(canonical_json_bytes(value)).hexdigest()


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise MigrationError(f"{field} must be a non-empty string")
    return value


def _edge_key(edge: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(edge.get("type", "")),
        str(edge.get("from", "")),
        str(edge.get("to", "")),
        canonical_json_bytes(edge.get("properties", {})).decode("utf-8"),
    )


def _sort_key(value: Mapping[str, Any]) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _exclusion(
    source_native_id: str,
    detail: str,
    *,
    reason: str = "other",
) -> dict[str, str]:
    if reason not in _EXCLUSION_REASONS:
        reason = "other"
    return {
        "source_native_id": source_native_id or "unknown-source-record",
        "reason": reason,
        "detail": detail,
    }


def _dedupe_exclusions(
    exclusions: Iterable[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    unique = {
        (
            item.get("source_native_id", ""),
            item.get("reason", "other"),
            item.get("detail", ""),
        ): {
            "source_native_id": item.get("source_native_id", ""),
            "reason": item.get("reason", "other"),
            "detail": item.get("detail", ""),
        }
        for item in exclusions
    }
    return tuple(unique[key] for key in sorted(unique))


def _validate_input_shape(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise MigrationError("input payload must declare Schema 4.1")
    if payload.get("payload_kind") not in {"topology", "diagnostic", "combined"}:
        raise MigrationError("input payload_kind is not supported")
    for field in ("nodes", "edges", "exclusions"):
        if not isinstance(payload.get(field), list):
            raise MigrationError(f"input {field} must be an array")


def _index_nodes(
    nodes: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        node_id = _string(node.get("id"), "node.id")
        if node_id in index:
            raise MigrationError(f"duplicate node id {node_id}")
        if not isinstance(node.get("label"), str):
            raise MigrationError(f"node {node_id} has no label")
        if not isinstance(node.get("properties"), Mapping):
            raise MigrationError(f"node {node_id} has no properties object")
        index[node_id] = node
    return index


def _edge_lists(
    edges: Iterable[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    by_type: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        edge_type = _string(edge.get("type"), "edge.type")
        _string(edge.get("from"), "edge.from")
        _string(edge.get("to"), "edge.to")
        if not isinstance(edge.get("properties"), Mapping):
            raise MigrationError(f"{edge_type} edge has no properties object")
        key = _edge_key(edge)
        if key in seen:
            raise MigrationError(
                f"duplicate input edge {edge_type} {edge.get('from')}->{edge.get('to')}"
            )
        seen.add(key)
        by_type[edge_type].append(edge)
    return by_type


def _mapping_record_indexes(
    nodes: Mapping[str, Mapping[str, Any]],
    by_type: Mapping[str, list[Mapping[str, Any]]],
) -> tuple[
    dict[str, Mapping[str, Any]],
    dict[str, dict[str, list[Mapping[str, Any]]]],
]:
    records = {
        node_id: node
        for node_id, node in nodes.items()
        if node.get("label") == "MappingRecord"
    }
    memberships: dict[str, dict[str, list[Mapping[str, Any]]]] = {
        record_id: defaultdict(list) for record_id in records
    }
    for edge_type in (
        "SCOPED_TO",
        "OBSERVES",
        "USES_ERROR_CODE",
        "ASSERTS_CAUSE",
        "RECOMMENDS_ACTION",
    ):
        for edge in by_type.get(edge_type, []):
            record_id = edge.get("from")
            if record_id not in records:
                raise MigrationError(
                    f"{edge_type} edge references unknown MappingRecord {record_id}"
                )
            memberships[record_id][edge_type].append(edge)

    for record_id, record in records.items():
        properties = record["properties"]
        if properties.get("mapping_record_id") != record_id:
            raise MigrationError(
                f"MappingRecord {record_id} mapping_record_id does not match node id"
            )
        if properties.get("review_status") != "reviewed":
            raise MigrationError(f"MappingRecord {record_id} is not reviewed")
        if properties.get("serving_safe") is not True:
            raise MigrationError(f"MappingRecord {record_id} is not serving-safe")
        if not properties.get("promotion_decision_id"):
            raise MigrationError(
                f"MappingRecord {record_id} has no promotion decision"
            )
        if len(memberships[record_id]["SCOPED_TO"]) != 1:
            raise MigrationError(
                f"MappingRecord {record_id} requires exactly one SCOPED_TO edge"
            )
        if len(memberships[record_id]["OBSERVES"]) != 1:
            raise MigrationError(
                f"MappingRecord {record_id} requires exactly one OBSERVES edge"
            )
        if len(memberships[record_id]["USES_ERROR_CODE"]) > 1:
            raise MigrationError(
                f"MappingRecord {record_id} has multiple USES_ERROR_CODE edges"
            )
    return records, memberships


def _pairing_index(
    pairings: Iterable[Mapping[str, Any]],
    records: Mapping[str, Mapping[str, Any]],
    memberships: Mapping[str, Mapping[str, list[Mapping[str, Any]]]],
    exclusions: list[dict[str, str]],
) -> dict[tuple[str, str], list[Mapping[str, str]]]:
    by_action: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    seen_pair_ids: dict[str, tuple[str, str, str]] = {}
    seen_triplets: dict[tuple[str, str, str], str] = {}
    for position, pairing in enumerate(pairings):
        source_id = str(pairing.get("cause_action_pair_id") or f"pair-{position}")
        required = (
            "mapping_record_id",
            "cause_id",
            "action_id",
            "cause_action_pair_id",
            "source",
            "extracted_from",
        )
        missing = [field for field in required if not pairing.get(field)]
        if missing:
            exclusions.append(
                _exclusion(source_id, f"pairing missing required fields: {','.join(missing)}")
            )
            continue
        record_id = str(pairing["mapping_record_id"])
        cause_id = str(pairing["cause_id"])
        action_id = str(pairing["action_id"])
        pair_id = str(pairing["cause_action_pair_id"])
        if pairing.get("review_status") != "reviewed" or pairing.get("serving_safe") is not True:
            exclusions.append(
                _exclusion(pair_id, "cause-action pairing is not reviewed and serving-safe")
            )
            continue
        if record_id not in records:
            exclusions.append(_exclusion(pair_id, f"unknown MappingRecord {record_id}"))
            continue
        causes = {edge["to"] for edge in memberships[record_id]["ASSERTS_CAUSE"]}
        actions = {edge["to"] for edge in memberships[record_id]["RECOMMENDS_ACTION"]}
        if cause_id not in causes or action_id not in actions:
            exclusions.append(
                _exclusion(
                    pair_id,
                    "pairing endpoints are not both backed by MappingRecord memberships",
                )
            )
            continue
        identity = (record_id, cause_id, action_id)
        previous_pair_id = seen_triplets.get(identity)
        if previous_pair_id and previous_pair_id != pair_id:
            exclusions.append(
                _exclusion(pair_id, "conflicting cause-action pair identifiers")
            )
            continue
        previous_identity = seen_pair_ids.get(pair_id)
        if previous_identity and previous_identity != identity:
            exclusions.append(_exclusion(pair_id, "pair identifier is reused for different endpoints"))
            continue
        seen_pair_ids[pair_id] = identity
        seen_triplets[identity] = pair_id
        by_action[(record_id, action_id)].append(
            {
                "mapping_record_id": record_id,
                "cause_id": cause_id,
                "action_id": action_id,
                "cause_action_pair_id": pair_id,
                "source": str(pairing["source"]),
                "extracted_from": str(pairing["extracted_from"]),
            }
        )
    for values in by_action.values():
        values.sort(key=lambda item: (item["cause_id"], item["action_id"], item["cause_action_pair_id"]))
    return by_action


def _projection(
    edge_type: str,
    from_id: str,
    to_id: str,
    mapping_record_id: str,
    source: str,
    extracted_from: str,
    *,
    cause_action_pair_id: str | None = None,
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "assertion_edge_id": assertion_edge_id(
            edge_type, from_id, to_id, mapping_record_id
        ),
        "mapping_record_id": mapping_record_id,
        "source": source,
        "extracted_from": extracted_from,
    }
    if cause_action_pair_id is not None:
        properties["cause_action_pair_id"] = cause_action_pair_id
    return {
        "type": edge_type,
        "from": from_id,
        "to": to_id,
        "properties": properties,
    }


def migrate_v4_1_payload(
    payload: Mapping[str, Any],
    *,
    pairings: Iterable[Mapping[str, Any]] = (),
) -> MigrationResult:
    """Migrate one governed Schema 4.1 bundle into a Schema 4.2 candidate.

    Pairings are an explicit reviewed input.  The adapter never creates a
    cause/action Cartesian product from independent membership edges.
    """

    _validate_input_shape(payload)
    nodes = _index_nodes(payload["nodes"])
    by_type = _edge_lists(payload["edges"])
    if any(edge_type in _PROJECTION_TYPES for edge_type in by_type):
        raise MigrationError("input already contains Schema 4.2 projection edges")
    records, memberships = _mapping_record_indexes(nodes, by_type)
    exclusions: list[dict[str, str]] = [
        copy.deepcopy(item) for item in payload.get("exclusions", [])
    ]
    pair_index = _pairing_index(pairings, records, memberships, exclusions)

    candidate_edges: list[dict[str, Any]] = []
    for edge in payload["edges"]:
        if edge["type"] != "HAS_STEP":
            candidate_edges.append(copy.deepcopy(dict(edge)))

    lineage: list[dict[str, str]] = []
    record_source: dict[str, tuple[str, str]] = {}
    for record_id, record in records.items():
        properties = record["properties"]
        source = str(properties["source_id"])
        extracted_from = str(
            properties.get("source_anchor") or properties["source_record_id"]
        )
        record_source[record_id] = (source, extracted_from)

        observed = memberships[record_id]["OBSERVES"][0]["to"]
        for edge_type, target_edges in (
            ("HAS_CODE", memberships[record_id]["USES_ERROR_CODE"]),
            ("HAS_CAUSE", memberships[record_id]["ASSERTS_CAUSE"]),
        ):
            for target_edge in sorted(target_edges, key=lambda item: str(item["to"])):
                generated = _projection(
                    edge_type,
                    observed,
                    str(target_edge["to"]),
                    record_id,
                    source,
                    extracted_from,
                )
                candidate_edges.append(generated)
                lineage.append(
                    {
                        "target_type": edge_type,
                        "target_assertion_edge_id": generated["properties"]["assertion_edge_id"],
                        "mapping_record_id": record_id,
                        "source": source,
                        "extracted_from": extracted_from,
                    }
                )

        action_edges = memberships[record_id]["RECOMMENDS_ACTION"]
        for action_edge in sorted(action_edges, key=lambda item: str(item["to"])):
            action_id = str(action_edge["to"])
            pairs = pair_index.get((record_id, action_id), [])
            if not pairs:
                exclusions.append(
                    _exclusion(
                        f"{record_id}:{action_id}",
                        "action membership has no explicit reviewed cause-action pairing",
                    )
                )
                continue
            for pairing in pairs:
                generated = _projection(
                    "HAS_ACTION",
                    str(pairing["cause_id"]),
                    action_id,
                    record_id,
                    pairing["source"],
                    pairing["extracted_from"],
                    cause_action_pair_id=pairing["cause_action_pair_id"],
                )
                candidate_edges.append(generated)
                lineage.append(
                    {
                        "target_type": "HAS_ACTION",
                        "target_assertion_edge_id": generated["properties"]["assertion_edge_id"],
                        "mapping_record_id": record_id,
                        "source": pairing["source"],
                        "extracted_from": pairing["extracted_from"],
                        "cause_action_pair_id": pairing["cause_action_pair_id"],
                    }
                )

    action_to_records: dict[str, set[str]] = defaultdict(set)
    for record_id, record_memberships in memberships.items():
        for edge in record_memberships["RECOMMENDS_ACTION"]:
            action_to_records[str(edge["to"])].add(record_id)
    seen_steps: set[tuple[str, str]] = set()
    for step_edge in by_type.get("HAS_STEP", []):
        action_id = str(step_edge["from"])
        step_id = str(step_edge["to"])
        key = (action_id, step_id)
        if key in seen_steps:
            exclusions.append(_exclusion(f"{action_id}:{step_id}", "duplicate HAS_STEP membership"))
            continue
        seen_steps.add(key)
        backing_records = sorted(action_to_records.get(action_id, set()))
        if len(backing_records) != 1:
            detail = (
                "HAS_STEP has no unique MappingRecord backing"
                if not backing_records
                else "HAS_STEP has multiple MappingRecord backings"
            )
            exclusions.append(_exclusion(f"{action_id}:{step_id}", detail))
            continue
        record_id = backing_records[0]
        source, extracted_from = record_source[record_id]
        generated = _projection(
            "HAS_STEPS",
            action_id,
            step_id,
            record_id,
            source,
            extracted_from,
        )
        candidate_edges.append(generated)
        lineage.append(
            {
                "target_type": "HAS_STEPS",
                "target_assertion_edge_id": generated["properties"]["assertion_edge_id"],
                "mapping_record_id": record_id,
                "source": source,
                "extracted_from": extracted_from,
            }
        )

    candidate = {
        "schema_version": TARGET_SCHEMA_VERSION,
        "payload_kind": payload["payload_kind"],
        "nodes": sorted(
            [copy.deepcopy(dict(node)) for node in payload["nodes"]],
            key=lambda item: (str(item.get("label")), str(item.get("id"))),
        ),
        "edges": sorted(candidate_edges, key=_sort_key),
        "exclusions": list(_dedupe_exclusions(exclusions)),
    }
    lineage.sort(key=_sort_key)
    try:
        validate_v4_2_semantics(candidate)
    except SchemaV42SemanticError as exc:
        raise MigrationError(f"migrated candidate failed semantic validation: {exc}") from exc
    return MigrationResult(
        candidate=candidate,
        exclusions=_dedupe_exclusions(exclusions),
        lineage=tuple(lineage),
    )
