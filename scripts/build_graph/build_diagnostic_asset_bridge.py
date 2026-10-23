#!/usr/bin/env python3
"""Build a deterministic diagnostic-to-asset bridge candidate artifact.

This script does not write Neo4j edges. It creates a reviewable JSON artifact
so `TRIGGERS` edges can be loaded only after inspection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.diagnostic_asset_bridge import (  # noqa: E402
    build_asset_catalog,
    build_bridge_artifact,
    load_alias_config,
    load_embedding_config,
    load_json,
)

_DEFAULT_DIAGNOSTIC = Path("data/processed/structured/diagnostic_complete_chains.json")
_DEFAULT_ASSET_INDEX = Path("data/processed/indexes/node_name_index.json")
_DEFAULT_TRIPLES = Path("data/processed/structured/triples.json")
_DEFAULT_OUTPUT = Path("data/processed/structured/diagnostic_asset_bridge_candidates.json")
_DEFAULT_ALIAS_CONFIG = Path("configs/diagnostic_asset_bridge_aliases.yaml")
_DEFAULT_EMBEDDING_CONFIG = Path("configs/diagnostic_asset_bridge_embedding.yaml")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else (_REPO_ROOT / path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic-input", type=Path, default=_DEFAULT_DIAGNOSTIC)
    parser.add_argument("--asset-index", type=Path, default=_DEFAULT_ASSET_INDEX)
    parser.add_argument("--triples", type=Path, default=_DEFAULT_TRIPLES)
    parser.add_argument("--alias-config", type=Path, default=_DEFAULT_ALIAS_CONFIG)
    parser.add_argument("--embedding-config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    diagnostic_input = _resolve(args.diagnostic_input)
    asset_index_input = _resolve(args.asset_index)
    triples_input = _resolve(args.triples)
    alias_config_input = _resolve(args.alias_config)
    embedding_config_input = _resolve(args.embedding_config) if args.embedding_config else None
    output = _resolve(args.output)

    diagnostic_data = load_json(diagnostic_input)
    asset_index_data = load_json(asset_index_input)
    triples_data = load_json(triples_input)
    alias_config = load_alias_config(alias_config_input)
    embedding_config = load_embedding_config(embedding_config_input) if embedding_config_input else None
    catalog = build_asset_catalog(asset_index_data, triples_data, alias_config=alias_config)

    artifact = build_bridge_artifact(
        diagnostic_data,
        catalog,
        diagnostic_input=str(diagnostic_input),
        asset_index_input=str(asset_index_input),
        triples_input=str(triples_input),
        alias_config_input=str(alias_config_input),
        embedding_config=embedding_config,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = artifact["summary"]
    print(f"Wrote: {output}")
    print(f"Records: {summary['record_count']}")
    for status, count in summary["status_counts"].items():
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
