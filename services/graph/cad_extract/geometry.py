"""
Geometry extraction from STEP entities.

Parses AXIS2_PLACEMENT_3D, PLANE, CYLINDRICAL_SURFACE (and friends) and builds
world-space face geometry per assembly instance (NAUO), ready for mate inference.

Instance-placement chain (SolidWorks flat-export pattern — all transforms are
directly in world space, no composition needed):

  NAUO
  -> PRODUCT_DEFINITION_SHAPE         (field[2] = #nauo_id)
  -> CONTEXT_DEPENDENT_SHAPE_REPR.    (field[1]  = #pds_id)
  -> compound entity (field[0]):  REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#idt_id)
  -> ITEM_DEFINED_TRANSFORMATION      (field[2]  = #placement_axis_id)
  -> AXIS2_PLACEMENT_3D               -> Frame in world space

Part-geometry chain:

  PRODUCT_DEFINITION
  -> PRODUCT_DEFINITION_SHAPE         (field[2] = #pd_id, where entity type is PD not NAUO)
  -> SHAPE_DEFINITION_REPRESENTATION  (field[0] = #pds_id, field[1] = #absr_id)
  -> ADVANCED_BREP_SHAPE_REPR.        (items include #brep_id)
  -> MANIFOLD_SOLID_BREP              (field[1] = #shell_id)
  -> CLOSED_SHELL                     (field[1] = [#face_id, ...])
  -> ADVANCED_FACE                    (field[2] = #surface_id, field[3] = same_sense)
  -> PLANE / CYLINDRICAL_SURFACE /... (field[1] = #placement_id)
  -> AXIS2_PLACEMENT_3D               (field[1] = #pt, field[2] = #z_dir, field[3] = #x_dir)
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

from .hierarchy import Hierarchy
from .parser import Entity, split_args, as_ref, unquote


# ---------------------------------------------------------------------------
# Vector / Frame math (pure Python — no numpy dependency)
# ---------------------------------------------------------------------------

@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, o: Vec3) -> Vec3:  return Vec3(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o: Vec3) -> Vec3:  return Vec3(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, s: float) -> Vec3: return Vec3(self.x*s, self.y*s, self.z*s)
    def __neg__(self) -> Vec3:           return Vec3(-self.x, -self.y, -self.z)
    def dot(self, o: Vec3) -> float:     return self.x*o.x + self.y*o.y + self.z*o.z
    def cross(self, o: Vec3) -> Vec3:
        return Vec3(
            self.y*o.z - self.z*o.y,
            self.z*o.x - self.x*o.z,
            self.x*o.y - self.y*o.x,
        )
    def length_sq(self) -> float: return self.x**2 + self.y**2 + self.z**2
    def length(self) -> float:    return math.sqrt(self.length_sq())
    def normalize(self) -> Vec3:
        n = self.length()
        return Vec3(self.x/n, self.y/n, self.z/n) if n > 1e-12 else Vec3(0.0, 0.0, 1.0)
    def __repr__(self) -> str:
        return f"Vec3({self.x:.4g}, {self.y:.4g}, {self.z:.4g})"


@dataclass
class Frame:
    """Decoded AXIS2_PLACEMENT_3D: origin + orthonormal basis."""
    placement_id: int
    origin: Vec3
    z_axis: Vec3   # surface normal / cylinder axis
    x_axis: Vec3   # reference direction
    y_axis: Vec3   # derived: z_axis × x_axis


# ---------------------------------------------------------------------------
# Surface / Face geometry descriptors
# ---------------------------------------------------------------------------

SUPPORTED_SURFACE_TYPES = frozenset({
    "PLANE",
    "CYLINDRICAL_SURFACE",
    "CONICAL_SURFACE",
    "TOROIDAL_SURFACE",
    "SPHERICAL_SURFACE",
})


@dataclass
class SurfaceGeom:
    """Geometry of one analytical surface in its own local frame."""
    surface_id: int
    surface_type: str   # one of SUPPORTED_SURFACE_TYPES
    placement_id: int   # -> Frame
    radius: float | None = None
    half_angle: float | None = None
    minor_radius: float | None = None


@dataclass
class WorldFace:
    """
    One ADVANCED_FACE with its geometry already transformed to world space.
    This is what the mate-inference code consumes.
    """
    face_id: int
    surface_type: str
    origin: Vec3    # world-space point on the surface (from placement origin)
    axis: Vec3      # world-space z_axis of the placement (= outward normal for planes,
                    # cylinder / cone axis for curved surfaces)
    radius: float | None
    same_sense: bool  # .T. = face outward normal agrees with surface z_axis


@dataclass
class InstanceGeometry:
    """World-space face geometry for one NAUO instance."""
    nauo_id: int
    product_ref: int
    parent_product_ref: int
    product_name: str
    product_id_str: str
    faces: list[WorldFace] = field(default_factory=list)
    aabb_min: Vec3 | None = None
    aabb_max: Vec3 | None = None


# Type alias used by every helper below.
ByType = dict[str, list[Entity]]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_float_list(raw: str) -> list[float]:
    inner = raw.strip().lstrip("(").rstrip(")")
    return [float(tok.strip()) for tok in inner.split(",") if tok.strip()]


def _parse_cartesian_points(by_type: ByType) -> dict[int, Vec3]:
    pts: dict[int, Vec3] = {}
    for e in by_type.get("CARTESIAN_POINT", []):
        args = split_args(e.raw_params)
        if len(args) < 2:
            continue
        try:
            coords = _parse_float_list(args[1])
            if len(coords) >= 3:
                pts[e.id] = Vec3(coords[0], coords[1], coords[2])
        except (ValueError, IndexError):
            pass
    return pts


def _parse_directions(by_type: ByType) -> dict[int, Vec3]:
    dirs: dict[int, Vec3] = {}
    for e in by_type.get("DIRECTION", []):
        args = split_args(e.raw_params)
        if len(args) < 2:
            continue
        try:
            ratios = _parse_float_list(args[1])
            if len(ratios) >= 3:
                dirs[e.id] = Vec3(ratios[0], ratios[1], ratios[2]).normalize()
        except (ValueError, IndexError):
            pass
    return dirs


def _parse_placements(
    by_type: ByType,
    pts: dict[int, Vec3],
    dirs: dict[int, Vec3],
) -> dict[int, Frame]:
    frames: dict[int, Frame] = {}
    for e in by_type.get("AXIS2_PLACEMENT_3D", []):
        args = split_args(e.raw_params)
        if len(args) < 4:
            continue
        pt_ref  = as_ref(args[1])
        z_ref   = as_ref(args[2])
        x_ref   = as_ref(args[3])
        if pt_ref is None or z_ref is None or x_ref is None:
            continue
        origin = pts.get(pt_ref)
        z_axis = dirs.get(z_ref)
        x_axis = dirs.get(x_ref)
        if origin is None or z_axis is None or x_axis is None:
            continue
        y_axis = z_axis.cross(x_axis).normalize()
        frames[e.id] = Frame(
            placement_id=e.id,
            origin=origin,
            z_axis=z_axis,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    return frames


def _parse_surface_geometries(
    by_type: ByType,
    placements: dict[int, Frame],
) -> dict[int, SurfaceGeom]:
    surfaces: dict[int, SurfaceGeom] = {}
    for surf_type in SUPPORTED_SURFACE_TYPES:
        for e in by_type.get(surf_type, []):
            args = split_args(e.raw_params)
            if len(args) < 2:
                continue
            placement_ref = as_ref(args[1])
            if placement_ref is None or placement_ref not in placements:
                continue
            radius = half_angle = minor_radius = None
            if e.name == "CYLINDRICAL_SURFACE":
                if len(args) >= 3:
                    try: radius = float(args[2])
                    except ValueError: pass
            elif e.name == "CONICAL_SURFACE":
                if len(args) >= 4:
                    try: radius = float(args[2]); half_angle = float(args[3])
                    except ValueError: pass
            elif e.name == "TOROIDAL_SURFACE":
                if len(args) >= 4:
                    try: radius = float(args[2]); minor_radius = float(args[3])
                    except ValueError: pass
            elif e.name == "SPHERICAL_SURFACE":
                if len(args) >= 3:
                    try: radius = float(args[2])
                    except ValueError: pass
            surfaces[e.id] = SurfaceGeom(
                surface_id=e.id,
                surface_type=e.name,
                placement_id=placement_ref,
                radius=radius,
                half_angle=half_angle,
                minor_radius=minor_radius,
            )
    return surfaces


def _parse_face_to_surface(by_type: ByType) -> dict[int, tuple[int, bool]]:
    result: dict[int, tuple[int, bool]] = {}
    for e in by_type.get("ADVANCED_FACE", []):
        args = split_args(e.raw_params)
        if len(args) < 4:
            continue
        surf_ref = as_ref(args[2])
        if surf_ref is None:
            continue
        same_sense = args[3].strip() == ".T."
        result[e.id] = (surf_ref, same_sense)
    return result


def _build_shell_to_faces(by_type: ByType) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for shell_type in ("CLOSED_SHELL", "OPEN_SHELL", "ORIENTED_CLOSED_SHELL"):
        for e in by_type.get(shell_type, []):
            args = split_args(e.raw_params)
            if len(args) < 2:
                continue
            items_raw = args[1].strip().lstrip("(").rstrip(")")
            face_ids = []
            for tok in items_raw.split(","):
                ref = as_ref(tok.strip())
                if ref is not None:
                    face_ids.append(ref)
            result[e.id] = face_ids
    return result


def _build_brep_to_shell(by_type: ByType) -> dict[int, int]:
    result: dict[int, int] = {}
    for brep_type in ("MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS"):
        for e in by_type.get(brep_type, []):
            args = split_args(e.raw_params)
            if len(args) < 2:
                continue
            shell_ref = as_ref(args[1])
            if shell_ref is not None:
                result[e.id] = shell_ref
    return result


def _build_absr_to_breps(by_type: ByType) -> dict[int, list[int]]:
    brep_ids: set[int] = {
        e.id
        for bt in ("MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS")
        for e in by_type.get(bt, [])
    }
    result: dict[int, list[int]] = {}
    for e in by_type.get("ADVANCED_BREP_SHAPE_REPRESENTATION", []):
        args = split_args(e.raw_params)
        if len(args) < 2:
            continue
        items_raw = args[1].strip().lstrip("(").rstrip(")")
        breps = []
        for tok in items_raw.split(","):
            ref = as_ref(tok.strip())
            if ref is not None and ref in brep_ids:
                breps.append(ref)
        if breps:
            result[e.id] = breps
    return result


def _build_pd_to_face_ids(
    by_type: ByType,
    face_to_surf: dict[int, tuple[int, bool]],
    surface_geoms: dict[int, SurfaceGeom],
) -> dict[int, list[int]]:
    """Walk PD -> PDS -> SDR -> ABSR -> BREP -> SHELL -> FACE chain."""
    pd_ids: set[int] = {e.id for e in by_type.get("PRODUCT_DEFINITION", [])}

    pd_to_pds: dict[int, int] = {}
    for e in by_type.get("PRODUCT_DEFINITION_SHAPE", []):
        args = split_args(e.raw_params)
        if len(args) < 3:
            continue
        ref = as_ref(args[2])
        if ref is not None and ref in pd_ids:
            pd_to_pds[ref] = e.id

    pds_to_sr: dict[int, int] = {}
    sr_ids: set[int] = {e.id for e in by_type.get("SHAPE_REPRESENTATION", [])}
    absr_ids: set[int] = {e.id for e in by_type.get("ADVANCED_BREP_SHAPE_REPRESENTATION", [])}
    for e in by_type.get("SHAPE_DEFINITION_REPRESENTATION", []):
        args = split_args(e.raw_params)
        if len(args) < 2:
            continue
        pds_ref = as_ref(args[0])
        sr_ref  = as_ref(args[1])
        if pds_ref is not None and sr_ref is not None and sr_ref in sr_ids:
            pds_to_sr[pds_ref] = sr_ref

    sr_to_absr: dict[int, int] = {}
    for e in by_type.get("SHAPE_REPRESENTATION_RELATIONSHIP", []):
        args = split_args(e.raw_params)
        if len(args) < 4:
            continue
        sr_ref   = as_ref(args[2])
        absr_ref = as_ref(args[3])
        if sr_ref is not None and absr_ref is not None and absr_ref in absr_ids:
            sr_to_absr[sr_ref] = absr_ref

    pds_to_absr: dict[int, int] = {
        pds: sr_to_absr[sr]
        for pds, sr in pds_to_sr.items()
        if sr in sr_to_absr
    }

    absr_to_breps = _build_absr_to_breps(by_type)
    brep_to_shell = _build_brep_to_shell(by_type)
    shell_to_faces = _build_shell_to_faces(by_type)

    pd_to_faces: dict[int, list[int]] = {}
    for pd_id, pds_id in pd_to_pds.items():
        absr_id = pds_to_absr.get(pds_id)
        if absr_id is None:
            continue
        face_ids: list[int] = []
        for brep_id in absr_to_breps.get(absr_id, []):
            shell_id = brep_to_shell.get(brep_id)
            if shell_id is None:
                continue
            for fid in shell_to_faces.get(shell_id, []):
                if fid in face_to_surf and face_to_surf[fid][0] in surface_geoms:
                    face_ids.append(fid)
        if face_ids:
            pd_to_faces[pd_id] = face_ids
    return pd_to_faces


def _build_nauo_to_placement(
    by_type: ByType,
    rr_transforms: dict[int, int],
    placements: dict[int, Frame],
) -> dict[int, int]:
    """Return {nauo_id: placement_id} by walking NAUO -> PDS -> CDSR -> IDT -> placement."""
    nauo_ids: set[int] = {e.id for e in by_type.get("NEXT_ASSEMBLY_USAGE_OCCURRENCE", [])}

    nauo_to_pds: dict[int, int] = {}
    for e in by_type.get("PRODUCT_DEFINITION_SHAPE", []):
        args = split_args(e.raw_params)
        if len(args) < 3:
            continue
        ref = as_ref(args[2])
        if ref is not None and ref in nauo_ids:
            nauo_to_pds[ref] = e.id

    pds_to_compound: dict[int, int] = {}
    for e in by_type.get("CONTEXT_DEPENDENT_SHAPE_REPRESENTATION", []):
        args = split_args(e.raw_params)
        if len(args) < 2:
            continue
        compound_ref = as_ref(args[0])
        pds_ref      = as_ref(args[1])
        if compound_ref is not None and pds_ref is not None:
            pds_to_compound[pds_ref] = compound_ref

    idt_to_placement: dict[int, int] = {}
    for e in by_type.get("ITEM_DEFINED_TRANSFORMATION", []):
        args = split_args(e.raw_params)
        if len(args) < 3:
            continue
        placement_ref = as_ref(args[2])
        if placement_ref is not None and placement_ref in placements:
            idt_to_placement[e.id] = placement_ref

    nauo_to_placement: dict[int, int] = {}
    for nauo_id, pds_id in nauo_to_pds.items():
        compound_id = pds_to_compound.get(pds_id)
        if compound_id is None:
            continue
        idt_id = rr_transforms.get(compound_id)
        if idt_id is None:
            continue
        placement_id = idt_to_placement.get(idt_id)
        if placement_id is not None:
            nauo_to_placement[nauo_id] = placement_id
    return nauo_to_placement


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def _transform_frame(local: Frame, instance: Frame) -> tuple[Vec3, Vec3]:
    """Apply the instance Frame (world-space placement) to a surface's local Frame."""
    lo = local.origin
    world_origin = Vec3(
        instance.origin.x + lo.x*instance.x_axis.x + lo.y*instance.y_axis.x + lo.z*instance.z_axis.x,
        instance.origin.y + lo.x*instance.x_axis.y + lo.y*instance.y_axis.y + lo.z*instance.z_axis.y,
        instance.origin.z + lo.x*instance.x_axis.z + lo.y*instance.y_axis.z + lo.z*instance.z_axis.z,
    )
    lz = local.z_axis
    world_axis = Vec3(
        lz.x*instance.x_axis.x + lz.y*instance.y_axis.x + lz.z*instance.z_axis.x,
        lz.x*instance.x_axis.y + lz.y*instance.y_axis.y + lz.z*instance.z_axis.y,
        lz.x*instance.x_axis.z + lz.y*instance.y_axis.z + lz.z*instance.z_axis.z,
    )
    return world_origin, world_axis.normalize()


def _compute_aabb(origins: list[Vec3]) -> tuple[Vec3, Vec3] | None:
    if not origins:
        return None
    xs = [v.x for v in origins]
    ys = [v.y for v in origins]
    zs = [v.z for v in origins]
    return Vec3(min(xs), min(ys), min(zs)), Vec3(max(xs), max(ys), max(zs))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_geometry_index(
    entities: dict[int, Entity],
    rr_transforms: dict[int, int],
    hierarchy: Hierarchy,
) -> dict[int, InstanceGeometry]:
    """
    Build world-space face geometry for every assembly instance (NAUO).

    Returns ``{nauo_id: InstanceGeometry}`` where each geometry object holds
    a list of :class:`WorldFace` entries already expressed in the assembly's
    world coordinate system.

    Products that appear in the hierarchy but have no parseable solid geometry
    produce an InstanceGeometry with an empty ``faces`` list.
    """
    t0 = time.perf_counter()
    by_type: ByType = defaultdict(list)
    for e in entities.values():
        by_type[e.name].append(e)
    log.info("  [geometry] type index: %d entities across %d types  (%.2fs)",
             len(entities), len(by_type), time.perf_counter() - t0)

    t0 = time.perf_counter()
    pts = _parse_cartesian_points(by_type)
    log.info("  [geometry] cartesian points: %d  (%.2fs)", len(pts), time.perf_counter() - t0)

    t0 = time.perf_counter()
    dirs = _parse_directions(by_type)
    log.info("  [geometry] directions: %d  (%.2fs)", len(dirs), time.perf_counter() - t0)

    t0 = time.perf_counter()
    placements = _parse_placements(by_type, pts, dirs)
    log.info("  [geometry] placements: %d  (%.2fs)", len(placements), time.perf_counter() - t0)

    t0 = time.perf_counter()
    surface_geoms = _parse_surface_geometries(by_type, placements)
    n_planes = sum(1 for s in surface_geoms.values() if s.surface_type == "PLANE")
    n_cyls   = sum(1 for s in surface_geoms.values() if s.surface_type == "CYLINDRICAL_SURFACE")
    log.info("  [geometry] surfaces: %d (%d planes, %d cylinders)  (%.2fs)",
             len(surface_geoms), n_planes, n_cyls, time.perf_counter() - t0)

    t0 = time.perf_counter()
    face_to_surf = _parse_face_to_surface(by_type)
    log.info("  [geometry] advanced faces: %d  (%.2fs)", len(face_to_surf), time.perf_counter() - t0)

    t0 = time.perf_counter()
    pd_to_face_ids = _build_pd_to_face_ids(by_type, face_to_surf, surface_geoms)
    log.info("  [geometry] products with geometry: %d  (%.2fs)",
             len(pd_to_face_ids), time.perf_counter() - t0)

    t0 = time.perf_counter()
    nauo_to_placement_id = _build_nauo_to_placement(by_type, rr_transforms, placements)
    log.info("  [geometry] instance transforms resolved: %d / %d  (%.2fs)",
             len(nauo_to_placement_id), len(hierarchy.children),
             time.perf_counter() - t0)
    if not nauo_to_placement_id:
        log.warning("  [geometry] zero instance transforms found — "
                    "all parts will use local-frame coordinates")

    pd_to_product_ref = _build_pd_to_product_ref(by_type)

    t0 = time.perf_counter()
    log.info("  [geometry] building world-space instances …")
    instances: dict[int, InstanceGeometry] = {}

    nauo_entities = {e.id: e for e in by_type.get("NEXT_ASSEMBLY_USAGE_OCCURRENCE", [])}

    for nauo_id, nauo_e in nauo_entities.items():
        nauo_args = split_args(nauo_e.raw_params)
        if len(nauo_args) < 5:
            continue
        relating_pd = as_ref(nauo_args[3])
        related_pd  = as_ref(nauo_args[4])
        if relating_pd is None or related_pd is None:
            continue

        parent_prod_ref = pd_to_product_ref.get(relating_pd)
        child_prod_ref  = pd_to_product_ref.get(related_pd)
        if parent_prod_ref is None or child_prod_ref is None:
            continue

        prod = hierarchy.products.get(child_prod_ref)
        if prod is None:
            continue

        instance_frame_id = nauo_to_placement_id.get(nauo_id)
        instance_frame    = placements.get(instance_frame_id) if instance_frame_id else None

        world_faces: list[WorldFace] = []
        face_ids = pd_to_face_ids.get(related_pd, [])

        for fid in face_ids:
            surf_ref, same_sense = face_to_surf[fid]
            surf = surface_geoms.get(surf_ref)
            if surf is None:
                continue
            local_frame = placements.get(surf.placement_id)
            if local_frame is None:
                continue

            if instance_frame is not None:
                world_origin, world_axis = _transform_frame(local_frame, instance_frame)
            else:
                world_origin = local_frame.origin
                world_axis   = local_frame.z_axis

            world_faces.append(WorldFace(
                face_id=fid,
                surface_type=surf.surface_type,
                origin=world_origin,
                axis=world_axis,
                radius=surf.radius,
                same_sense=same_sense,
            ))

        aabb = _compute_aabb([wf.origin for wf in world_faces]) if world_faces else None

        inst = InstanceGeometry(
            nauo_id=nauo_id,
            product_ref=child_prod_ref,
            parent_product_ref=parent_prod_ref,
            product_name=prod.name,
            product_id_str=prod.id,
            faces=world_faces,
        )
        if aabb is not None:
            inst.aabb_min, inst.aabb_max = aabb
        instances[nauo_id] = inst

    n_with_geom = sum(1 for i in instances.values() if i.faces)
    log.info("  [geometry] instances built: %d (%d with geometry)  (%.2fs)",
             len(instances), n_with_geom, time.perf_counter() - t0)
    return instances


def _build_pd_to_product_ref(by_type: ByType) -> dict[int, int]:
    """Reconstruct PRODUCT_DEFINITION -> PRODUCT chain (pd_id -> product_ref)."""
    pdf_to_product: dict[int, int] = {}
    for pdf_type in (
        "PRODUCT_DEFINITION_FORMATION",
        "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE",
    ):
        for e in by_type.get(pdf_type, []):
            args = split_args(e.raw_params)
            if len(args) < 3:
                continue
            prod_ref = as_ref(args[2])
            if prod_ref is not None:
                pdf_to_product[e.id] = prod_ref

    pd_to_product: dict[int, int] = {}
    for e in by_type.get("PRODUCT_DEFINITION", []):
        args = split_args(e.raw_params)
        if len(args) < 3:
            continue
        pdf_ref = as_ref(args[2])
        if pdf_ref is not None and pdf_ref in pdf_to_product:
            pd_to_product[e.id] = pdf_to_product[pdf_ref]
    return pd_to_product
