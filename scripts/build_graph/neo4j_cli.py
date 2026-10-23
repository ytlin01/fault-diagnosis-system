#!/usr/bin/env python3
"""Common Neo4j maintenance queries for FaultDx.

Credentials are read from .env (FAULTDX_NEO4J_* vars).

Usage
-----
    python scripts/build_graph/neo4j_cli.py --counts
    python scripts/build_graph/neo4j_cli.py --view
    python scripts/build_graph/neo4j_cli.py --wipe
    python scripts/build_graph/neo4j_cli.py --delete-label SubComponent
    python scripts/build_graph/neo4j_cli.py --sample Component --limit 5
    python scripts/build_graph/neo4j_cli.py --constraints
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.neo4j_client import (  # noqa: E402
    NEO4J_DATABASE, NEO4J_HOST, NEO4J_PASSWORD, NEO4J_USER, make_driver,
)

_VALID_LABELS = {"Station", "Module", "Component", "SubComponent"}


def _connect(uri: str, user: str, password: str, database: str):
    return make_driver(uri, user, password)


def cmd_counts(session) -> None:
    print("Node counts:")
    result = session.run(
        "MATCH (n) WITH labels(n)[0] AS label, count(*) AS c "
        "RETURN label, c ORDER BY label"
    )
    for r in result:
        print(f"  {r['label']}: {r['c']}")

    print("Edge counts:")
    result = session.run(
        "MATCH ()-[r]->() WITH type(r) AS t, count(*) AS c "
        "RETURN t, c ORDER BY t"
    )
    for r in result:
        print(f"  {r['t']}: {r['c']}")


_LABEL_ID_PROP = {
    "Station": "station_id",
    "Module": "module_id",
    "Component": "component_id",
    "SubComponent": "subcomponent_id",
}


def cmd_view(session) -> None:
    """Print counts plus a few sample node names per label."""
    cmd_counts(session)
    print()
    for label in ("Station", "Module", "Component", "SubComponent"):
        id_prop = _LABEL_ID_PROP[label]
        result = session.run(
            f"MATCH (n:{label}) "
            f"RETURN n.{id_prop} AS nid, n.name AS name LIMIT 5"
        )
        rows = result.data()
        if rows:
            print(f"{label} samples:")
            for row in rows:
                display = row["name"] or row["nid"]
                print(f"  {row['nid']}  {display}")


def cmd_wipe(session) -> None:
    print("Wiping all nodes and relationships...")
    session.run("MATCH (n) DETACH DELETE n")
    print("Done — database is empty.")


def cmd_delete_label(session, label: str) -> None:
    result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
    count = result.single()["c"]
    if count == 0:
        print(f"No {label} nodes found — nothing to delete.")
        return
    print(f"Deleting {count} {label} nodes (and their relationships)...")
    session.run(f"MATCH (n:{label}) DETACH DELETE n")
    print("Done.")


def cmd_sample(session, label: str, limit: int) -> None:
    result = session.run(
        f"MATCH (n:{label}) RETURN n LIMIT $limit", limit=limit
    )
    rows = result.data()
    print(f"{label} ({len(rows)} of up to {limit}):")
    for row in rows:
        props = dict(row["n"])
        print(f"  {props}")


def cmd_constraints(session) -> None:
    result = session.run("SHOW CONSTRAINTS")
    rows = result.data()
    if not rows:
        print("No constraints defined.")
        return
    print(f"{'Name':<40} {'Type':<20} {'Entity'}")
    print("-" * 80)
    for r in rows:
        print(f"  {r.get('name', ''):<38} {r.get('type', ''):<20} {r.get('labelsOrTypes', '')} {r.get('properties', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Common Neo4j maintenance queries for FaultDx."
    )

    parser.add_argument("--uri", default=NEO4J_HOST)
    parser.add_argument("--user", default=NEO4J_USER)
    parser.add_argument("--password", default=NEO4J_PASSWORD)
    parser.add_argument("--database", default=NEO4J_DATABASE)

    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--counts", action="store_true",
        help="Print node and edge counts per type.")
    actions.add_argument("--view", action="store_true",
        help="Print counts plus sample node names per label.")
    actions.add_argument("--wipe", action="store_true",
        help="Delete ALL nodes and relationships (irreversible).")
    actions.add_argument("--delete-label", metavar="LABEL",
        help=f"Delete all nodes of one label and their edges. "
             f"Valid: {', '.join(sorted(_VALID_LABELS))}")
    actions.add_argument("--sample", metavar="LABEL",
        help="Print raw properties of sample nodes for a label.")
    actions.add_argument("--constraints", action="store_true",
        help="List all schema constraints.")

    parser.add_argument("--limit", type=int, default=10,
        help="Row limit for --sample (default: 10).")

    args = parser.parse_args()

    if not args.password:
        print("error: no password. Set FAULTDX_NEO4J_PASSWORD in .env or pass --password.",
              file=sys.stderr)
        sys.exit(2)

    driver = _connect(args.uri, args.user, args.password, args.database)
    try:
        with driver.session(database=args.database) as session:
            if args.counts:
                cmd_counts(session)
            elif args.view:
                cmd_view(session)
            elif args.wipe:
                cmd_wipe(session)
            elif args.delete_label:
                cmd_delete_label(session, args.delete_label)
            elif args.sample:
                cmd_sample(session, args.sample, args.limit)
            elif args.constraints:
                cmd_constraints(session)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
