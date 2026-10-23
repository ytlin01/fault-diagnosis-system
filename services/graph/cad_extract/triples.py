"""
Emit schema v3.2-conformant nodes and edges from the extracted CAD model.

Bridges the CAD-layer artifacts (Hierarchy + HierarchyEdge + Mate) into the
{nodes, edges} shape that the diagnostic KG expects:

  Nodes
    Station      (one per extraction run — the STEP root assembly)  ST_<id>
    Module       (depth-1 children of root)                         M_<nauo_id>
    Component    (depth-2 children of Module)                       C_<nauo_id>
    SubComponent (depth ≥ 3 children of Component/SubComponent)     SC_<nauo_id>

  Edges
    HAS_MODULE        Station              -> Module
    HAS_COMPONENT     Module              -> Component
    HAS_SUBCOMPONENT  Component/SubComponent -> SubComponent
    HAS_CONNECTION    {Module,Component,SubComponent} -- {Module,Component,SubComponent}  (undirected)

v3.2 differences from v3.1
---------------------------
- QPL node removed from schema. Station is the new top-level device-asset node.
- Module.station_id replaces Module.qpl_id — always a real string.
- HAS_MODULE.from is always a Station node id (no more null).
- One Station node is emitted per extraction run, derived from the STEP root
  assembly (Option A — see docs/agents/cad_extract.md).

ID convention: a single NAUO becomes a single node; node id is the typed
prefix plus the NAUO id (`M_31`, `C_42`). The Station id is `ST_<station_id>`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .hierarchy import Hierarchy
from .kg_edges import (
    EDGE_HAS_COMPONENT,
    EDGE_HAS_MODULE,
    EDGE_HAS_SUBCOMPONENT,
    HierarchyEdge,
    canonical_parent_nauo_by_product,
    compute_nauo_depths,
)
from .relationships import Mate


SCHEMA_VERSION = "3.2"

EDGE_HAS_CONNECTION = "HAS_CONNECTION"
SOURCE_CAD_GEOMETRY = "cad_geometry"

DEFAULT_MODULE_TYPE = "mechanical"
DEFAULT_COMPONENT_TYPE = "mechanical"
DEFAULT_SUBCOMPONENT_TYPE = "mechanical"


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """One graph node ready for KG insertion."""
    label: str
    id: str
    properties: dict

    def to_dict(self) -> dict:
        return {"label": self.label, "id": self.id, "properties": self.properties}


@dataclass
class Edge:
    """One graph edge ready for KG insertion."""
    type: str
    from_id: str | None
    to_id: str
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "from": self.from_id,
            "to": self.to_id,
            "properties": self.properties,
        }


@dataclass
class TripleSet:
    """All nodes + edges emitted from one extraction run."""
    schema_version: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for n in self.nodes:
            c[f"node:{n.label}"] = c.get(f"node:{n.label}", 0) + 1
        for e in self.edges:
            c[f"edge:{e.type}"] = c.get(f"edge:{e.type}", 0) + 1
        return c


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def _station_id(station_id: str) -> str:
    return f"ST_{station_id}"


def _module_id(nauo_id: int) -> str:
    return f"M_{nauo_id}"


def _component_id(nauo_id: int) -> str:
    return f"C_{nauo_id}"


def _subcomponent_id(nauo_id: int) -> str:
    return f"SC_{nauo_id}"


def _node_id_for(nauo_id: int, depth: int) -> str:
    if depth == 1:
        return _module_id(nauo_id)
    if depth == 2:
        return _component_id(nauo_id)
    return _subcomponent_id(nauo_id)


def _label_for(depth: int) -> str:
    if depth == 1:
        return "Module"
    if depth == 2:
        return "Component"
    return "SubComponent"


# ---------------------------------------------------------------------------
# Tree-flattening helpers
# ---------------------------------------------------------------------------

def _ancestor_module_nauo_id(
    nauo_id: int,
    nauo_depths: dict[int, int],
    canonical_parent_by_product: dict[int, int],
    nauo_to_parent_product: dict[int, int],
) -> str | None:
    """
    Walk up the canonical-NAUO chain and return the M_<nauo> id of the
    depth-1 Module ancestor, or None if the chain breaks.
    """
    cursor = nauo_id
    visited: set[int] = set()
    while True:
        if cursor in visited:
            return None
        visited.add(cursor)
        d = nauo_depths.get(cursor, -1)
        if d <= 0:
            return None
        if d == 1:
            return _module_id(cursor)
        parent_product = nauo_to_parent_product.get(cursor)
        if parent_product is None:
            return None
        parent_nauo = canonical_parent_by_product.get(parent_product)
        if parent_nauo is None:
            return None
        cursor = parent_nauo


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def emit_triples(
    hierarchy: Hierarchy,
    hierarchy_edges: Iterable[HierarchyEdge],
    mates: Iterable[Mate],
    display_names_by_product_id: dict[str, str] | None = None,
    station_id: str | None = None,
    station_type: str | None = None,
) -> TripleSet:
    """
    Build the schema v3.2 {nodes, edges} bundle from one extraction run.

    station_id  — canonical id for the Station node (e.g. the dataset name).
                  When None, derived from the root product's PRODUCT.id.
    station_type — human-readable type label (e.g. root product name). When None,
                   derived from hierarchy.roots[0]'s PRODUCT.name.
    """
    nauo_depths = compute_nauo_depths(hierarchy)
    canonical_parent_by_product = canonical_parent_nauo_by_product(hierarchy)
    nauo_to_parent_product: dict[int, int] = {
        nauo_id: parent_pref
        for parent_pref, _child_pref, nauo_id in hierarchy.nauo_edges
    }

    # Resolve station identity from the STEP root when not provided.
    root_product = None
    if hierarchy.roots:
        root_product = hierarchy.products.get(hierarchy.roots[0])
    if station_id is None:
        station_id = (root_product.id if root_product else "") or "UNKNOWN"
    if station_type is None:
        station_type = (root_product.name if root_product else "") or station_id

    st_node_id = _station_id(station_id)

    ts = TripleSet(schema_version=SCHEMA_VERSION)
    display_names_by_product_id = display_names_by_product_id or {}

    # ---- Station node: one per extraction run ------------------------------
    ts.nodes.append(Node(
        label="Station",
        id=st_node_id,
        properties={
            "station_id": station_id,
            "station_type": station_type,
        },
    ))

    # ---- Nodes: one per resolved NAUO -------------------------------------
    edges_list = list(hierarchy_edges)
    for he in edges_list:
        depth = he.depth
        node_id = _node_id_for(he.nauo_id, depth)
        product = hierarchy.products.get(he.child_product_ref)
        product_id = product.id if product else ""
        name = (
            display_names_by_product_id.get(product_id)
            or (product.name if product else "")
            or product_id
            or node_id
        )

        if depth == 1:
            ts.nodes.append(Node(
                label="Module",
                id=node_id,
                properties={
                    "module_id": node_id,
                    "name": name,
                    "module_type": DEFAULT_MODULE_TYPE,
                    "station_id": station_id,
                },
            ))
        elif depth == 2:
            ancestor_module_id = _ancestor_module_nauo_id(
                he.nauo_id,
                nauo_depths,
                canonical_parent_by_product,
                nauo_to_parent_product,
            )
            ts.nodes.append(Node(
                label="Component",
                id=node_id,
                properties={
                    "component_id": node_id,
                    "name": name,
                    "component_type": DEFAULT_COMPONENT_TYPE,
                    "module_id": ancestor_module_id,
                },
            ))
        else:  # depth >= 3 → SubComponent
            ancestor_module_id = _ancestor_module_nauo_id(
                he.nauo_id,
                nauo_depths,
                canonical_parent_by_product,
                nauo_to_parent_product,
            )
            ts.nodes.append(Node(
                label="SubComponent",
                id=node_id,
                properties={
                    "subcomponent_id": node_id,
                    "name": name,
                    "component_type": DEFAULT_SUBCOMPONENT_TYPE,
                    "module_id": ancestor_module_id,
                },
            ))

    # ---- Hierarchy edges: one per NAUO ------------------------------------
    for he in edges_list:
        depth = he.depth
        child_node_id = _node_id_for(he.nauo_id, depth)

        if depth == 1:
            ts.edges.append(Edge(
                type=EDGE_HAS_MODULE,
                from_id=st_node_id,
                to_id=child_node_id,
            ))
            continue

        parent_nauo_id = canonical_parent_by_product.get(he.parent_product_ref)
        if parent_nauo_id is None:
            continue
        parent_depth = nauo_depths.get(parent_nauo_id, -1)
        if parent_depth <= 0:
            continue
        parent_node_id = _node_id_for(parent_nauo_id, parent_depth)

        edge_type = EDGE_HAS_COMPONENT if depth == 2 else EDGE_HAS_SUBCOMPONENT
        ts.edges.append(Edge(
            type=edge_type,
            from_id=parent_node_id,
            to_id=child_node_id,
        ))

    # ---- HAS_CONNECTION edges from mates ----------------------------------
    for m in mates:
        depth_a = nauo_depths.get(m.nauo_a)
        depth_b = nauo_depths.get(m.nauo_b)
        if depth_a is None or depth_a <= 0 or depth_b is None or depth_b <= 0:
            continue
        from_id = _node_id_for(m.nauo_a, depth_a)
        to_id = _node_id_for(m.nauo_b, depth_b)
        ts.edges.append(Edge(
            type=EDGE_HAS_CONNECTION,
            from_id=from_id,
            to_id=to_id,
            properties={
                "connection_type": m.mate_type,
                "confidence": round(m.confidence, 3),
                "source": SOURCE_CAD_GEOMETRY,
            },
        ))

    return ts
