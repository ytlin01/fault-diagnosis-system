#!/usr/bin/env python3
"""Write TRIGGERS edges from a reviewed bridge artifact into Neo4j.

Reads the bridge candidate artifact and creates
    (:Component)-[:TRIGGERS {validated, source, mapping_status, evidence_rule}]->(:Fault)
for every record whose mapping_status is in the allowed statuses (default: "mapped").

This script does NOT modify diagnostic or CAD asset nodes — it only writes edges.

Usage
-----
    python scripts/build_graph/load_triggers_to_neo4j.py
    python scripts/build_graph/load_triggers_to_neo4j.py --wipe-triggers
    python scripts/build_graph/load_triggers_to_neo4j.py --allow-status mapped module_only
    python scripts/build_graph/load_triggers_to_neo4j.py --dry-run
    python scripts/build_graph/load_triggers_to_neo4j.py --bridge-input path/to/artifact.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.neo4j_client import (  # noqa: E402
    NEO4J_DATABASE, NEO4J_HOST, NEO4J_PASSWORD, NEO4J_USER, make_driver,
)

_DEFAULT_BRIDGE_INPUT = _REPO_ROOT / "data/processed/structured/diagnostic_asset_bridge_candidates.json"
_DEFAULT_ALLOW_STATUSES = ("mapped",)
_SOURCE_TAG = "diagnostic_asset_bridge_v1"
BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# Cypher
# ---------------------------------------------------------------------------

MERGE_TRIGGERS = """
UNWIND $rows AS row
MATCH (c:Component {component_id: row.component_id})
MATCH (f:Fault {id: row.fault_id})
MERGE (c)-[r:TRIGGERS]->(f)
  SET r.validated     = row.validated,
      r.source        = row.source,
      r.mapping_status = row.mapping_status,
      r.evidence_rule = row.evidence_rule
"""

WIPE_TRIGGERS = "MATCH ()-[r:TRIGGERS]->() DELETE r"

COUNT_TRIGGERS = "MATCH ()-[r:TRIGGERS]->() RETURN count(r) AS c"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_connect = make_driver


def _run_batch(session: Any, cypher: str, rows: list[dict]) -> None:
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        session.run(cypher, rows=batch)


def _build_trigger_rows(records: list[dict], allow_statuses: set[str]) -> list[dict]:
    rows: list[dict] = []
    for rec in records:
        status = rec.get("mapping_status", "")
        if status not in allow_statuses:
            continue
        component_id = rec.get("component_id")
        fault_id = rec.get("fault_id")
        if not component_id or not fault_id:
            continue
        evidence_rule = (rec.get("evidence") or {}).get("rule", "")
        rows.append({
            "component_id": component_id,
            "fault_id": fault_id,
            "validated": False,
            "source": _SOURCE_TAG,
            "mapping_status": status,
            "evidence_rule": evidence_rule,
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-input", type=Path, default=_DEFAULT_BRIDGE_INPUT,
        help="Bridge candidate artifact JSON (default: %(default)s)")
    parser.add_argument("--allow-status", nargs="+", default=list(_DEFAULT_ALLOW_STATUSES),
        metavar="STATUS",
        help="Mapping statuses to load as TRIGGERS (default: mapped). "
             "Add 'module_only' only after manual review.")
    parser.add_argument("--wipe-triggers", action="store_true",
        help="Delete all existing TRIGGERS edges before loading.")
    parser.add_argument("--dry-run", action="store_true",
        help="Print what would be written without touching Neo4j.")
    parser.add_argument("--uri", default=NEO4J_HOST)
    parser.add_argument("--user", default=NEO4J_USER)
    parser.add_argument("--password", default=NEO4J_PASSWORD)
    parser.add_argument("--database", default=NEO4J_DATABASE)
    args = parser.parse_args(argv)

    bridge_path = args.bridge_input if args.bridge_input.is_absolute() else _REPO_ROOT / args.bridge_input
    if not bridge_path.exists():
        print(f"error: bridge artifact not found: {bridge_path}", file=sys.stderr)
        return 2

    artifact = json.loads(bridge_path.read_text(encoding="utf-8"))
    records: list[dict] = artifact.get("records", [])
    allow_statuses = set(args.allow_status)

    rows = _build_trigger_rows(records, allow_statuses)

    print(f"Bridge artifact:  {bridge_path}")
    print(f"Generated at:     {artifact.get('metadata', {}).get('generated_at', 'unknown')}")
    print(f"Allow statuses:   {', '.join(sorted(allow_statuses))}")
    print(f"Records in file:  {len(records)}")
    print(f"TRIGGERS to load: {len(rows)}")

    if args.dry_run:
        print("\n--- Dry run: rows that would be written ---")
        for row in rows:
            print(f"  ({row['component_id']})-[:TRIGGERS]->({row['fault_id']})"
                  f"  rule={row['evidence_rule']}")
        return 0

    if not args.password:
        print("error: no password. Set FAULTDX_NEO4J_PASSWORD in .env or pass --password.",
              file=sys.stderr)
        return 2

    driver = _connect(args.uri, args.user, args.password)
    t0 = time.monotonic()
    try:
        with driver.session(database=args.database) as session:
            if args.wipe_triggers:
                session.run(WIPE_TRIGGERS)
                print("Wiped existing TRIGGERS edges.")

            _run_batch(session, MERGE_TRIGGERS, rows)

            count = session.run(COUNT_TRIGGERS).single()["c"]
    finally:
        driver.close()

    elapsed = time.monotonic() - t0
    print(f"Done in {elapsed:.1f}s — TRIGGERS in graph: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
