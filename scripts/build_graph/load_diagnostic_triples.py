"""
Load diagnostic chain data from diagnostic_complete_chains.json into Neo4j.

Builds nodes: ErrorCode, Fault, Cause, Action, ActionStep
Builds edges: INDICATES, HAS_CAUSE, RESOLVED_BY, HAS_STEP

All nodes carry validated=false and source="diagnostic_fp_join_v1_baseline"
to distinguish them from future reviewed data.

ActionStep nodes are derived from PA field content:
  - Multiple PA list items → one ActionStep per item
  - Single PA item with \\n → split on newline → one ActionStep per non-empty line

Side output: data/processed/diagnostic/error_code_index.json

Usage
-----
    python scripts/build_graph/load_diagnostic_triples.py
    python scripts/build_graph/load_diagnostic_triples.py --wipe-diagnostic
    python scripts/build_graph/load_diagnostic_triples.py --append
    python scripts/build_graph/load_diagnostic_triples.py --build-index-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.neo4j_client import (  # noqa: E402
    NEO4J_DATABASE, NEO4J_HOST, NEO4J_PASSWORD, NEO4J_USER, make_driver,
)

_SOURCE_TAG = "diagnostic_fp_join_v1_baseline"
_DEFAULT_INPUT = _REPO_ROOT / "data/processed/structured/diagnostic_complete_chains.json"
_DEFAULT_INDEX_OUT = _REPO_ROOT / "data/processed/indexes/error_code_index.json"
BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Cypher — constraints
# ---------------------------------------------------------------------------

CONSTRAINT_STATEMENTS = [
    "CREATE CONSTRAINT ec_code_id_unique IF NOT EXISTS "
    "FOR (n:ErrorCode) REQUIRE n.code_id IS UNIQUE",
    "CREATE CONSTRAINT fault_id_unique IF NOT EXISTS "
    "FOR (n:Fault) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT cause_id_unique IF NOT EXISTS "
    "FOR (n:Cause) REQUIRE n.cause_id IS UNIQUE",
    "CREATE CONSTRAINT action_id_unique IF NOT EXISTS "
    "FOR (n:Action) REQUIRE n.action_id IS UNIQUE",
    "CREATE CONSTRAINT step_id_unique IF NOT EXISTS "
    "FOR (n:ActionStep) REQUIRE n.step_id IS UNIQUE",
]

# ---------------------------------------------------------------------------
# Cypher — node merges
# ---------------------------------------------------------------------------

MERGE_ERROR_CODES = """
UNWIND $rows AS row
MERGE (n:ErrorCode {code_id: row.code_id})
  SET n.description = row.description,
      n.device_type  = row.device_type,
      n.validated    = row.validated,
      n.source       = row.source
"""

MERGE_FAULTS = """
UNWIND $rows AS row
MERGE (n:Fault {id: row.id})
  SET n.name        = row.name,
      n.description = row.description,
      n.keywords    = row.keywords,
      n.severity    = row.severity,
      n.validated   = row.validated,
      n.source      = row.source
"""

MERGE_CAUSES = """
UNWIND $rows AS row
MERGE (n:Cause {cause_id: row.cause_id})
  SET n.description = row.description,
      n.validated   = row.validated,
      n.source      = row.source
"""

MERGE_ACTIONS = """
UNWIND $rows AS row
MERGE (n:Action {action_id: row.action_id})
  SET n.action_name = row.action_name,
      n.validated   = row.validated,
      n.source      = row.source
"""

MERGE_STEPS = """
UNWIND $rows AS row
MERGE (n:ActionStep {step_id: row.step_id})
  SET n.order           = row.order,
      n.instruction     = row.instruction,
      n.expected_result = row.expected_result,
      n.placeholder     = row.placeholder,
      n.validated       = row.validated,
      n.source          = row.source
"""

# ---------------------------------------------------------------------------
# Cypher — edge merges
# ---------------------------------------------------------------------------

MERGE_INDICATES = """
UNWIND $rows AS row
MATCH (ec:ErrorCode {code_id: row.ec_id})
MATCH (f:Fault {id: row.fault_id})
MERGE (ec)-[:INDICATES]->(f)
"""

MERGE_HAS_CAUSE = """
UNWIND $rows AS row
MATCH (f:Fault {id: row.fault_id})
MATCH (ca:Cause {cause_id: row.cause_id})
MERGE (f)-[:HAS_CAUSE]->(ca)
"""

MERGE_RESOLVED_BY = """
UNWIND $rows AS row
MATCH (ca:Cause {cause_id: row.cause_id})
MATCH (act:Action {action_id: row.action_id})
MERGE (ca)-[:RESOLVED_BY]->(act)
"""

MERGE_HAS_STEP = """
UNWIND $rows AS row
MATCH (act:Action {action_id: row.action_id})
MATCH (s:ActionStep {step_id: row.step_id})
MERGE (act)-[:HAS_STEP]->(s)
"""

WIPE_DIAGNOSTIC = """
MATCH (n)
WHERE n:ErrorCode OR n:Fault OR n:Cause OR n:Action OR n:ActionStep
DETACH DELETE n
"""


# ---------------------------------------------------------------------------
# Data transformation helpers
# ---------------------------------------------------------------------------

def _stable_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _pa_to_steps(pa: list[str]) -> list[str]:
    """Flatten PA list into ordered action step instructions."""
    steps: list[str] = []
    for item in pa:
        for line in item.split("\n"):
            line = line.strip()
            if line:
                steps.append(line)
    return steps or pa


def _ec_device_type(ec_code: str) -> str:
    """Infer a coarse device type from the EC prefix character."""
    prefix = ec_code[0].upper() if ec_code else "?"
    _MAP = {"W": "workstation", "M": "module", "E": "equipment",
             "N": "network", "C": "control", "V": "vision"}
    return _MAP.get(prefix, "unknown")


def _build_rows(records: list[dict]) -> dict[str, list[dict]]:
    error_codes: list[dict] = []
    faults: list[dict] = []
    causes: list[dict] = []
    actions: list[dict] = []
    steps: list[dict] = []

    indicates: list[dict] = []
    has_cause: list[dict] = []
    resolved_by: list[dict] = []
    has_step: list[dict] = []

    seen_faults: set[str] = set()

    for rec in records:
        ec_code: str = rec["EC"]
        standard_fp: str = rec["standard_fp"]
        rc_list: list[str] = rec["RC"]
        pa_list: list[str] = rec["PA"]
        mapping_id: str = rec["mapping_id"]

        fault_id = "fault:" + _stable_hash(standard_fp)
        action_id = "action:" + mapping_id
        pa_steps = _pa_to_steps(pa_list)

        # ErrorCode node
        error_codes.append({
            "code_id": ec_code,
            "description": standard_fp,
            "device_type": _ec_device_type(ec_code),
            "validated": False,
            "source": _SOURCE_TAG,
        })

        # Fault node (deduplicated by standard_fp)
        if fault_id not in seen_faults:
            seen_faults.add(fault_id)
            keywords = list({w for w in standard_fp.replace("_", " ").split() if len(w) > 1})
            faults.append({
                "id": fault_id,
                "name": standard_fp,
                "description": standard_fp,
                "keywords": keywords or [standard_fp],
                "severity": "medium",
                "validated": False,
                "source": _SOURCE_TAG,
            })

        # Action node (one per record)
        action_name = pa_steps[0][:120] if pa_steps else standard_fp
        actions.append({
            "action_id": action_id,
            "action_name": action_name,
            "validated": False,
            "source": _SOURCE_TAG,
        })

        # ActionStep nodes
        for i, instruction in enumerate(pa_steps, start=1):
            step_id = f"step:{mapping_id}:{i}"
            steps.append({
                "step_id": step_id,
                "order": i,
                "instruction": instruction,
                "expected_result": "",
                "placeholder": False,
                "validated": False,
                "source": _SOURCE_TAG,
            })
            has_step.append({"action_id": action_id, "step_id": step_id})

        # Cause nodes (one per RC item)
        for rc_idx, rc_text in enumerate(rc_list):
            cause_id = "cause:" + _stable_hash(f"{mapping_id}:{rc_idx}:{rc_text}")
            causes.append({
                "cause_id": cause_id,
                "description": rc_text,
                "validated": False,
                "source": _SOURCE_TAG,
            })
            has_cause.append({"fault_id": fault_id, "cause_id": cause_id})
            resolved_by.append({"cause_id": cause_id, "action_id": action_id})

        # Edges
        indicates.append({"ec_id": ec_code, "fault_id": fault_id})

    return {
        "error_codes": error_codes,
        "faults": faults,
        "causes": causes,
        "actions": actions,
        "steps": steps,
        "indicates": indicates,
        "has_cause": has_cause,
        "resolved_by": resolved_by,
        "has_step": has_step,
    }


def _build_error_code_index(records: list[dict]) -> dict[str, str]:
    """Return {ec_code: ec_code} index for prekg EC detection."""
    return {rec["EC"]: rec["EC"] for rec in records}


# ---------------------------------------------------------------------------
# Bolt loader
# ---------------------------------------------------------------------------

def _chunks(lst: list, n: int) -> Iterable[list]:
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def _run_batched(session: Any, query: str, rows: list[dict]) -> None:
    for batch in _chunks(rows, BATCH_SIZE):
        session.run(query, rows=batch)
        sys.stdout.write(".")
        sys.stdout.flush()


def load(
    input_path: Path,
    uri: str,
    user: str,
    password: str,
    database: str = "neo4j",
    wipe_diagnostic: bool = False,
    index_path: Path = _DEFAULT_INDEX_OUT,
) -> None:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    records = data["records"]
    print(f"Input: {input_path}  ({len(records)} records)")

    parts = _build_rows(records)

    # Write error_code_index side output
    index = _build_error_code_index(records)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Error code index written: {index_path}  ({len(index)} entries)")

    print(f"Connecting to {uri} (db={database!r})...")
    driver = make_driver(uri, user, password)
    try:
        with driver.session(database=database) as session:
            if wipe_diagnostic:
                print("Wiping existing diagnostic nodes (ErrorCode/Fault/Cause/Action/ActionStep)...")
                session.run(WIPE_DIAGNOSTIC)

            print("Creating constraints...")
            for stmt in CONSTRAINT_STATEMENTS:
                session.run(stmt)

            _step("ErrorCode", parts["error_codes"], MERGE_ERROR_CODES, session)
            _step("Fault", parts["faults"], MERGE_FAULTS, session)
            _step("Cause", parts["causes"], MERGE_CAUSES, session)
            _step("Action", parts["actions"], MERGE_ACTIONS, session)
            _step("ActionStep", parts["steps"], MERGE_STEPS, session)
            _step("INDICATES", parts["indicates"], MERGE_INDICATES, session)
            _step("HAS_CAUSE", parts["has_cause"], MERGE_HAS_CAUSE, session)
            _step("RESOLVED_BY", parts["resolved_by"], MERGE_RESOLVED_BY, session)
            _step("HAS_STEP", parts["has_step"], MERGE_HAS_STEP, session)

            _print_counts(session)
    finally:
        driver.close()


def _step(label: str, rows: list[dict], query: str, session: Any) -> None:
    t0 = time.perf_counter()
    print(f"Merging {len(rows):>5} {label} ", end="")
    _run_batched(session, query, rows)
    print(f"  ({time.perf_counter() - t0:.1f}s)")


def _print_counts(session: Any) -> None:
    result = session.run(
        "MATCH (n) WITH labels(n)[0] AS label, count(*) AS c RETURN label, c ORDER BY label"
    )
    print("\nNode counts:")
    for r in result:
        print(f"  {r['label']}: {r['c']}")
    result = session.run(
        "MATCH ()-[r]->() WITH type(r) AS t, count(*) AS c RETURN t, c ORDER BY t"
    )
    print("Edge counts:")
    for r in result:
        print(f"  {r['t']}: {r['c']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    p.add_argument("--index-out", type=Path, default=_DEFAULT_INDEX_OUT)
    p.add_argument("--uri", default=NEO4J_HOST)
    p.add_argument("--user", default=NEO4J_USER)
    p.add_argument("--password", default=NEO4J_PASSWORD)
    p.add_argument("--database", default=NEO4J_DATABASE)
    p.add_argument("--wipe-diagnostic", action="store_true",
                   help="Delete all ErrorCode/Fault/Cause/Action/ActionStep nodes before loading.")
    p.add_argument("--append", action="store_true",
                   help="Append mode (default): MERGE nodes, keep existing data.")
    p.add_argument("--build-index-only", action="store_true",
                   help="Write error_code_index.json only, do not touch Neo4j.")
    args = p.parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    if args.build_index_only:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        index = _build_error_code_index(data["records"])
        args.index_out.parent.mkdir(parents=True, exist_ok=True)
        args.index_out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Error code index written: {args.index_out}  ({len(index)} entries)")
        return 0

    if not args.password:
        print("error: no password. Set FAULTDX_NEO4J_PASSWORD in .env or pass --password.",
              file=sys.stderr)
        return 2

    load(
        input_path=args.input,
        uri=args.uri,
        user=args.user,
        password=args.password,
        database=args.database,
        wipe_diagnostic=args.wipe_diagnostic,
        index_path=args.index_out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
