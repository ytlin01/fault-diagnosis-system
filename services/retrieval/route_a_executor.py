"""Route A structured executor — source guard + Neo4j text2cypher execution.

Receives a serialised CanonicalState dict, enforces source policy, resolves the
best CAD asset entity slot, selects a Cypher template, executes against Neo4j,
and returns a {items, used_sources, warnings} dict.

Never raises — all errors are returned as warnings so the LangGraph main
graph is not disrupted.

Neo4j connection is read from environment variables (via .env):
    FAULTDX_NEO4J_HOST      bolt://127.0.0.1:7687
    FAULTDX_NEO4J_USER      neo4j
    FAULTDX_NEO4J_PASSWORD  <your-password>
    FAULTDX_NEO4J_DATABASE  neo4j
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from services.graph.neo4j_client import NEO4J_DATABASE, get_driver
from services.graph.text2cypher.templates import (
    CYPHER,
    CYPHER_DIAGNOSTIC,
    INTENT_CONNECTIONS,
    INTENT_CROSS_MODULE,
    INTENT_DIAGNOSTIC_CHAIN,
    INTENT_HIERARCHY,
    VALID_INTENTS,
)
from services.routing.query_router import (
    ASSET_STRUCTURED_QUERY,
    REVIEWED_DIAGNOSTIC_CHAIN,
    UNREVIEWED_DIAGNOSTIC_CHAIN,
)

_LABEL_PRIORITY = ("subcomponent", "component", "module", "station")

_FP_QUESTION_SUFFIXES = (
    "怎么处理", "如何处理", "怎么修", "如何修",
    "怎么排查", "如何排查", "如何解决", "怎么解决",
    "怎么办", "是什么原因", "是什么意思", "是什么",
    "如何处理", "如何操作",
)
_NEO4J_SOURCE_ID = "neo4j_cad_kg_v3_2"
_ROUTE_A_ALLOWED = {REVIEWED_DIAGNOSTIC_CHAIN, UNREVIEWED_DIAGNOSTIC_CHAIN, ASSET_STRUCTURED_QUERY}
_DIAGNOSTIC_ROUTES = {REVIEWED_DIAGNOSTIC_CHAIN, UNREVIEWED_DIAGNOSTIC_CHAIN}


def execute_route_a(
    canonical_state: Mapping[str, Any],
    *,
    route: str,
    allowed_sources: Iterable[str],
) -> dict[str, Any]:
    """Execute Route A structured slot.

    Parameters
    ----------
    canonical_state:
        Serialised CanonicalState dict (output of ``canonicalize_query()``).
    route:
        Resolved route from the routing decision (e.g. ``REVIEWED_DIAGNOSTIC_CHAIN``).
    allowed_sources:
        Sources cleared by the policy router for this request.

    Returns
    -------
    dict with keys ``items``, ``used_sources``, ``warnings``. Never raises.
    """
    if route not in _ROUTE_A_ALLOWED:
        return _empty_output(f"Route A received an unsupported route target: {route!r}.")

    allowed = tuple(str(s) for s in allowed_sources)
    if not allowed:
        return _empty_output(
            "Route A is guarded: no reviewed serving-ready structured source was allowed."
        )

    intent = INTENT_DIAGNOSTIC_CHAIN if route in _DIAGNOSTIC_ROUTES else INTENT_HIERARCHY
    return execute_text2cypher(canonical_state, intent=intent)


def execute_text2cypher(
    canonical_state: Mapping[str, Any],
    *,
    intent: str = INTENT_HIERARCHY,
) -> dict[str, Any]:
    """Execute a Cypher query anchored on the best entity slot in canonical_state.

    Parameters
    ----------
    canonical_state:
        Serialised CanonicalState dict (i.e. the result of
        ``CanonicalState.as_dict()``).
    intent:
        One of INTENT_HIERARCHY / INTENT_CONNECTIONS / INTENT_CROSS_MODULE /
        INTENT_DIAGNOSTIC_CHAIN. Defaults to INTENT_HIERARCHY.

    Returns
    -------
    dict with keys ``items``, ``used_sources``, ``warnings``.
    """
    if intent not in VALID_INTENTS:
        return _empty_output(f"Route A: unknown intent {intent!r}.")

    if intent == INTENT_DIAGNOSTIC_CHAIN:
        return _execute_diagnostic_chain(canonical_state)

    node_id, label = _resolve_anchor(canonical_state)
    if not node_id:
        return _empty_output(
            "Route A: no CAD asset entity resolved in canonical state."
        )

    bucket = CYPHER.get(intent, {})
    cypher = bucket.get(label)
    if not cypher:
        return _empty_output(
            f"Route A: no Cypher template for intent={intent!r}, label={label!r}."
        )

    try:
        records = _run_cypher(cypher, {"node_id": node_id})
    except Exception as exc:  # noqa: BLE001
        return _empty_output(f"Route A: Neo4j query failed: {exc}")

    if not records:
        return _empty_output(
            f"Route A: node {node_id!r} ({label}) not found in the graph.",
            status="not_found",
        )

    items = _format_items(records, label, intent)
    return {
        "items": items,
        "used_sources": [_neo4j_source()],
        "warnings": [],
    }


def _resolve_anchor(
    canonical_state: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    """Return (node_id, label) for the highest-priority filled asset slot."""
    asset: Mapping[str, Any] = (
        canonical_state.get("entities", {}).get("asset", {})
    )
    for label in _LABEL_PRIORITY:
        slot = asset.get(label, {})
        canonical = slot.get("canonical") if isinstance(slot, Mapping) else None
        if canonical:
            return canonical, label
    return None, None


def _resolve_error_code(canonical_state: Mapping[str, Any]) -> str | None:
    """Return the canonical error code string from the diagnostic slot, if present."""
    slot = (
        canonical_state.get("entities", {})
        .get("diagnostic", {})
        .get("error_code", {})
    )
    canonical = slot.get("canonical") if isinstance(slot, Mapping) else None
    return canonical or None


def _resolve_fault_text(canonical_state: Mapping[str, Any]) -> str | None:
    """Return a clean fault phenomenon text with question suffixes stripped."""
    slot = (
        canonical_state.get("entities", {})
        .get("diagnostic", {})
        .get("fault", {})
    )
    text = slot.get("canonical") if isinstance(slot, Mapping) else None
    if not text:
        slot = (
            canonical_state.get("entities", {})
            .get("observation", {})
            .get("phenomenon_text", {})
        )
        text = slot.get("canonical") if isinstance(slot, Mapping) else None
    if not text:
        return None
    for suffix in _FP_QUESTION_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    text = text.rstrip("？?").strip()
    return text if len(text) >= 4 else None


def _execute_diagnostic_chain(canonical_state: Mapping[str, Any]) -> dict[str, Any]:
    ec_code = _resolve_error_code(canonical_state)
    if ec_code:
        cypher = CYPHER_DIAGNOSTIC["error_code"]
        params: dict[str, Any] = {"error_code": ec_code}
        anchor_desc = f"error_code={ec_code!r}"
    else:
        node_id, label = _resolve_anchor(canonical_state)
        if label == "component" and node_id:
            cypher = CYPHER_DIAGNOSTIC["component"]
            params = {"node_id": node_id}
            anchor_desc = f"component={node_id!r}"
        elif label == "module" and node_id:
            cypher = CYPHER_DIAGNOSTIC["module"]
            params = {"node_id": node_id}
            anchor_desc = f"module={node_id!r}"
        else:
            fault_text = _resolve_fault_text(canonical_state)
            if fault_text:
                cypher = CYPHER_DIAGNOSTIC["fault_text"]
                params = {"text": fault_text}
                anchor_desc = f"fault_text={fault_text!r}"
            else:
                return _empty_output(
                    "Route A diagnostic: no error_code, component, module, or fault text anchor resolved in canonical state."
                )

    try:
        records = _run_cypher(cypher, params)
    except Exception as exc:  # noqa: BLE001
        return _empty_output(f"Route A diagnostic: Neo4j query failed: {exc}")

    if not records:
        return _empty_output(
            f"Route A diagnostic: {anchor_desc} not found in graph.",
            status="not_found",
        )

    items = _format_diagnostic_items(records)
    return {
        "items": items,
        "used_sources": [_neo4j_source()],
        "warnings": [],
    }


def _run_cypher(cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(cypher, params)
        return [dict(record) for record in result]


def _format_items(
    records: list[dict[str, Any]],
    label: str,
    intent: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    if intent == INTENT_HIERARCHY:
        for rec in records:
            item: dict[str, Any] = {
                "label": label.capitalize(),
                "properties": _props(rec.get("node")),
            }
            children = rec.get("children")
            if children:
                item["children"] = [_props(c) for c in children if c]
            parent_props = rec.get("parent_props")
            if parent_props:
                item["parent"] = {
                    "label": str(rec.get("parent_label") or ""),
                    "properties": _props(parent_props),
                }
            items.append(item)

    elif intent == INTENT_CONNECTIONS:
        for rec in records:
            items.append({
                "source": {
                    "label": label.capitalize(),
                    "properties": _props(rec.get("source")),
                },
                "neighbor": {
                    "label": str(rec.get("neighbor_label") or ""),
                    "properties": _props(rec.get("neighbor")),
                },
                "connection_type": rec.get("connection_type"),
                "confidence": rec.get("confidence"),
            })

    elif intent == INTENT_CROSS_MODULE:
        for rec in records:
            item = {"label": label.capitalize(), "properties": _props(rec.get("node"))}
            for key in ("modules", "components", "subcomponents", "descendants"):
                if key in rec:
                    item[key] = [_props(c) for c in (rec[key] or []) if c]
            items.append(item)

    else:
        for rec in records:
            items.append({k: (v if not _is_neo4j_node(v) else dict(v)) for k, v in rec.items()})

    return items


def _format_diagnostic_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for rec in records:
        item: dict[str, Any] = {}
        if rec.get("error_code"):
            item["error_code"] = _props(rec["error_code"])
        if rec.get("component"):
            item["component"] = _props(rec["component"])
        if rec.get("fault"):
            item["fault"] = _props(rec["fault"])
        if rec.get("cause"):
            item["cause"] = _props(rec["cause"])
        if rec.get("action"):
            item["action"] = _props(rec["action"])
        steps = rec.get("steps") or []
        item["steps"] = [_props(s) for s in steps if s]
        items.append(item)
    return items


def _props(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return dict(value)
    except Exception:
        return {}


def _is_neo4j_node(value: Any) -> bool:
    return hasattr(value, "labels") and hasattr(value, "items")


def _neo4j_source() -> dict[str, Any]:
    return {
        "source_type": "reviewed_asset_graph",
        "source_id": _NEO4J_SOURCE_ID,
        "snapshot_id": None,
        "updated_at": None,
    }


def _empty_output(warning: str, *, status: str = "warning") -> dict[str, Any]:
    return {
        "items": [],
        "used_sources": [],
        "warnings": [warning],
    }
