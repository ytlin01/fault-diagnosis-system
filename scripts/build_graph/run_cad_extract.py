#!/usr/bin/env python3
"""
Full STEP → KG triple extraction pipeline for FaultDx_main.

Reads configs/cad_extract.yaml, then runs:
  parse → hierarchy → geometry → mate inference → triples (v3.2) → validate → write

Usage
-----
    # From the FaultDx_main repo root:
    python scripts/build_graph/run_cad_extract.py
    python scripts/build_graph/run_cad_extract.py data/raw/Y25_CSTN_Va_STP.STEP
    python scripts/build_graph/run_cad_extract.py --config path/to/other.yaml
    python scripts/build_graph/run_cad_extract.py --root "SubAssemblyName"

Station convention (schema v3.2, Option A)
------------------------------------------
The STEP root assembly product is mapped to one Station node:
  station_id   = station.station_id from configs/cad_extract.yaml (if set),
                 otherwise falls back to cfg.dataset
  station_type = root PRODUCT.name from the STEP file
One STEP file → one Station. Multi-unit disambiguation requires a future
station_registry.yaml (see docs/agents/cad_extract.md).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure the repo root is on sys.path regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.cad_extract.bom import load_bom
from services.graph.cad_extract.config import get_config
from services.graph.cad_extract.geometry import build_geometry_index
from services.graph.cad_extract.hierarchy import (
    build_hierarchy,
    find_product_by_name_or_id,
    subtree_product_refs,
)
from services.graph.cad_extract.kg_edges import serialize_hierarchy_edges
from services.graph.cad_extract.parser import parse_step_full, scan_rr_transforms
from services.graph.cad_extract.relationships import infer_mates
from services.graph.cad_extract.stats import compute_stats, format_stats_text
from services.graph.cad_extract.triples import emit_triples
from services.graph.cad_extract.validate import format_summary, load_schema, validate_triples

log = logging.getLogger(__name__)


def _elapsed(t0: float) -> str:
    return f"{time.perf_counter() - t0:.1f}s"


def _load_bom_display_names(cfg) -> dict[str, str]:
    """Return {PRODUCT id: BOM display name} when the BOM XLSX can be read."""
    bom_file = _REPO_ROOT / cfg.bom_file
    if not bom_file.exists():
        return {}
    try:
        from services.graph.cad_extract.bom import _make_norm
        bom = load_bom(
            bom_file,
            strip_rev_suffix=cfg.bom.strip_rev_suffix,
        )
        _norm = _make_norm(cfg.bom.strip_rev_suffix)
    except Exception as exc:
        log.warning("Could not load BOM display names from %s: %s", bom_file, exc)
        return {}

    names: dict[str, str] = {}
    for key, entry in bom.items():
        model = entry.get("型号") or ""
        name = entry.get("名称") or ""
        if model and name:
            names[str(model)] = str(name)
            names[_norm(model)] = str(name)
        elif key and name:
            names[str(key)] = str(name)
    return names


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Extract part hierarchy and KG triples from a STEP file.",
    )
    p.add_argument(
        "step_file",
        type=Path,
        nargs="?",
        default=None,
        help="Path to the STEP file (default: data/raw/{dataset}_STP.STEP from config).",
    )
    p.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        metavar="YAML",
        help="Config YAML path (default: configs/cad_extract.yaml in repo root).",
    )
    p.add_argument(
        "--root",
        type=str,
        default=None,
        metavar="NAME_OR_ID",
        help="Limit geometry and mate inference to this sub-assembly.",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d [%(levelname)-5s]  %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, args.log_level),
        stream=sys.stderr,
    )

    cfg = get_config(args.config)
    step_file = args.step_file or (_REPO_ROOT / cfg.step_file)
    output_dir = _REPO_ROOT / cfg.output_dir
    schema_file = _REPO_ROOT / cfg.schema_file

    t_total = time.perf_counter()

    if not step_file.exists():
        log.error("STEP file not found: %s", step_file)
        return 1

    # ── Phase 1: parse ───────────────────────────────────────────────────────
    log.info("Phase 1 — parsing %s  (%.1f MB)",
             step_file, step_file.stat().st_size / 1_048_576)
    t0 = time.perf_counter()
    try:
        entities, data_text = parse_step_full(step_file)
    except Exception:
        log.exception("Fatal error during STEP parse")
        return 1
    log.info("  %d entities in DATA section  (%s)", len(entities), _elapsed(t0))

    # ── Phase 2: hierarchy ───────────────────────────────────────────────────
    log.info("Phase 2 — building product hierarchy")
    t0 = time.perf_counter()
    try:
        hierarchy = build_hierarchy(entities)
    except Exception:
        log.exception("Fatal error building hierarchy")
        return 1
    log.info("  %d products, %d roots, %d orphans, %d unresolved NAUOs  (%s)",
             len(hierarchy.products),
             len(hierarchy.roots),
             len(hierarchy.orphans),
             hierarchy.unresolved_nauos,
             _elapsed(t0))
    if hierarchy.unresolved_nauos:
        log.warning("  %d NAUOs could not be resolved (missing PD/PDF refs)",
                    hierarchy.unresolved_nauos)
    if hierarchy.orphans:
        sample = [hierarchy.products[o].name or hierarchy.products[o].id
                  for o in hierarchy.orphans[:3]]
        log.warning("  %d orphan PRODUCT(s) dropped from BOM: %s%s",
                    len(hierarchy.orphans), sample,
                    "..." if len(hierarchy.orphans) > 3 else "")

    t0 = time.perf_counter()
    stats = compute_stats(hierarchy)
    log.info("  stats computed  (%s)", _elapsed(t0))

    # ── --root filter ────────────────────────────────────────────────────────
    subtree: set[int] | None = None
    if args.root:
        matches = find_product_by_name_or_id(hierarchy, args.root)
        if not matches:
            log.error("No product with name or id '%s' found.", args.root)
            return 1
        if len(matches) > 1:
            names = [f"#{r} {hierarchy.products[r].name!r}" for r in matches]
            log.warning("'%s' matched %d products (%s); using first.",
                        args.root, len(matches), ", ".join(names))
        root_ref = matches[0]
        subtree = subtree_product_refs(hierarchy, root_ref)
        log.info("--root '%s' → product #%d (%r): %d products in subtree",
                 args.root, root_ref, hierarchy.products[root_ref].name, len(subtree))

    # ── Phase 3: geometry ────────────────────────────────────────────────────
    log.info("Phase 3 — extracting geometry and inferring mates")
    t0 = time.perf_counter()
    try:
        rr_transforms = scan_rr_transforms(data_text)
    except Exception:
        log.exception("Fatal error scanning RR transforms")
        return 1
    log.info("  %d instance-transform links found  (%s)", len(rr_transforms), _elapsed(t0))

    t0 = time.perf_counter()
    try:
        instances = build_geometry_index(entities, rr_transforms, hierarchy)
    except Exception:
        log.exception("Fatal error building geometry index")
        return 1
    log.info("  geometry index built: %d instances  (%s)", len(instances), _elapsed(t0))

    if subtree is not None:
        before = len(instances)
        instances = {
            nauo_id: inst for nauo_id, inst in instances.items()
            if inst.parent_product_ref in subtree
        }
        log.info("  filtered %d → %d instances within --root subtree", before, len(instances))

    # ── Phase 4: mate inference ──────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        raw_mates = infer_mates(instances, hierarchy, cfg=cfg.mate)
    except Exception:
        log.exception("Fatal error during mate inference")
        return 1
    log.info("  %d mates detected  (%s)", len(raw_mates), _elapsed(t0))

    stats = compute_stats(hierarchy, mates=raw_mates)

    # ── Phase 5: write outputs ───────────────────────────────────────────────
    log.info("Phase 5 — writing outputs")
    log.info(format_stats_text(stats, sample=cfg.sample_size))

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        bom_parts = [
            {"bom名称": p["name"], "bom型号": p["id"], "bom数量": p["qty"]}
            for p in stats["parts"]
        ]
        parts_path = output_dir / "parts_list.json"
        parts_path.write_text(
            json.dumps(bom_parts, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("  parts list → %s  (%d parts)", parts_path, len(bom_parts))

        stats_path = output_dir / "stats.json"
        stats_path.write_text(
            json.dumps({
                "summary": stats["summary"],
                "hierarchy": stats["hierarchy"],
                "mates_note": stats["mates_note"],
                "roots": stats["roots"],
                "orphans": stats["orphans"],
                "warnings": stats["warnings"],
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("  stats → %s", stats_path)

        mates_path = output_dir / "mates_list.json"
        mates_out = [m.to_dict() for m in raw_mates]
        mates_path.write_text(
            json.dumps(mates_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("  mates list → %s  (%d mates)", mates_path, len(mates_out))

        hierarchy_edges = serialize_hierarchy_edges(hierarchy)
        edges_path = output_dir / "hierarchy_edges.json"
        edges_out = [e.to_dict() for e in hierarchy_edges]
        edges_path.write_text(
            json.dumps(edges_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        edge_type_counts: dict[str, int] = {}
        for e in hierarchy_edges:
            edge_type_counts[e.edge_type] = edge_type_counts.get(e.edge_type, 0) + 1
        log.info("  hierarchy edges → %s  (%d edges: %s)",
                 edges_path, len(edges_out),
                 ", ".join(f"{k}={v}" for k, v in sorted(edge_type_counts.items())))

        bom_display_names = _load_bom_display_names(cfg)
        if bom_display_names:
            log.info("  loaded %d BOM display names for triples", len(bom_display_names))

        # Resolve station identity from config (Option A: dataset name + STEP root name)
        root_product = None
        if hierarchy.roots:
            root_product = hierarchy.products.get(hierarchy.roots[0])
        station_id = cfg.station_id or cfg.dataset
        station_type = (root_product.name if root_product else "") or station_id

        triples = emit_triples(
            hierarchy,
            hierarchy_edges,
            raw_mates,
            display_names_by_product_id=bom_display_names,
            station_id=station_id,
            station_type=station_type,
        )
        triples_path = output_dir / "triples.json"
        triples_dict = triples.to_dict()
        triples_path.write_text(
            json.dumps(triples_dict, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        triple_counts = triples.counts()
        log.info("  triples → %s  (%s)",
                 triples_path,
                 ", ".join(f"{k}={v}" for k, v in sorted(triple_counts.items())))

        schema = load_schema(schema_file) if schema_file.exists() else None
        if schema is None:
            log.warning("  schema file not found at %s — skipping validation", schema_file)
            return 0

        report = validate_triples(triples_dict, schema=schema)
        validation_path = output_dir / "validation.json"
        validation_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8",
        )
        log.info("  %s → %s", format_summary(report), validation_path)
        if not report.is_valid:
            log.warning(
                "  triples FAILED schema validation: %d real error(s); first few: %s",
                len(report.violations),
                "; ".join(
                    f"{v.location} {v.rule}: {v.detail}" for v in report.violations[:3]
                ),
            )

    except OSError:
        log.exception("Failed to write output files")
        return 1

    log.info("Done — total elapsed: %s", _elapsed(t_total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
