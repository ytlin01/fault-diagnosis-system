"""
Mate inference from world-space face geometry.

Detects four connection types between pairs of assembly instances:

  planar_contact  — two flat faces are coplanar and facing each other
  concentric      — a cylindrical pin/shaft fits a cylindrical hole (axes
                    aligned, radii match, one convex + one concave face)
  tangent         — a curved face (cylinder/cone/torus) touches a flat face
  proximity       — bounding boxes overlap but no analytic contact found
                    (catch-all for complex surfaces like B-splines)

Two passes are run. First a sibling pass over instances sharing the same
parent NAUO, which captures the bulk of mates cheaply. Second a cousin pass
over AABB-overlapping non-sibling pairs discovered via a uniform spatial
grid, which catches cross-subassembly mates that the sibling rule misses
(e.g. top-level fasteners crossing subassembly boundaries in SolidWorks
top-down assemblies). Mates are tagged scope="sibling" or scope="cousin"
so downstream can distinguish them during debugging.

HAS_CONNECTION semantics: undirected. Every emitted `Mate` satisfies
`nauo_a < nauo_b` (canonical ordering, enforced in `_detect_and_emit_pair`)
and at most one mate exists per `(nauo_a, nauo_b, mate_type)` triple. This
lets the KG export emit one undirected edge per pair-type without de-duping
again, and lets Cypher use `MATCH (x)-[r:HAS_CONNECTION]-(y)` (no arrow).

Config
------
All threshold constants are exposed as module-level defaults (matching
configs/cad_extract.yaml) AND overridable via the `cfg` parameter on
`infer_mates`. CLI entry points must read from yaml and pass `cfg`; calling
code must not hardcode any threshold.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

from .config import MateInferenceConfig
from .geometry import InstanceGeometry, Vec3, WorldFace
from .hierarchy import Hierarchy

# ---------------------------------------------------------------------------
# Module-level defaults — must stay in sync with configs/cad_extract.yaml.
# These exist so the detectors can reference named constants; runtime values
# come from MateInferenceConfig passed to infer_mates().
# ---------------------------------------------------------------------------

MAX_SIBLINGS_PER_PARENT: int = 100
MAX_TOTAL_PAIRS: int = 200_000
MAX_COUSIN_PAIRS: int = 100_000
SPATIAL_GRID_CELL_MM: float = 100.0
MAX_PLANES_PER_INSTANCE: int = 60
MAX_CYLS_PER_INSTANCE: int = 40
MAX_MATES_PER_INSTANCE_PER_TYPE: int = 50
MATE_CONFIDENCE_THRESHOLD: float = 0.5

# Geometric tolerances (all in mm). Also in yaml; override via cfg.
PLANE_DIST_TOL: float = 0.05
PLANE_NORMAL_TOL: float = 0.01
AXIS_PARALLEL_TOL: float = 0.01
AXIS_OFFSET_TOL: float = 0.05
RADIUS_REL_TOL: float = 0.02
AABB_TOL: float = 1.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Mate:
    """One detected connection between two assembly instances.

    HAS_CONNECTION is **undirected** — `(a, b)` and `(b, a)` describe the same
    physical contact. Canonical ordering: `nauo_a < nauo_b` always (enforced in
    `_detect_and_emit_pair`). Cypher should use `MATCH (x)-[r:HAS_CONNECTION]-(y)`
    (no arrow).

    The `_a` / `_b` suffix on product fields tracks which instance the
    `detail` string was measured against; it does not imply a role.
    """
    nauo_a: int
    nauo_b: int
    product_name_a: str
    product_id_a: str
    product_name_b: str
    product_id_b: str
    mate_type: str      # planar_contact | concentric | tangent | proximity
    confidence: float   # 0.0 – 1.0
    detail: str = ""
    scope: str = "sibling"  # "sibling" | "cousin"

    def to_dict(self) -> dict:
        return {
            "part_a": self.product_id_a or self.product_name_a,
            "part_b": self.product_id_b or self.product_name_b,
            "type":   self.mate_type,
            "confidence": round(self.confidence, 3),
            "detail": self.detail,
            "scope":  self.scope,
            "nauo_a": self.nauo_a,
            "nauo_b": self.nauo_b,
        }


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------

def _aabbs_overlap(
    min_a: Vec3, max_a: Vec3,
    min_b: Vec3, max_b: Vec3,
    tol: float = AABB_TOL,
) -> bool:
    return (
        min_a.x - tol <= max_b.x and max_a.x + tol >= min_b.x and
        min_a.y - tol <= max_b.y and max_a.y + tol >= min_b.y and
        min_a.z - tol <= max_b.z and max_a.z + tol >= min_b.z
    )


def _aabb_overlap_ratio(
    min_a: Vec3, max_a: Vec3,
    min_b: Vec3, max_b: Vec3,
) -> float:
    """Fractional AABB intersection: intersection_volume / min(vol_a, vol_b)."""
    ix = min(max_a.x, max_b.x) - max(min_a.x, min_b.x)
    iy = min(max_a.y, max_b.y) - max(min_a.y, min_b.y)
    iz = min(max_a.z, max_b.z) - max(min_a.z, min_b.z)
    if ix <= 0.0 or iy <= 0.0 or iz <= 0.0:
        return 0.0
    i_vol = ix * iy * iz
    vol_a = (max_a.x - min_a.x) * (max_a.y - min_a.y) * (max_a.z - min_a.z)
    vol_b = (max_b.x - min_b.x) * (max_b.y - min_b.y) * (max_b.z - min_b.z)
    denom = max(min(vol_a, vol_b), 1e-9)
    return min(i_vol / denom, 1.0)


def _axis_line_distance(
    origin_a: Vec3, axis_a: Vec3,
    origin_b: Vec3, axis_b: Vec3,
) -> float:
    """Shortest distance between two infinite lines defined by (origin, direction)."""
    w = origin_a - origin_b
    cross = axis_a.cross(axis_b)
    denom = cross.length()
    if denom < 1e-10:
        return axis_a.cross(w).length()
    return abs(w.dot(cross)) / denom


# ---------------------------------------------------------------------------
# Contact detectors
# ---------------------------------------------------------------------------

def _check_planar(
    faces_a: list[WorldFace],
    faces_b: list[WorldFace],
) -> list[tuple[float, str]]:
    """Return (confidence, detail) for every planar-contact pair found."""
    planes_a = [f for f in faces_a if f.surface_type == "PLANE"]
    planes_b = [f for f in faces_b if f.surface_type == "PLANE"]
    hits: list[tuple[float, str]] = []

    for fa in planes_a:
        na = fa.axis if fa.same_sense else Vec3(-fa.axis.x, -fa.axis.y, -fa.axis.z)
        for fb in planes_b:
            nb = fb.axis if fb.same_sense else Vec3(-fb.axis.x, -fb.axis.y, -fb.axis.z)
            dot = na.dot(nb)
            if dot > -(1.0 - PLANE_NORMAL_TOL):
                continue
            dist = abs((fb.origin - fa.origin).dot(na))
            if dist < PLANE_DIST_TOL:
                dist_score   = 1.0 - dist / PLANE_DIST_TOL
                normal_score = (-dot - (1.0 - PLANE_NORMAL_TOL)) / PLANE_NORMAL_TOL
                conf = 0.5 + 0.25 * dist_score + 0.25 * normal_score
                detail = (f"dist={dist:.4f}mm dot={dot:.4f} "
                          f"normal=({na.x:.2f},{na.y:.2f},{na.z:.2f})")
                hits.append((conf, detail))
    return hits


def _check_concentric(
    faces_a: list[WorldFace],
    faces_b: list[WorldFace],
) -> list[tuple[float, str]]:
    """Return (confidence, detail) for every concentric cylindrical pair."""
    cyls_a = [f for f in faces_a if f.surface_type == "CYLINDRICAL_SURFACE" and f.radius]
    cyls_b = [f for f in faces_b if f.surface_type == "CYLINDRICAL_SURFACE" and f.radius]
    hits: list[tuple[float, str]] = []

    for fa in cyls_a:
        for fb in cyls_b:
            r_max = max(fa.radius, fb.radius)
            r_err = abs(fa.radius - fb.radius) / r_max
            if r_err > RADIUS_REL_TOL:
                continue
            cross_len = fa.axis.cross(fb.axis).length()
            if cross_len > AXIS_PARALLEL_TOL:
                continue
            offset = _axis_line_distance(fa.origin, fa.axis, fb.origin, fb.axis)
            if offset > AXIS_OFFSET_TOL:
                continue
            r_score    = 1.0 - r_err / RADIUS_REL_TOL
            axis_score = 1.0 - offset / AXIS_OFFSET_TOL
            sense_bonus = 0.1 if (fa.same_sense != fb.same_sense) else 0.0
            conf = 0.7 + 0.1 * r_score + 0.1 * axis_score + sense_bonus
            detail = (f"r={fa.radius:.3f}mm offset={offset:.4f}mm "
                      f"r_err={r_err:.4f} "
                      f"{'pin-hole' if fa.same_sense != fb.same_sense else 'same-sense'}")
            hits.append((conf, detail))
    return hits


def _check_tangent(
    faces_a: list[WorldFace],
    faces_b: list[WorldFace],
) -> list[tuple[float, str]]:
    """Detect tangent contact: a cylinder/cone touching a flat plane."""
    curved_types = {"CYLINDRICAL_SURFACE", "CONICAL_SURFACE", "SPHERICAL_SURFACE"}
    hits: list[tuple[float, str]] = []

    AXIS_TO_NORMAL_TOL = 0.1
    TANGENCY_DIST_TOL  = PLANE_DIST_TOL + 0.1

    def _check_cyl_plane(cyls: list[WorldFace], planes: list[WorldFace]) -> None:
        for fc in cyls:
            if fc.radius is None:
                continue
            for fp in planes:
                pn = fp.axis if fp.same_sense else Vec3(-fp.axis.x, -fp.axis.y, -fp.axis.z)
                axis_dot_normal = abs(fc.axis.dot(pn))
                if axis_dot_normal > AXIS_TO_NORMAL_TOL:
                    continue
                dist_axis_to_plane = abs((fc.origin - fp.origin).dot(pn))
                dist_err = abs(dist_axis_to_plane - fc.radius)
                if dist_err < TANGENCY_DIST_TOL:
                    axis_score = 1.0 - axis_dot_normal / AXIS_TO_NORMAL_TOL
                    dist_score = 1.0 - dist_err / TANGENCY_DIST_TOL
                    conf = 0.5 + 0.25 * axis_score + 0.25 * dist_score
                    detail = (f"r={fc.radius:.3f}mm "
                              f"dist_axis={dist_axis_to_plane:.4f}mm "
                              f"axis·n={axis_dot_normal:.4f}")
                    hits.append((conf, detail))

    cyls_a  = [f for f in faces_a if f.surface_type in curved_types]
    planes_b = [f for f in faces_b if f.surface_type == "PLANE"]
    cyls_b  = [f for f in faces_b if f.surface_type in curved_types]
    planes_a = [f for f in faces_a if f.surface_type == "PLANE"]
    _check_cyl_plane(cyls_a, planes_b)
    _check_cyl_plane(cyls_b, planes_a)
    return hits


# ---------------------------------------------------------------------------
# Spatial index — used by the cousin pass
# ---------------------------------------------------------------------------

class _SpatialGrid:
    """Uniform 3D grid for AABB-overlap candidate lookup in the cousin pass."""

    def __init__(self, cell_size: float):
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)

    def _coords(self, p: Vec3) -> tuple[int, int, int]:
        cs = self.cell_size
        return (int(math.floor(p.x / cs)),
                int(math.floor(p.y / cs)),
                int(math.floor(p.z / cs)))

    def insert(self, nauo_id: int, aabb_min: Vec3, aabb_max: Vec3) -> None:
        cmin = self._coords(aabb_min)
        cmax = self._coords(aabb_max)
        for x in range(cmin[0], cmax[0] + 1):
            for y in range(cmin[1], cmax[1] + 1):
                for z in range(cmin[2], cmax[2] + 1):
                    self.cells[(x, y, z)].append(nauo_id)

    def query(self, aabb_min: Vec3, aabb_max: Vec3) -> set[int]:
        cmin = self._coords(aabb_min)
        cmax = self._coords(aabb_max)
        out: set[int] = set()
        for x in range(cmin[0], cmax[0] + 1):
            for y in range(cmin[1], cmax[1] + 1):
                for z in range(cmin[2], cmax[2] + 1):
                    bucket = self.cells.get((x, y, z))
                    if bucket:
                        out.update(bucket)
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capped_faces(
    faces: list[WorldFace],
    max_planes: int = MAX_PLANES_PER_INSTANCE,
    max_cyls: int = MAX_CYLS_PER_INSTANCE,
) -> list[WorldFace]:
    """Cap face list to avoid O(F_a × F_b) blowup on complex parts."""
    planes: list[WorldFace] = []
    cyls:   list[WorldFace] = []
    other:  list[WorldFace] = []
    for f in faces:
        if f.surface_type == "PLANE":
            if len(planes) < max_planes:
                planes.append(f)
        elif f.surface_type == "CYLINDRICAL_SURFACE":
            if len(cyls) < max_cyls:
                cyls.append(f)
        else:
            other.append(f)
    return planes + cyls + other


def _detect_and_emit_pair(
    id_a: int, id_b: int,
    inst_a: InstanceGeometry, inst_b: InstanceGeometry,
    mates: list[Mate],
    scope: str,
    max_planes: int = MAX_PLANES_PER_INSTANCE,
    max_cyls: int = MAX_CYLS_PER_INSTANCE,
    aabb_tol: float = AABB_TOL,
) -> None:
    """
    Run the full detector stack on one pair and append mates to the list.

    Enforces the HAS_CONNECTION canonical ordering invariant `nauo_a < nauo_b`
    by swapping the inputs upfront. Detectors are symmetric, so swapping only
    changes which side `detail` reports its measurements from.
    """
    if id_a > id_b:
        id_a, id_b = id_b, id_a
        inst_a, inst_b = inst_b, inst_a

    if not inst_a.faces or not inst_b.faces:
        return
    if (inst_a.aabb_min is not None and inst_b.aabb_min is not None and
            not _aabbs_overlap(
                inst_a.aabb_min, inst_a.aabb_max,
                inst_b.aabb_min, inst_b.aabb_max,
                tol=aabb_tol)):
        return

    fa = _capped_faces(inst_a.faces, max_planes, max_cyls)
    fb = _capped_faces(inst_b.faces, max_planes, max_cyls)

    emitted_any = False
    emitted_types: set[str] = set()
    for detector, mate_type in (
        (_check_planar,     "planar_contact"),
        (_check_concentric, "concentric"),
        (_check_tangent,    "tangent"),
    ):
        hits = detector(fa, fb)
        if not hits:
            continue
        # Tangent is a weak signal — suppress it when a stronger geometric
        # contact (planar or concentric) was already found for this pair.
        if mate_type == "tangent" and emitted_types & {"planar_contact", "concentric"}:
            continue
        best_conf, best_detail = max(hits, key=lambda h: h[0])
        mates.append(Mate(
            nauo_a=id_a,
            nauo_b=id_b,
            product_name_a=inst_a.product_name,
            product_id_a=inst_a.product_id_str,
            product_name_b=inst_b.product_name,
            product_id_b=inst_b.product_id_str,
            mate_type=mate_type,
            confidence=best_conf,
            detail=best_detail,
            scope=scope,
        ))
        emitted_any = True
        emitted_types.add(mate_type)

    if (not emitted_any and
            inst_a.aabb_min is not None and inst_b.aabb_min is not None and
            _aabbs_overlap(
                inst_a.aabb_min, inst_a.aabb_max,
                inst_b.aabb_min, inst_b.aabb_max,
                tol=0.0)):
        ratio = _aabb_overlap_ratio(
            inst_a.aabb_min, inst_a.aabb_max,
            inst_b.aabb_min, inst_b.aabb_max,
        )
        conf = 0.2 + 0.4 * ratio
        mates.append(Mate(
            nauo_a=id_a,
            nauo_b=id_b,
            product_name_a=inst_a.product_name,
            product_id_a=inst_a.product_id_str,
            product_name_b=inst_b.product_name,
            product_id_b=inst_b.product_id_str,
            mate_type="proximity",
            confidence=conf,
            detail=f"AABB overlap ratio={ratio:.3f}",
            scope=scope,
        ))


def _cap_mates_per_instance_degree(
    mates: list[Mate],
    max_per_instance_per_type: int,
) -> list[Mate]:
    """
    Trim each (instance, mate_type) bucket to its top-K highest-confidence mates.

    A mate survives only if it is in the top-K of BOTH endpoints for its type.
    This guarantees per-instance degree is bounded. Set max_per_instance_per_type=0
    to disable.
    """
    if max_per_instance_per_type <= 0 or not mates:
        return mates

    by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    for idx, m in enumerate(mates):
        by_key[(m.nauo_a, m.mate_type)].append(idx)
        by_key[(m.nauo_b, m.mate_type)].append(idx)

    survivors: dict[tuple[int, str], set[int]] = {}
    capped_buckets = 0
    for key, idxs in by_key.items():
        if len(idxs) <= max_per_instance_per_type:
            survivors[key] = set(idxs)
            continue
        idxs.sort(key=lambda i: (-mates[i].confidence, i))
        survivors[key] = set(idxs[:max_per_instance_per_type])
        capped_buckets += 1

    keep: list[Mate] = []
    for idx, m in enumerate(mates):
        if (idx in survivors[(m.nauo_a, m.mate_type)]
                and idx in survivors[(m.nauo_b, m.mate_type)]):
            keep.append(m)

    if capped_buckets:
        log.info(
            "  [mates] degree cap: %d (instance, type) bucket(s) over top-%d "
            "→ %d → %d mates",
            capped_buckets, max_per_instance_per_type, len(mates), len(keep),
        )
    return keep


# ---------------------------------------------------------------------------
# Main inference entry point
# ---------------------------------------------------------------------------

def infer_mates(
    instances: dict[int, InstanceGeometry],
    hierarchy: Hierarchy,
    cfg: MateInferenceConfig | None = None,
) -> list[Mate]:
    """
    Detect mates between instance pairs.

    Pass ``cfg`` (from ``get_config().mate``) so CLI scripts drive all thresholds
    from configs/cad_extract.yaml. When cfg is None the module-level defaults
    apply; this path is used by unit tests that don't need yaml.

    Two passes:
      1. Sibling pass — pairs sharing the same parent NAUO.
      2. Cousin pass — non-sibling AABB-overlapping pairs via spatial grid.

    Post-filters: per-instance degree cap then confidence floor.
    """
    # Resolve effective config values from cfg or module-level defaults.
    _max_siblings    = cfg.max_siblings_per_parent       if cfg else MAX_SIBLINGS_PER_PARENT
    _max_total       = cfg.max_total_pairs               if cfg else MAX_TOTAL_PAIRS
    _max_cousin      = cfg.max_cousin_pairs              if cfg else MAX_COUSIN_PAIRS
    _cell_mm         = cfg.spatial_grid_cell_mm          if cfg else SPATIAL_GRID_CELL_MM
    _max_planes      = cfg.max_planes_per_instance       if cfg else MAX_PLANES_PER_INSTANCE
    _max_cyls        = cfg.max_cyls_per_instance         if cfg else MAX_CYLS_PER_INSTANCE
    _degree_cap      = cfg.max_mates_per_instance_per_type if cfg else MAX_MATES_PER_INSTANCE_PER_TYPE
    _conf_threshold  = cfg.mate_confidence_threshold     if cfg else MATE_CONFIDENCE_THRESHOLD
    _aabb_tol        = cfg.aabb_tol                      if cfg else AABB_TOL

    parent_to_children: dict[int, list[int]] = defaultdict(list)
    for nauo_id, inst in instances.items():
        parent_to_children[inst.parent_product_ref].append(nauo_id)

    t0 = time.perf_counter()
    mates: list[Mate] = []
    checked_pairs: set[frozenset] = set()
    total_pairs = 0
    skipped_parents = 0

    # ---- Sibling pass ------------------------------------------------------
    for parent_ref, children in parent_to_children.items():
        original_count = len(children)
        if original_count > _max_siblings:
            skipped_parents += 1
            children = children[:_max_siblings]

        if total_pairs >= _max_total:
            break

        parent_name = hierarchy.products.get(parent_ref)
        log.debug(
            "  [mates] parent #%d (%s): %d children%s → %d pairs",
            parent_ref,
            parent_name.name if parent_name else "?",
            original_count,
            f" (capped to {_max_siblings})" if original_count > _max_siblings else "",
            len(children) * (len(children) - 1) // 2,
        )

        for i in range(len(children)):
            for j in range(i + 1, len(children)):
                if total_pairs >= _max_total:
                    break
                total_pairs += 1
                id_a = children[i]
                id_b = children[j]
                pair_key = frozenset((id_a, id_b))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                _detect_and_emit_pair(
                    id_a, id_b,
                    instances[id_a], instances[id_b],
                    mates,
                    scope="sibling",
                    max_planes=_max_planes,
                    max_cyls=_max_cyls,
                    aabb_tol=_aabb_tol,
                )

    sibling_elapsed = time.perf_counter() - t0
    sibling_mate_count = len(mates)
    log.info("  [mates] sibling pass: %d pairs checked, %d mates  (%.2fs)",
             total_pairs, sibling_mate_count, sibling_elapsed)
    if skipped_parents:
        log.warning("  [mates] %d parent(s) had >%d siblings — truncated.",
                    skipped_parents, _max_siblings)
    if total_pairs >= _max_total:
        log.warning("  [mates] sibling pass hit MAX_TOTAL_PAIRS=%d cap.", _max_total)

    # ---- Cousin pass -------------------------------------------------------
    t1 = time.perf_counter()
    grid = _SpatialGrid(cell_size=_cell_mm)
    for nauo_id, inst in instances.items():
        if inst.aabb_min is None or inst.aabb_max is None:
            continue
        grid.insert(nauo_id, inst.aabb_min, inst.aabb_max)

    cousin_pairs = 0
    cousin_mates_before = len(mates)
    hit_cousin_cap = False

    for id_a, inst_a in instances.items():
        if cousin_pairs >= _max_cousin:
            hit_cousin_cap = True
            break
        if inst_a.aabb_min is None or inst_a.aabb_max is None:
            continue
        candidates = grid.query(inst_a.aabb_min, inst_a.aabb_max)
        for id_b in candidates:
            if id_b <= id_a:
                continue
            pair_key = frozenset((id_a, id_b))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)
            cousin_pairs += 1
            if cousin_pairs >= _max_cousin:
                hit_cousin_cap = True
                break
            _detect_and_emit_pair(
                id_a, id_b,
                inst_a, instances[id_b],
                mates,
                scope="cousin",
                max_planes=_max_planes,
                max_cyls=_max_cyls,
                aabb_tol=_aabb_tol,
            )

    cousin_elapsed = time.perf_counter() - t1
    cousin_mate_count = len(mates) - cousin_mates_before
    log.info("  [mates] cousin pass: %d pairs checked, %d mates  (%.2fs)",
             cousin_pairs, cousin_mate_count, cousin_elapsed)
    if hit_cousin_cap:
        log.warning("  [mates] cousin pass hit MAX_COUSIN_PAIRS=%d cap.", _max_cousin)

    # Post-filter 1: per-instance degree cap
    mates = _cap_mates_per_instance_degree(mates, _degree_cap)

    # Post-filter 2: confidence floor (applied after cap so cap ranks the full pool)
    if _conf_threshold > 0.0:
        before = len(mates)
        mates = [m for m in mates if m.confidence >= _conf_threshold]
        dropped = before - len(mates)
        if dropped:
            log.info(
                "  [mates] confidence floor: dropped %d edge(s) below %.2f → %d mates",
                dropped, _conf_threshold, len(mates),
            )

    log.info("  [mates] total: %d mates  (%.2fs)", len(mates), time.perf_counter() - t0)
    return mates
