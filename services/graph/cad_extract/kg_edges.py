"""
Serialize STEP product hierarchy as KG hierarchy edges.

Bridge between the STEP-extracted Hierarchy and the schema v3.2 edges that
the triples emitter will consume:

  HAS_MODULE        Station   -> Module       (depth-1 children of root)
  HAS_COMPONENT     Module    -> Component    (depth-2 children)
  HAS_SUBCOMPONENT  Component -> Component    (depth ≥ 3)

The depth-to-edge-type mapping: a sub-assembly directly under the root is a
Module; everything deeper (sub-sub-assemblies and leaf parts) is a Component.

Each emitted record corresponds to one resolved NAUO — the same instance key
used by the geometry index and mate inference.

Per-NAUO depth invariant
------------------------
Earlier code used BFS-shallowest-depth-per-product. That broke on DAGs where
a sub-assembly is reused at multiple depths: the same product became M_ on one
NAUO and C_ on another, producing HAS_COMPONENT(C_->C_) edges that violate the
schema. Validation surfaced 75 such edges on the Di file.

The fix: depth is computed **per NAUO** via the canonical-parent-NAUO chain.
Each non-root NAUO has a unique canonical parent — the smallest-id NAUO that
introduces its parent product. Depth(root NAUO)=1; for any other NAUO N with
parent product P: Depth(N) = Depth(canonical_NAUO[P]) + 1.

Do not regress this. If you find yourself needing per-product depth, think hard
about whether you actually want per-NAUO depth — usually you do.
"""

from __future__ import annotations

from dataclasses import dataclass

from .hierarchy import Hierarchy


EDGE_HAS_MODULE = "HAS_MODULE"
EDGE_HAS_COMPONENT = "HAS_COMPONENT"
EDGE_HAS_SUBCOMPONENT = "HAS_SUBCOMPONENT"


@dataclass
class HierarchyEdge:
    """One per-NAUO hierarchy edge ready for triple emission."""
    nauo_id: int
    child_product_ref: int
    parent_product_ref: int
    depth: int
    edge_type: str

    def to_dict(self) -> dict:
        return {
            "nauo_id": self.nauo_id,
            "child_product_ref": self.child_product_ref,
            "parent_product_ref": self.parent_product_ref,
            "depth": self.depth,
            "edge_type": self.edge_type,
        }


def _edge_type_for_depth(child_depth: int) -> str:
    if child_depth == 1:
        return EDGE_HAS_MODULE
    if child_depth == 2:
        return EDGE_HAS_COMPONENT
    return EDGE_HAS_SUBCOMPONENT


def canonical_parent_nauo_by_product(h: Hierarchy) -> dict[int, int]:
    """
    For each non-root product, the smallest-id NAUO that introduces it.

    Public because both compute_nauo_depths here and emit_triples in triples.py
    need the same canonical-parent map; building it twice risks drift.
    """
    candidates: dict[int, list[int]] = {}
    for _parent_pref, child_pref, nauo_id in h.nauo_edges:
        candidates.setdefault(child_pref, []).append(nauo_id)
    return {pref: min(nauos) for pref, nauos in candidates.items()}


def compute_nauo_depths(h: Hierarchy) -> dict[int, int]:
    """
    Per-NAUO depth measured along the canonical-parent-NAUO chain.

    Definition:
      - Root NAUO (parent_product_ref ∈ h.roots) → depth 1
      - Otherwise: depth(N) = depth(canonical_NAUO[parent_product]) + 1

    NAUOs whose depth cannot be resolved are returned as -1. That indicates a
    structural defect upstream — the validator will flag any edge referencing
    such a node.
    """
    canonical = canonical_parent_nauo_by_product(h)
    nauo_to_parent_product: dict[int, int] = {
        nauo_id: parent_pref for parent_pref, _child_pref, nauo_id in h.nauo_edges
    }
    roots_set = set(h.roots)
    depth: dict[int, int] = {}

    def resolve(nauo_id: int) -> int:
        # Iterative walk-then-fill; avoids hitting Python's recursion limit on
        # deep assemblies (Di-class: depth 8+, limit 1000 — stay safe).
        chain: list[int] = []
        cursor = nauo_id
        seen: set[int] = set()
        while cursor not in depth:
            if cursor in seen:
                for c in chain + [cursor]:
                    depth[c] = -1
                return -1
            seen.add(cursor)
            parent_product = nauo_to_parent_product.get(cursor)
            if parent_product is None:
                depth[cursor] = -1
                while chain: depth[chain.pop()] = -1
                return -1
            if parent_product in roots_set:
                depth[cursor] = 1
                break
            parent_nauo = canonical.get(parent_product)
            if parent_nauo is None:
                depth[cursor] = -1
                while chain: depth[chain.pop()] = -1
                return -1
            chain.append(cursor)
            cursor = parent_nauo
        d = depth[cursor]
        while chain:
            d += 1
            depth[chain.pop()] = d
        return depth[nauo_id]

    for _, _, nauo_id in h.nauo_edges:
        if nauo_id not in depth:
            resolve(nauo_id)
    return depth


def serialize_hierarchy_edges(h: Hierarchy) -> list[HierarchyEdge]:
    """
    Emit one HierarchyEdge per resolved NAUO, sorted by nauo_id.

    NAUOs whose depth could not be resolved are skipped.
    """
    nauo_depths = compute_nauo_depths(h)
    edges: list[HierarchyEdge] = []
    for parent_pref, child_pref, nauo_id in h.nauo_edges:
        d = nauo_depths.get(nauo_id, -1)
        if d <= 0:
            continue
        edges.append(HierarchyEdge(
            nauo_id=nauo_id,
            child_product_ref=child_pref,
            parent_product_ref=parent_pref,
            depth=d,
            edge_type=_edge_type_for_depth(d),
        ))
    edges.sort(key=lambda e: e.nauo_id)
    return edges
