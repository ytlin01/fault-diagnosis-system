"""
Compute and format extraction stats over a built Hierarchy.

Output is intentionally shaped for the BOM-matching step:
 - every unique product carries its id, name, description, and qty
 - totals and a quick eyeball sample make it easy to sanity-check extraction
   before we compare against the BOM CSV
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .hierarchy import Hierarchy, max_depth


def compute_stats(h: Hierarchy, mates: Iterable[Any] | None = None) -> dict[str, Any]:
    """Build a JSON-serializable stats dict covering counts + per-part qtys.

    If ``mates`` is provided (an iterable of relationships.Mate), the summary
    block reports actual mate counts and a per-type breakdown. Pass None when
    mate inference hasn't run yet to keep the legacy "no mates" shape.
    """
    # Orphans are PRODUCTs declared in the STEP file but referenced by zero
    # NAUOs. Per task #6 we drop them from the BOM-shaped parts list (qty would
    # be 0 and they aren't part of the assembly tree); they remain visible
    # under stats.json["orphans"] for diagnostics.
    orphan_set = set(h.orphans)
    parts = []
    for pref, prod in sorted(h.products.items()):
        if pref in orphan_set:
            continue
        parts.append({
            "product_ref": pref,
            "id": prod.id,
            "name": prod.name,
            "description": prod.description,
            "qty": h.instance_count.get(pref, 0),
            "is_root": pref in h.roots,
        })

    total_instances = sum(h.instance_count.values())

    if mates is None:
        total_mates = 0
        mates_by_type: dict[str, int] = {}
        mates_note = (
            "Mate inference not run yet. STEP AP203/AP214/AP242 do not encode "
            "SolidWorks mate constraints; relationships must be inferred from "
            "geometry (face contact, coaxiality, proximity). See docs/agents/cad_extract.md."
        )
    else:
        mates_list = list(mates)
        total_mates = len(mates_list)
        mates_by_type = dict(Counter(m.mate_type for m in mates_list))
        mates_note = (
            f"{total_mates} mates inferred from geometry "
            f"(planar/concentric/tangent + proximity fallback). "
            f"See mates_list.json for per-edge details."
        )

    return {
        "summary": {
            "unique_products": len(h.products),
            "total_instances": total_instances,
            "root_assemblies": len(h.roots),
            "orphan_products": len(h.orphans),
            "max_hierarchy_depth": max_depth(h),
            "total_mates": total_mates,
            "mates_by_type": mates_by_type,
            "unresolved_nauos": h.unresolved_nauos,
        },
        "hierarchy": _by_level(h),
        "mates_note": mates_note,
        "roots": [
            {
                "product_ref": r,
                "id": h.products[r].id,
                "name": h.products[r].name,
            }
            for r in h.roots
            if r in h.products
        ],
        "orphans": [
            {
                "product_ref": o,
                "id": h.products[o].id,
                "name": h.products[o].name,
            }
            for o in h.orphans
            if o in h.products
        ],
        "parts": parts,
        "warnings": _warnings(h, parts),
    }


def _by_level(h: Hierarchy) -> dict[str, dict[str, int]]:
    # Walk the instance tree (NAUO edges) from each root, tallying by depth.
    # "assemblies" = has children, "parts" = leaf. Counts *instances*
    # (duplicates across parents), not unique products.
    counts: dict[int, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "assemblies": 0, "parts": 0}
    )
    stack: list[tuple[int, int, frozenset[int]]] = [
        (r, 1, frozenset()) for r in h.roots
    ]
    while stack:
        node, depth, ancestors = stack.pop()
        if node in ancestors:  # cycle guard
            continue
        kids = h.children.get(node, [])
        counts[depth]["total"] += 1
        counts[depth]["assemblies" if kids else "parts"] += 1
        new_ancestors = ancestors | {node}
        for child in kids:
            stack.append((child, depth + 1, new_ancestors))
    return {str(lvl): counts[lvl] for lvl in sorted(counts)}


def _warnings(h: Hierarchy, parts: list[dict[str, Any]]) -> list[str]:
    """Surface things the user should eyeball before trusting the extraction."""
    w: list[str] = []
    if not h.products:
        w.append("No PRODUCT entities found — is this really a STEP file?")
    if not h.roots and h.products:
        w.append("No roots identified — assembly may be cyclic or malformed.")
    if h.unresolved_nauos:
        w.append(
            f"{h.unresolved_nauos} NAUO(s) could not be resolved to a product "
            f"(missing PD/PDF refs). These instances are not counted in qty."
        )
    if h.orphans:
        sample = [h.products[o].name or h.products[o].id for o in h.orphans[:3]]
        w.append(
            f"{len(h.orphans)} orphan PRODUCT(s) dropped from BOM "
            f"(no parent and no children — declared but unused): "
            f"{sample}{'...' if len(h.orphans) > 3 else ''}"
        )
    empty_names = sum(1 for p in parts if not p["name"])
    if empty_names:
        w.append(f"{empty_names} product(s) have an empty PRODUCT.name field.")
    empty_ids = sum(1 for p in parts if not p["id"])
    if empty_ids:
        w.append(f"{empty_ids} product(s) have an empty PRODUCT.id field.")
    id_counts: dict[str, int] = {}
    for p in parts:
        if p["id"]:
            id_counts[p["id"]] = id_counts.get(p["id"], 0) + 1
    dupes = [k for k, v in id_counts.items() if v > 1]
    if dupes:
        w.append(f"{len(dupes)} duplicate PRODUCT.id value(s): {dupes[:5]}...")
    return w


def format_stats_text(stats: dict[str, Any], sample: int = 10) -> str:
    """Human-readable summary for stdout."""
    s = stats["summary"]
    lines = [
        "=" * 60,
        "STEP extraction summary",
        "=" * 60,
        f"  unique products    : {s['unique_products']}",
        f"  total instances    : {s['total_instances']}",
        f"  root assemblies    : {s['root_assemblies']}",
        f"  orphan products    : {s.get('orphan_products', 0)}",
        f"  max hierarchy depth: {s['max_hierarchy_depth']}",
        f"  unresolved NAUOs   : {s['unresolved_nauos']}",
        f"  total mates        : {s['total_mates']}",
        "",
    ]
    if s["mates_by_type"]:
        lines.append("Mates by type:")
        for t, n in sorted(s["mates_by_type"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {t:<18} {n:>6}")
        lines.append("")

    if stats["roots"]:
        lines.append("Roots:")
        for r in stats["roots"]:
            lines.append(f"  #{r['product_ref']}  id={r['id']!r}  name={r['name']!r}")
        lines.append("")

    if stats.get("hierarchy"):
        lines.append(f"{'Level':<8}{'Total':>8}{'Assemblies':>13}{'Parts':>8}")
        lines.append("-" * 40)
        h = stats["hierarchy"]
        tot = sum(v["total"] for v in h.values())
        asm = sum(v["assemblies"] for v in h.values())
        prt = sum(v["parts"] for v in h.values())
        for lvl, v in h.items():
            lines.append(f"{lvl:<8}{v['total']:>8}{v['assemblies']:>13}{v['parts']:>8}")
        lines.append("-" * 40)
        lines.append(f"{'Sum':<8}{tot:>8}{asm:>13}{prt:>8}")
        lines.append("")

    parts_sorted = sorted(stats["parts"], key=lambda p: (-p["qty"], p["id"]))
    shown = parts_sorted[:sample]
    if shown:
        lines.append(f"Top {len(shown)} parts by qty (of {len(stats['parts'])}):")
        lines.append(f"  {'qty':>5}  {'id':<24}  name")
        for p in shown:
            name = p["name"][:40]
            lines.append(f"  {p['qty']:>5}  {p['id'][:24]:<24}  {name}")
        lines.append("")

    if stats["warnings"]:
        lines.append("Warnings:")
        for w in stats["warnings"]:
            lines.append(f"  ! {w}")
        lines.append("")

    return "\n".join(lines)
