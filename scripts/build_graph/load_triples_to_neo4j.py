#!/usr/bin/env python3
"""
Stream `triples.json` directly into a running Neo4j instance via Bolt.

Schema v3.2: Station is a real first-class node. No QPL placeholder is
created. HAS_MODULE runs from Station → Module using the real station_id.

Beats the cypher-shell path for two reasons:
  1. Parameterized UNWIND batches (no per-row literal serialization, no
     reserved-keyword concerns).
  2. Stays in one Python process, so progress and errors are visible inline.

Usage
-----
    # Credentials are read from .env (copy .env.example → .env and fill in):
    #   FAULTDX_NEO4J_HOST     = bolt://127.0.0.1:7687
    #   FAULTDX_NEO4J_USER     = neo4j
    #   FAULTDX_NEO4J_PASSWORD = <your-password>
    #   FAULTDX_NEO4J_DATABASE = neo4j   # or cad_triples, etc.

    # Then run from the FaultDx_main repo root:
    python scripts/build_graph/load_triples_to_neo4j.py
    python scripts/build_graph/load_triples_to_neo4j.py --wipe

CLI flags override environment variables. The script is idempotent (MERGE
everywhere) so re-runs against a populated DB are safe.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterable
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.neo4j_client import (  # noqa: E402
    NEO4J_DATABASE, NEO4J_HOST, NEO4J_PASSWORD, NEO4J_USER, make_driver,
)

from services.graph.cad_extract.config import get_config  # noqa: E402


BATCH_SIZE = 5000

_LABEL_TO_KEY = {
    "Station": "station_id",
    "Module": "module_id",
    "Component": "component_id",
    "SubComponent": "subcomponent_id",
}

# ---------------------------------------------------------------------------
# Cypher statements (parameterized; $rows is the UNWIND batch list)
# ---------------------------------------------------------------------------

CONSTRAINT_STATEMENTS = [
    "CREATE CONSTRAINT station_id_unique IF NOT EXISTS "
    "FOR (n:Station) REQUIRE n.station_id IS UNIQUE",
    "CREATE CONSTRAINT module_id_unique IF NOT EXISTS "
    "FOR (n:Module) REQUIRE n.module_id IS UNIQUE",
    "CREATE CONSTRAINT component_id_unique IF NOT EXISTS "
    "FOR (n:Component) REQUIRE n.component_id IS UNIQUE",
    "CREATE CONSTRAINT subcomponent_id_unique IF NOT EXISTS "
    "FOR (n:SubComponent) REQUIRE n.subcomponent_id IS UNIQUE",
]

MERGE_STATIONS = """
UNWIND $rows AS row
MERGE (n:Station {station_id: row.station_id})
  SET n.station_type = row.station_type
"""

MERGE_MODULES = """
UNWIND $rows AS row
MERGE (n:Module {module_id: row.module_id})
  SET n.name = row.name,
      n.module_type = row.module_type,
      n.station_id = row.station_id
"""

MERGE_COMPONENTS = """
UNWIND $rows AS row
MERGE (n:Component {component_id: row.component_id})
  SET n.name = row.name,
      n.component_type = row.component_type,
      n.module_id = row.module_id
"""

MERGE_SUBCOMPONENTS = """
UNWIND $rows AS row
MERGE (n:SubComponent {subcomponent_id: row.subcomponent_id})
  SET n.name = row.name,
      n.component_type = row.component_type,
      n.module_id = row.module_id
"""

# v3.2: HAS_MODULE from_id is the Station node id (e.g. "ST_Y24_CSTN_Di").
# We carry the station_id property value (not the node id) for the MATCH.
MERGE_HAS_MODULE = """
UNWIND $rows AS row
MATCH (s:Station {station_id: row.station_id})
MATCH (m:Module {module_id: row.module_id})
MERGE (s)-[:HAS_MODULE]->(m)
"""


def _merge_hierarchy_edge_query(
    edge_type: str,
    from_label: str, from_key: str,
    to_label: str, to_key: str,
) -> str:
    return f"""
UNWIND $rows AS row
MATCH (a:{from_label} {{{from_key}: row.from_id}})
MATCH (b:{to_label} {{{to_key}: row.to_id}})
MERGE (a)-[:{edge_type}]->(b)
"""


def _merge_has_connection_query(
    from_label: str, from_key: str,
    to_label: str, to_key: str,
) -> str:
    return f"""
UNWIND $rows AS row
MATCH (a:{from_label} {{{from_key}: row.from_id}})
MATCH (b:{to_label} {{{to_key}: row.to_id}})
MERGE (a)-[r:HAS_CONNECTION {{connection_type: row.connection_type}}]->(b)
  SET r.confidence = row.confidence,
      r.source = row.source
"""


# ---------------------------------------------------------------------------
# Data partitioning
# ---------------------------------------------------------------------------

def _chunks(lst: list, n: int) -> Iterable[list]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _partition_triples(triples: dict) -> dict:
    nodes = triples.get("nodes", [])
    edges = triples.get("edges", [])

    id_to_label = {n["id"]: n["label"] for n in nodes if isinstance(n.get("id"), str)}
    # Map Station node id → station_id property for HAS_MODULE resolution.
    station_node_id_to_station_id: dict[str, str] = {
        n["id"]: (n.get("properties") or {}).get("station_id", "")
        for n in nodes
        if n.get("label") == "Station" and isinstance(n.get("id"), str)
    }

    stations: list[dict] = []
    modules: list[dict] = []
    components: list[dict] = []
    subcomponents: list[dict] = []
    for n in nodes:
        props = dict(n.get("properties") or {})
        label = n.get("label", "")
        if label == "Station":
            stations.append(props)
        elif label == "Module":
            modules.append(props)
        elif label == "Component":
            components.append(props)
        elif label == "SubComponent":
            subcomponents.append(props)

    has_module: list[dict] = []
    has_component: list[dict] = []
    # HAS_SUBCOMPONENT: from=Component|SubComponent, to=SubComponent — bucket by pair.
    has_subcomp_buckets: dict[tuple[str, str], list[dict]] = {}
    has_connection_buckets: dict[tuple[str, str], list[dict]] = {}

    for e in edges:
        etype = e.get("type", "")
        f, t = e.get("from"), e.get("to")
        props = e.get("properties") or {}
        if etype == "HAS_MODULE":
            station_id_val = station_node_id_to_station_id.get(f or "", "")
            has_module.append({"station_id": station_id_val, "module_id": t})
        elif etype == "HAS_COMPONENT":
            has_component.append({"from_id": f, "to_id": t})
        elif etype == "HAS_SUBCOMPONENT":
            from_label = id_to_label.get(f)
            to_label = id_to_label.get(t)
            if from_label not in _LABEL_TO_KEY or to_label not in _LABEL_TO_KEY:
                continue
            has_subcomp_buckets.setdefault((from_label, to_label), []).append(
                {"from_id": f, "to_id": t}
            )
        elif etype == "HAS_CONNECTION":
            from_label = id_to_label.get(f)
            to_label = id_to_label.get(t)
            if from_label not in _LABEL_TO_KEY or to_label not in _LABEL_TO_KEY:
                continue
            has_connection_buckets.setdefault((from_label, to_label), []).append({
                "from_id": f,
                "to_id": t,
                "connection_type": props.get("connection_type"),
                "confidence": props.get("confidence"),
                "source": props.get("source"),
            })

    return {
        "stations": stations,
        "modules": modules,
        "components": components,
        "subcomponents": subcomponents,
        "has_module": has_module,
        "has_component": has_component,
        "has_subcomp_buckets": has_subcomp_buckets,
        "has_connection_buckets": has_connection_buckets,
    }


# ---------------------------------------------------------------------------
# Bolt loader
# ---------------------------------------------------------------------------

def _run_batched(session, query: str, rows: list[dict]) -> None:
    for batch in _chunks(rows, BATCH_SIZE):
        session.run(query, rows=batch)
        sys.stdout.write(".")
        sys.stdout.flush()


def load(
    triples_path: Path,
    uri: str,
    user: str,
    password: str,
    database: str = "neo4j",
    wipe: bool = False,
) -> None:
    triples = json.loads(triples_path.read_text(encoding="utf-8"))
    parts = _partition_triples(triples)

    print(f"Connecting to {uri} (db={database!r})...")
    driver = make_driver(uri, user, password)
    try:
        with driver.session(database=database) as session:
            if wipe:
                print("Wiping existing nodes and relationships...")
                session.run("MATCH (n) DETACH DELETE n")

            print("Creating constraints...")
            for stmt in CONSTRAINT_STATEMENTS:
                session.run(stmt)

            t0 = time.perf_counter()
            print(f"Merging {len(parts['stations'])} Station nodes ", end="")
            _run_batched(session, MERGE_STATIONS, parts["stations"])
            print(f"  ({time.perf_counter() - t0:.1f}s)")

            t0 = time.perf_counter()
            print(f"Merging {len(parts['modules'])} Module nodes ", end="")
            _run_batched(session, MERGE_MODULES, parts["modules"])
            print(f"  ({time.perf_counter() - t0:.1f}s)")

            t0 = time.perf_counter()
            print(f"Merging {len(parts['components'])} Component nodes ", end="")
            _run_batched(session, MERGE_COMPONENTS, parts["components"])
            print(f"  ({time.perf_counter() - t0:.1f}s)")

            t0 = time.perf_counter()
            print(f"Merging {len(parts['subcomponents'])} SubComponent nodes ", end="")
            _run_batched(session, MERGE_SUBCOMPONENTS, parts["subcomponents"])
            print(f"  ({time.perf_counter() - t0:.1f}s)")

            t0 = time.perf_counter()
            print(f"Merging {len(parts['has_module'])} HAS_MODULE edges ", end="")
            _run_batched(session, MERGE_HAS_MODULE, parts["has_module"])
            print(f"  ({time.perf_counter() - t0:.1f}s)")

            t0 = time.perf_counter()
            print(f"Merging {len(parts['has_component'])} HAS_COMPONENT edges ", end="")
            _run_batched(
                session,
                _merge_hierarchy_edge_query(
                    "HAS_COMPONENT", "Module", "module_id", "Component", "component_id",
                ),
                parts["has_component"],
            )
            print(f"  ({time.perf_counter() - t0:.1f}s)")

            for (from_label, to_label), rows in sorted(parts["has_subcomp_buckets"].items()):
                t0 = time.perf_counter()
                print(f"Merging {len(rows)} HAS_SUBCOMPONENT {from_label}->{to_label} ", end="")
                _run_batched(
                    session,
                    _merge_hierarchy_edge_query(
                        "HAS_SUBCOMPONENT",
                        from_label, _LABEL_TO_KEY[from_label],
                        to_label, _LABEL_TO_KEY[to_label],
                    ),
                    rows,
                )
                print(f"  ({time.perf_counter() - t0:.1f}s)")

            for (from_label, to_label), rows in sorted(parts["has_connection_buckets"].items()):
                t0 = time.perf_counter()
                print(
                    f"Merging {len(rows)} HAS_CONNECTION {from_label}->{to_label} ",
                    end="",
                )
                _run_batched(
                    session,
                    _merge_has_connection_query(
                        from_label, _LABEL_TO_KEY[from_label],
                        to_label, _LABEL_TO_KEY[to_label],
                    ),
                    rows,
                )
                print(f"  ({time.perf_counter() - t0:.1f}s)")

            result = session.run(
                "MATCH (n) "
                "WITH labels(n)[0] AS label, count(*) AS c "
                "RETURN label, c ORDER BY label"
            )
            print("\nNode counts:")
            for record in result:
                print(f"  {record['label']}: {record['c']}")
            result = session.run(
                "MATCH ()-[r]->() "
                "WITH type(r) AS t, count(*) AS c "
                "RETURN t, c ORDER BY t"
            )
            print("Edge counts:")
            for record in result:
                print(f"  {record['t']}: {record['c']}")
    finally:
        driver.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load triples.json into Neo4j over Bolt.")
    p.add_argument("triples", type=Path, nargs="?", default=None,
                   help="Path to triples.json (default: from config output_dir).")
    p.add_argument("--uri", default=NEO4J_HOST, help="Bolt URI (env: FAULTDX_NEO4J_HOST)")
    p.add_argument("--user", default=NEO4J_USER, help="Username (env: FAULTDX_NEO4J_USER)")
    p.add_argument("--password", default=NEO4J_PASSWORD,
                   help="Password (env: FAULTDX_NEO4J_PASSWORD — set in .env, not on CLI)")
    p.add_argument("--database", default=NEO4J_DATABASE,
                   help="Database name (env: FAULTDX_NEO4J_DATABASE)")
    p.add_argument("--wipe", action="store_true",
                   help="Run MATCH (n) DETACH DELETE n before loading.")
    p.add_argument("--config", "-c", type=Path, default=None, metavar="YAML")
    args = p.parse_args(argv)

    cfg = get_config(args.config)
    triples_path = args.triples or (_REPO_ROOT / cfg.output_dir / "triples.json")

    if not triples_path.exists():
        print(f"error: {triples_path} not found", file=sys.stderr)
        return 1
    if not args.password:
        print(
            "error: no password. Set $env:NEO4J_PASSWORD or pass --password.",
            file=sys.stderr,
        )
        return 2

    load(
        triples_path=triples_path,
        uri=args.uri,
        user=args.user,
        password=args.password,
        database=args.database,
        wipe=args.wipe,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
