#!/usr/bin/env python3
"""Build a name-to-node_id lookup index from triples.json.

Reads Module / Component / SubComponent nodes and writes node_name_index.json
in the same directory as the source triples.json. Re-run after each KG
extraction pass.

Output format
-------------
{
  "module": {"<name_string>": "<module_id>", ...},
  "component": {"<name_string>": "<component_id>", ...},
  "subcomponent": {"<name_string>": "<subcomponent_id>", ...},
  "__metadata__": {
    "schema_version": "node_name_index_v2",
    "collisions": {"component": {"安装板": ["C_...", "C_..."]}}
  }
}

Bare display names that collide across nodes are excluded from lookup buckets
and recorded under metadata. Hierarchy-qualified aliases are added so common
names such as `安装板` can still be resolved when the query includes module or
parent context.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_DEFAULT_TRIPLES = Path("data/processed/structured/triples.json")

_LABEL_TO_BUCKET: dict[str, str] = {
    "Module": "module",
    "Component": "component",
    "SubComponent": "subcomponent",
}

_LABEL_TO_ID_PROP: dict[str, str] = {
    "Module": "module_id",
    "Component": "component_id",
    "SubComponent": "subcomponent_id",
}

_LABEL_PREFIX: dict[str, str] = {
    "Module": "M_",
    "Component": "C_",
    "SubComponent": "SC_",
}

_HIERARCHY_EDGES = {"HAS_MODULE", "HAS_COMPONENT", "HAS_SUBCOMPONENT"}


def build_index(
    triples_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    """Return (index, stats) from triples_path."""
    with triples_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    index: dict[str, Any] = {
        "module": {},
        "component": {},
        "subcomponent": {},
    }
    stats: dict[str, dict[str, int]] = {
        label: {"total": 0, "with_name": 0, "alias_count": 0, "scoped_count": 0}
        for label in _LABEL_TO_BUCKET
    }
    candidates: dict[str, dict[str, set[str]]] = {
        "module": defaultdict(set),
        "component": defaultdict(set),
        "subcomponent": defaultdict(set),
    }
    # Maps property-based node_id → graph node id (for parent lookup)
    node_id_to_graph_id: dict[str, str] = {}

    nodes_by_id = _nodes_by_id(data)
    parent_by_child = _parent_by_child(data)

    # Pass 1: collect all aliases and build node_id→graph_id mapping
    for node in data.get("nodes", []):
        label: str = node.get("label", "")
        if label not in _LABEL_TO_BUCKET:
            continue

        bucket = _LABEL_TO_BUCKET[label]
        props: dict[str, Any] = node.get("properties", {})
        node_id: str = str(props.get(_LABEL_TO_ID_PROP[label]) or node["id"])
        name = _string_or_none(props.get("name"))

        stats[label]["total"] += 1
        if not name:
            continue
        stats[label]["with_name"] += 1

        node_id_to_graph_id[node_id] = str(node["id"])

        for alias in _aliases_for_node(
            node=node,
            node_id=node_id,
            name=name,
            nodes_by_id=nodes_by_id,
            parent_by_child=parent_by_child,
        ):
            candidates[bucket][alias].add(node_id)

        raw_id = _raw_node_id(str(node["id"]), label)
        if raw_id != name:
            candidates[bucket][raw_id].add(node_id)
            stats[label]["alias_count"] += 1

    # Pass 2: resolve collisions — generate scoped keys, keep bare name via setdefault
    collisions: dict[str, dict[str, list[str]]] = {}
    label_by_bucket = {v: k for k, v in _LABEL_TO_BUCKET.items()}
    for bucket, alias_map in candidates.items():
        bucket_collisions: dict[str, list[str]] = {}
        label = label_by_bucket[bucket]
        for alias, node_ids in sorted(alias_map.items()):
            if len(node_ids) == 1:
                index[bucket][alias] = next(iter(node_ids))
            else:
                bucket_collisions[alias] = sorted(node_ids)
                # Keep bare name as secondary alias — first sorted node_id wins
                index[bucket].setdefault(alias, sorted(node_ids)[0])
                # Generate underscore-scoped key per colliding node
                for node_id in sorted(node_ids):
                    graph_id = node_id_to_graph_id.get(node_id, node_id)
                    parent_graph_id = parent_by_child.get(graph_id)
                    if parent_graph_id:
                        parent_props = nodes_by_id.get(parent_graph_id, {}).get("properties", {})
                        parent_name = _string_or_none(parent_props.get("name"))
                        if parent_name:
                            scoped_key = _make_scoped_key(parent_name, alias)
                            index[bucket][scoped_key] = node_id
                            stats[label]["scoped_count"] += 1
                        else:
                            print(
                                f"  [WARN] {label} {node_id}: parent {parent_graph_id} "
                                f"has no name; bare alias '{alias}' kept without scoped key",
                                flush=True,
                            )
                    else:
                        print(
                            f"  [WARN] {label} {node_id}: no parent found for duplicate "
                            f"alias '{alias}'; bare alias kept",
                            flush=True,
                        )
        if bucket_collisions:
            collisions[bucket] = bucket_collisions

    index["__metadata__"] = {
        "schema_version": "node_name_index_v2",
        "collision_policy": (
            "bare alias kept for first occurrence; hierarchy-qualified and "
            "underscore-scoped keys added for all occurrences"
        ),
        "collisions": collisions,
    }
    return index, stats


def _nodes_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node["id"]): node
        for node in data.get("nodes", [])
        if node.get("id")
    }


def _parent_by_child(data: dict[str, Any]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for edge in data.get("edges", []):
        if edge.get("type") not in _HIERARCHY_EDGES:
            continue
        parent = edge.get("from")
        child = edge.get("to")
        if parent and child:
            parents[str(child)] = str(parent)
    return parents


def _aliases_for_node(
    *,
    node: dict[str, Any],
    node_id: str,
    name: str,
    nodes_by_id: dict[str, dict[str, Any]],
    parent_by_child: dict[str, str],
) -> list[str]:
    aliases = [name]
    path_names = _ancestor_names(str(node["id"]), nodes_by_id, parent_by_child)
    if path_names:
        aliases.extend(_qualified_aliases(path_names, name))

    props = node.get("properties", {})
    for key in ("module_id", "component_id", "subcomponent_id"):
        value = _string_or_none(props.get(key))
        if value and value != name and value != node_id:
            aliases.append(f"{value}/{name}")

    return list(dict.fromkeys(alias for alias in aliases if alias))


def _ancestor_names(
    node_id: str,
    nodes_by_id: dict[str, dict[str, Any]],
    parent_by_child: dict[str, str],
) -> list[str]:
    names: list[str] = []
    current = parent_by_child.get(node_id)
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        parent = nodes_by_id.get(current, {})
        props = parent.get("properties", {})
        name = _string_or_none(props.get("name"))
        if name:
            names.append(name)
        current = parent_by_child.get(current)
    names.reverse()
    return names


def _qualified_aliases(path_names: list[str], name: str) -> list[str]:
    aliases: list[str] = []
    for start in range(len(path_names)):
        suffix = path_names[start:] + [name]
        aliases.append("/".join(suffix))
        aliases.append(" ".join(suffix))
    return aliases


def _raw_node_id(node_id: str, label: str) -> str:
    prefix = _LABEL_PREFIX[label]
    return node_id[len(prefix):] if node_id.startswith(prefix) else node_id


def _make_scoped_key(parent_name: str, child_name: str) -> str:
    return f"{parent_name}_{child_name}"


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


_DEFAULT_OUTPUT = Path("data/processed/indexes/node_name_index.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build node_name_index.json from triples.json"
    )
    parser.add_argument(
        "--triples",
        type=Path,
        default=_DEFAULT_TRIPLES,
        help="Path to triples.json (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output path for node_name_index.json (default: %(default)s)",
    )
    args = parser.parse_args()

    triples_path: Path = args.triples
    if not triples_path.is_absolute():
        triples_path = Path.cwd() / triples_path

    print(f"Reading:  {triples_path}")
    index, stats = build_index(triples_path)

    out_path: Path = args.output
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    print(f"Written:  {out_path}")

    from services.governance._operation_log import safe_repo_path
    from services.governance.index_registry import record, snapshot_id

    record(
        index_name=out_path.stem,
        source_id=safe_repo_path(triples_path, REPO_ROOT),
        serving_snapshot_id=snapshot_id(triples_path),
        build_script=safe_repo_path(Path(__file__), REPO_ROOT),
        index_type="node_name_lookup",
        notes=f"output={safe_repo_path(out_path, REPO_ROOT)}",
    )

    print("\n--- Coverage ---")
    for label, s in stats.items():
        total = s["total"]
        with_name = s["with_name"]
        aliases = s["alias_count"]
        scoped = s["scoped_count"]
        pct = 100 * with_name // total if total else 0
        print(
            f"  {label:15s}: {total:4d} total, {with_name:4d} with name "
            f"({pct}%), {aliases} raw-id alias keys added, {scoped} scoped keys"
        )

    total_nodes = sum(s["total"] for s in stats.values())
    total_named = sum(s["with_name"] for s in stats.values())
    total_entries = sum(len(v) for k, v in index.items() if k != "__metadata__")
    total_scoped = sum(s["scoped_count"] for s in stats.values())
    collision_aliases = sum(
        len(bucket)
        for bucket in index.get("__metadata__", {}).get("collisions", {}).values()
    )
    print(
        f"\n  Total: {total_named}/{total_nodes} nodes indexed, "
        f"{total_entries} lookup entries written"
    )
    print(f"  {total_scoped} scoped (duplicate) keys added")
    print(f"  {collision_aliases} bare aliases with collisions (bare name kept for first occurrence)")


if __name__ == "__main__":
    main()
