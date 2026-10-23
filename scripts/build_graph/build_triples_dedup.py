#!/usr/bin/env python3
"""Write triples_dedup.json with disambiguated node names.

For any Module / Component / SubComponent whose display name collides with
another node of the same label, the name property is replaced with
    {parent_name}_{original_name}
Unique names are left unchanged.  All edges and non-name properties are
copied verbatim.

Usage
-----
    python scripts/build_graph/build_triples_dedup.py
    python scripts/build_graph/build_triples_dedup.py --triples path/to/triples.json
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

_DEFAULT_TRIPLES = Path("data/processed/structured/triples.json")

_HIERARCHY_EDGES = {"HAS_MODULE", "HAS_COMPONENT", "HAS_SUBCOMPONENT"}
_LABELS = ("Module", "Component", "SubComponent")


def _nodes_by_id(data: dict) -> dict[str, dict]:
    return {str(n["id"]): n for n in data.get("nodes", []) if n.get("id")}


def _parent_by_child(data: dict) -> dict[str, str]:
    parents: dict[str, str] = {}
    for e in data.get("edges", []):
        if e.get("type") in _HIERARCHY_EDGES and e.get("from") and e.get("to"):
            parents[str(e["to"])] = str(e["from"])
    return parents


def _duplicate_ids(data: dict, label: str) -> set[str]:
    """Return graph IDs of nodes whose name appears more than once within label."""
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for n in data.get("nodes", []):
        if n.get("label") == label:
            name = (n.get("properties") or {}).get("name")
            if name:
                name_to_ids[name].append(str(n["id"]))
    dupes: set[str] = set()
    for ids in name_to_ids.values():
        if len(ids) > 1:
            dupes.update(ids)
    return dupes


def _short_id(graph_id: str) -> str:
    """Strip label prefix (e.g. 'C_', 'SC_') and return the numeric suffix."""
    return graph_id.split("_", 1)[-1] if "_" in graph_id else graph_id


def build_dedup(triples_path: Path) -> tuple[dict, dict[str, int], int]:
    with triples_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    nodes_by_id = _nodes_by_id(data)
    parent_by_child = _parent_by_child(data)

    dupe_ids: dict[str, set[str]] = {
        label: _duplicate_ids(data, label) for label in _LABELS
    }

    stats: dict[str, int] = {label: 0 for label in _LABELS}
    warn_count = 0

    # Pass 1: scope duplicate names with parent prefix
    new_nodes = []
    for node in data.get("nodes", []):
        label = node.get("label", "")
        if label not in _LABELS or str(node["id"]) not in dupe_ids.get(label, set()):
            new_nodes.append(node)
            continue

        node = copy.deepcopy(node)
        props = node["properties"]
        original_name: str = props["name"]
        graph_id = str(node["id"])

        parent_graph_id = parent_by_child.get(graph_id)
        parent_name: str | None = None
        if parent_graph_id:
            parent_props = nodes_by_id.get(parent_graph_id, {}).get("properties") or {}
            parent_name = parent_props.get("name") or None

        if parent_name:
            props["name"] = f"{parent_name}_{original_name}"
            stats[label] += 1
        else:
            print(
                f"  [WARN] {label} {graph_id} ('{original_name}'): "
                f"no parent name found (parent={parent_graph_id or graph_id}); "
                f"falling back to id suffix",
                flush=True,
            )
            props["name"] = f"{_short_id(graph_id)}_{original_name}"
            stats[label] += 1
            warn_count += 1

        new_nodes.append(node)

    # Pass 2: if names still collide after parent prefix (same parent, same name),
    # append the node's own short id to guarantee uniqueness
    second_pass_count = 0
    for label in _LABELS:
        name_to_ids: dict[str, list[str]] = defaultdict(list)
        for n in new_nodes:
            if n.get("label") == label:
                name_to_ids[(n.get("properties") or {}).get("name", "")].append(str(n["id"]))
        still_dupes: set[str] = {
            nid for ids in name_to_ids.values() if len(ids) > 1 for nid in ids
        }
        if still_dupes:
            for n in new_nodes:
                if n.get("label") == label and str(n["id"]) in still_dupes:
                    n["properties"]["name"] = f"{n['properties']['name']}_{_short_id(str(n['id']))}"
                    second_pass_count += 1

    result = dict(data)
    result["nodes"] = new_nodes
    stats["_second_pass"] = second_pass_count
    return result, stats, warn_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write triples_dedup.json with scoped names for duplicate nodes."
    )
    parser.add_argument(
        "--triples",
        type=Path,
        default=_DEFAULT_TRIPLES,
        help="Path to triples.json (default: %(default)s)",
    )
    args = parser.parse_args()

    triples_path: Path = args.triples
    if not triples_path.is_absolute():
        triples_path = Path.cwd() / triples_path

    if not triples_path.exists():
        print(f"error: {triples_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Reading:  {triples_path}")
    result, stats, warn_count = build_dedup(triples_path)

    out_path = triples_path.parent / "triples_dedup.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"Written:  {out_path}")

    print("\n--- Scoped names ---")
    for label, count in stats.items():
        if label == "_second_pass":
            continue
        print(f"  {label:15s}: {count} nodes renamed")
    if stats.get("_second_pass"):
        print(f"  {stats['_second_pass']} further suffixed with own id (same-parent duplicates)")
    if warn_count:
        print(f"  {warn_count} nodes had no parent name — used id suffix (see [WARN] above)")
    print(f"  Total nodes in output: {len(result['nodes'])}")


if __name__ == "__main__":
    main()
