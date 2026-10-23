#!/usr/bin/env python3
"""Merge non-CAD device nodes from configs/device_registry.yaml into Neo4j.

Creates :Component nodes for physical devices not modeled in the STEP file.
All registry nodes carry source="device_registry" so they are distinguishable
from CAD-derived components.

This script is idempotent (MERGE). Run it after load_triples_to_neo4j.py and
before load_triggers_to_neo4j.py whenever device_registry.yaml changes.

Usage
-----
    python scripts/build_graph/load_device_registry.py
    python scripts/build_graph/load_device_registry.py --dry-run
    python scripts/build_graph/load_device_registry.py --config path/to/device_registry.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

from services.graph.neo4j_client import (  # noqa: E402
    NEO4J_DATABASE, NEO4J_HOST, NEO4J_PASSWORD, NEO4J_USER, make_driver,
)

_DEFAULT_REGISTRY = _REPO_ROOT / "configs/device_registry.yaml"

MERGE_DEVICE_NODES = """
UNWIND $rows AS row
MERGE (n:Component {component_id: row.id})
  SET n.name            = row.name,
      n.source          = row.source,
      n.device_category = row.device_category,
      n.description     = row.description
"""

COUNT_REGISTRY_NODES = (
    "MATCH (n:Component {source: 'device_registry'}) RETURN count(n) AS c"
)


def _load_registry(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices = data.get("devices", [])
    rows = []
    for entry in devices:
        if not entry.get("id") or not entry.get("name"):
            print(f"warning: skipping entry missing id or name: {entry}", file=sys.stderr)
            continue
        rows.append({
            "id":              entry["id"],
            "name":            entry["name"],
            "source":          entry.get("source", "device_registry"),
            "device_category": entry.get("device_category", ""),
            "description":     entry.get("description", ""),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=_DEFAULT_REGISTRY,
        help="Path to device_registry.yaml (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
        help="Print nodes that would be merged without touching Neo4j.")
    parser.add_argument("--uri", default=NEO4J_HOST)
    parser.add_argument("--user", default=NEO4J_USER)
    parser.add_argument("--password", default=NEO4J_PASSWORD)
    parser.add_argument("--database", default=NEO4J_DATABASE)
    args = parser.parse_args(argv)

    config_path = args.config if args.config.is_absolute() else _REPO_ROOT / args.config
    if not config_path.exists():
        print(f"error: registry config not found: {config_path}", file=sys.stderr)
        return 2

    rows = _load_registry(config_path)
    print(f"Registry config:  {config_path}")
    print(f"Devices to merge: {len(rows)}")

    if args.dry_run:
        print("\n--- Dry run: nodes that would be merged ---")
        for row in rows:
            print(f"  :Component {{component_id: {row['id']!r}, name: {row['name']!r}, "
                  f"source: {row['source']!r}, device_category: {row['device_category']!r}}}")
        return 0

    if not args.password:
        print("error: no password. Set FAULTDX_NEO4J_PASSWORD in .env or pass --password.",
              file=sys.stderr)
        return 2

    driver = make_driver(args.uri, args.user, args.password)
    t0 = time.monotonic()
    try:
        with driver.session(database=args.database) as session:
            session.run(MERGE_DEVICE_NODES, rows=rows)
            count = session.run(COUNT_REGISTRY_NODES).single()["c"]
    finally:
        driver.close()

    elapsed = time.monotonic() - t0
    print(f"Done in {elapsed:.1f}s — device_registry Component nodes in graph: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
