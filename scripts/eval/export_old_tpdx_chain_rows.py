"""Export frozen old-TP-DX chain rows from the live old KG (read-only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.old_tpdx_expert_ranking_mapping import graph_snapshot_id

EXPORT_SCHEMA_VERSION = "old_tpdx_chain_rows_export_v1"
EXPORT_ID = "old_tpdx_chain_rows_v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_read_only(cypher: str) -> list[dict]:
    from services.graph.neo4j_client import NEO4J_DATABASE, get_driver

    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(cypher)
        return [dict(record) for record in result]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only export of Cause-[:RESOLVED_BY]->Action chain rows from "
            "the live old TP-DX KG, with count verification against the "
            "2026-05-18 audit and a content snapshot digest. Never mutates "
            "the graph."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    observed: dict[str, int] = {}
    for name, cypher in config["graph_count_queries"].items():
        rows = _run_read_only(cypher)
        observed[name] = int(rows[0]["count"])
    expected = {k: v for k, v in config["expected_audit_counts"].items() if k != "reference"}
    diverged = sorted(
        name for name in expected if observed.get(name) != expected[name]
    )

    chain_rows = _run_read_only(config["chain_export_query"])
    incomplete = [
        index
        for index, row in enumerate(chain_rows)
        if not str(row.get("cause_text") or "").strip()
        or not str(row.get("action_text") or "").strip()
    ]
    if incomplete:
        raise SystemExit(
            f"chain rows {incomplete[:5]} have empty cause_text/action_text; "
            "graph property names diverge from the frozen export query"
        )

    export = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "export_id": EXPORT_ID,
        "config": {
            "path": str(args.config).replace("\\", "/"),
            "sha256": _sha256_file(args.config),
        },
        "graph_version": config["graph_version"],
        "graph_counts": {
            "observed": observed,
            "expected": expected,
            "diverged": diverged,
            "reference": config["expected_audit_counts"]["reference"],
        },
        "chain_row_count": len(chain_rows),
        "snapshot_id": graph_snapshot_id(chain_rows),
        "chain_rows": chain_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(export, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"chain_rows={len(chain_rows)} snapshot_id={export['snapshot_id']}"
    )
    print(f"observed_counts={observed}")
    if diverged:
        print(f"WARNING: counts diverged from audit: {diverged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
