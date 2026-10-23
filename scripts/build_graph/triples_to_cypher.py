#!/usr/bin/env python3
"""
Generate a Cypher script from `triples.json` for Neo4j Desktop import.

Schema v3.2: Station is a real node (not a QPL placeholder). Every HAS_MODULE
edge has a real `from` pointing at a Station node. No placeholder QPL is
created; the Station node is MERGE'd from the triples data directly.

Output is idempotent (MERGE everywhere) so re-runs against the same DB are safe.

Usage
-----
    # From the FaultDx_main repo root:
    python scripts/build_graph/triples_to_cypher.py
    python scripts/build_graph/triples_to_cypher.py data/processed/Y24_CSTN_Di_matched/triples.json
    python scripts/build_graph/triples_to_cypher.py path/to/triples.json -o out.cypher

Loading the result in Neo4j Desktop
-----------------------------------
The Di file produces ~17k edges; the resulting .cypher is ~1–2 MB, which
may exceed the Browser drag-drop threshold. Two reliable paths:

1. **cypher-shell** (recommended):
       cd "<Neo4j Desktop install>/bin"
       cypher-shell -u neo4j -p <pass> -d <db> -f path/to/triples.cypher

2. **Browser :source** — copy the .cypher into the DB's import folder
   (right-click DB → "Open folder" → "Import"), then in Browser:
       :source file:///triples.cypher

Visualization tips
------------------
- Start with limited views to avoid overwhelming Browser:
      MATCH (s:Station)-[:HAS_MODULE]->(m) RETURN s, m LIMIT 50
      MATCH (m:Module)-[:HAS_COMPONENT]->(c) RETURN m, c LIMIT 200
      MATCH (a)-[r:HAS_CONNECTION]-(b) WHERE r.connection_type = 'concentric'
      RETURN a, r, b LIMIT 100
- To wipe and re-import cleanly: MATCH (n) DETACH DELETE n;
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.cad_extract.config import get_config


BATCH_SIZE = 5000

# Maps schema label → unique-id property name.
_LABEL_TO_KEY = {
    "Station": "station_id",
    "Module": "module_id",
    "Component": "component_id",
}


# ---------------------------------------------------------------------------
# Cypher literal formatting
# ---------------------------------------------------------------------------

def _cy_value(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    raise TypeError(f"Cannot render {type(v).__name__} as Cypher literal: {v!r}")


def _cy_map(d: dict) -> str:
    return "{" + ", ".join(f"{k}: {_cy_value(v)}" for k, v in d.items()) + "}"


def _chunks(lst: list, n: int) -> Iterable[list]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


# ---------------------------------------------------------------------------
# Cypher section emitters
# ---------------------------------------------------------------------------

def _emit_constraints() -> list[str]:
    return [
        "// ---- 1. Uniqueness constraints (idempotent) ----------------------",
        "CREATE CONSTRAINT station_id_unique IF NOT EXISTS "
        "FOR (n:Station) REQUIRE n.station_id IS UNIQUE;",
        "CREATE CONSTRAINT module_id_unique IF NOT EXISTS "
        "FOR (n:Module) REQUIRE n.module_id IS UNIQUE;",
        "CREATE CONSTRAINT component_id_unique IF NOT EXISTS "
        "FOR (n:Component) REQUIRE n.component_id IS UNIQUE;",
        "",
    ]


def _emit_node_batches(label: str, key_field: str, props_list: list[dict]) -> list[str]:
    if not props_list:
        return []
    out = [f"// ---- Nodes: {label} ({len(props_list)} total) ----"]
    total_batches = (len(props_list) + BATCH_SIZE - 1) // BATCH_SIZE
    for i, batch in enumerate(_chunks(props_list, BATCH_SIZE), start=1):
        rows_lit = ",\n  ".join(_cy_map(p) for p in batch)
        non_key_fields = [k for k in batch[0].keys() if k != key_field]
        set_clause = ", ".join(f"n.{k} = row.{k}" for k in non_key_fields)
        out.append(
            f"// {label} batch {i}/{total_batches}\n"
            f"UNWIND [\n  {rows_lit}\n] AS row\n"
            f"MERGE (n:{label} {{{key_field}: row.{key_field}}})\n"
            + (f"  SET {set_clause};" if set_clause else "  RETURN n;")
        )
    out.append("")
    return out


def _emit_typed_edges(
    edge_type: str,
    from_label: str,
    from_key: str,
    to_label: str,
    to_key: str,
    rows: list[dict],
    edge_props_keys: list[str],
) -> list[str]:
    if not rows:
        return []
    out = [
        f"// ---- Edges: {edge_type} {from_label}->{to_label} "
        f"({len(rows)} total) ----"
    ]
    for batch in _chunks(rows, BATCH_SIZE):
        rows_lit = ",\n  ".join(_cy_map(r) for r in batch)
        if edge_props_keys:
            set_clause = ", ".join(f"r.{k} = row.{k}" for k in edge_props_keys)
            edge_clause = (
                f"MERGE (a)-[r:{edge_type}]->(b)\n"
                f"  ON CREATE SET {set_clause}\n"
                f"  ON MATCH  SET {set_clause};"
            )
        else:
            edge_clause = f"MERGE (a)-[:{edge_type}]->(b);"
        out.append(
            f"UNWIND [\n  {rows_lit}\n] AS row\n"
            f"MATCH (a:{from_label} {{{from_key}: row.from_id}})\n"
            f"MATCH (b:{to_label} {{{to_key}: row.to_id}})\n"
            f"{edge_clause}"
        )
    out.append("")
    return out


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_cypher(triples: dict, source_path: Path | None = None) -> str:
    nodes = triples.get("nodes", [])
    edges = triples.get("edges", [])

    id_to_label = {n["id"]: n["label"] for n in nodes if isinstance(n.get("id"), str)}

    stations_props: list[dict] = []
    modules_props: list[dict] = []
    components_props: list[dict] = []
    for n in nodes:
        props = dict(n.get("properties") or {})
        label = n.get("label", "")
        if label == "Station":
            stations_props.append(props)
        elif label == "Module":
            modules_props.append(props)
        elif label == "Component":
            components_props.append(props)
        else:
            print(
                f"warning: skipping unknown node label {label!r} for id={n.get('id')!r}",
                file=sys.stderr,
            )

    has_module_rows: list[dict] = []
    has_component_rows: list[dict] = []
    has_subcomp_rows: list[dict] = []
    has_connection_buckets: dict[tuple[str, str], list[dict]] = {}
    skipped_unknown_edges = 0

    for e in edges:
        etype = e.get("type", "")
        f, t = e.get("from"), e.get("to")
        props = e.get("properties") or {}
        if etype == "HAS_MODULE":
            # v3.2: `from` is a real Station node id (not null).
            has_module_rows.append({"from_id": f, "to_id": t})
        elif etype == "HAS_COMPONENT":
            has_component_rows.append({"from_id": f, "to_id": t})
        elif etype == "HAS_SUBCOMPONENT":
            has_subcomp_rows.append({"from_id": f, "to_id": t})
        elif etype == "HAS_CONNECTION":
            row = {"from_id": f, "to_id": t, **props}
            from_label = id_to_label.get(f, "")
            to_label = id_to_label.get(t, "")
            has_connection_buckets.setdefault((from_label, to_label), []).append(row)
        else:
            skipped_unknown_edges += 1

    if skipped_unknown_edges:
        print(
            f"warning: skipped {skipped_unknown_edges} edge(s) with unknown type",
            file=sys.stderr,
        )

    parts: list[str] = []
    parts.append(f"// Generated from {source_path}" if source_path else "// Generated triples")
    parts.append(
        f"// Schema v{triples.get('schema_version', '?')}; "
        f"{len(nodes)} nodes, {len(edges)} edges"
    )
    parts.append("// To wipe before re-import, uncomment:")
    parts.append("//   MATCH (n) DETACH DELETE n;")
    parts.append("")
    parts.extend(_emit_constraints())
    # Nodes: Station first so HAS_MODULE MATCH finds them.
    parts.extend(_emit_node_batches("Station", "station_id", stations_props))
    parts.extend(_emit_node_batches("Module", "module_id", modules_props))
    parts.extend(_emit_node_batches("Component", "component_id", components_props))
    # HAS_MODULE: Station → Module (v3.2 has real from_id)
    parts.extend(
        _emit_typed_edges(
            "HAS_MODULE", "Station", "station_id", "Module", "module_id",
            has_module_rows, edge_props_keys=[],
        )
    )
    parts.extend(
        _emit_typed_edges(
            "HAS_COMPONENT", "Module", "module_id", "Component", "component_id",
            has_component_rows, edge_props_keys=[],
        )
    )
    parts.extend(
        _emit_typed_edges(
            "HAS_SUBCOMPONENT", "Component", "component_id", "Component", "component_id",
            has_subcomp_rows, edge_props_keys=[],
        )
    )
    for (from_label, to_label), rows in sorted(has_connection_buckets.items()):
        if from_label not in _LABEL_TO_KEY or to_label not in _LABEL_TO_KEY:
            print(
                f"warning: skipping HAS_CONNECTION {from_label}->{to_label} "
                f"({len(rows)} edges) — unknown endpoint label",
                file=sys.stderr,
            )
            continue
        parts.extend(
            _emit_typed_edges(
                "HAS_CONNECTION",
                from_label, _LABEL_TO_KEY[from_label],
                to_label, _LABEL_TO_KEY[to_label],
                rows,
                edge_props_keys=["connection_type", "confidence", "source"],
            )
        )

    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convert triples.json into a Cypher import script.")
    p.add_argument(
        "triples",
        type=Path,
        nargs="?",
        default=None,
        help="Path to triples.json (default: from config output_dir).",
    )
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output .cypher path (default: triples.cypher next to the input).",
    )
    p.add_argument("--config", "-c", type=Path, default=None, metavar="YAML")
    args = p.parse_args(argv)

    cfg = get_config(args.config)
    triples_path = args.triples or (_REPO_ROOT / cfg.output_dir / "triples.json")

    if not triples_path.exists():
        print(f"error: {triples_path} not found", file=sys.stderr)
        return 1

    triples = json.loads(triples_path.read_text(encoding="utf-8"))
    out_path = args.output or triples_path.with_suffix(".cypher")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_cypher(triples, source_path=triples_path), encoding="utf-8")

    nodes = triples.get("nodes", [])
    edges = triples.get("edges", [])
    by_label: dict[str, int] = {}
    for n in nodes:
        lb = n.get("label", "")
        by_label[lb] = by_label.get(lb, 0) + 1
    by_etype: dict[str, int] = {}
    for e in edges:
        et = e.get("type", "")
        by_etype[et] = by_etype.get(et, 0) + 1

    print(f"wrote {out_path}")
    print(f"  nodes: " + ", ".join(f"{k}={v}" for k, v in sorted(by_label.items())))
    print("  edges: " + ", ".join(f"{k}={v}" for k, v in sorted(by_etype.items())))
    print(f"  size: {out_path.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
