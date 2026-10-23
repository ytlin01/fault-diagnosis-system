#!/usr/bin/env python3
"""
Match the STEP-extracted parts list against the project BOM (XLSX).

All defaults come from configs/cad_extract.yaml.

Usage
-----
    # From the FaultDx_main repo root:
    python scripts/build_graph/run_bom_match.py
    python scripts/build_graph/run_bom_match.py --parts ... --bom ... --out ...
    python scripts/build_graph/run_bom_match.py --config path/to/other.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from services.graph.cad_extract.bom import load_bom, load_parts, match_parts_to_bom
from services.graph.cad_extract.config import get_config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Match STEP parts list against BOM.")
    p.add_argument("--parts", type=Path, default=None,
                   help="Path to parts_list.json (default: from config output_dir).")
    p.add_argument("--bom", type=Path, default=None,
                   help="Path to BOM XLSX (default: from config bom_file).")
    p.add_argument("--out", type=Path, default=None,
                   help="Output JSON path (default: bom_match.json in output_dir).")
    p.add_argument("--config", "-c", type=Path, default=None,
                   metavar="YAML",
                   help="Config YAML path (default: configs/cad_extract.yaml).")
    p.add_argument("--fuzzy-cutoff", type=float, default=None,
                   help="Similarity cutoff for fuzzy candidates (overrides config).")
    p.add_argument("--no-filter-noise", action="store_true",
                   help="Keep qty=0 and numeric-only STEP entries in the matching pool.")
    args = p.parse_args(argv)

    cfg = get_config(args.config)

    parts_path = args.parts or (_REPO_ROOT / cfg.output_dir / "parts_list.json")
    bom_path = args.bom or (_REPO_ROOT / cfg.bom_file)
    out_path = args.out or (_REPO_ROOT / cfg.output_dir / "bom_match.json")
    fuzzy_cutoff = args.fuzzy_cutoff if args.fuzzy_cutoff is not None else cfg.bom.fuzzy_cutoff
    filter_noise = (not args.no_filter_noise) and cfg.bom.filter_step_noise

    if not parts_path.exists():
        print(f"ERROR: {parts_path} does not exist. Run run_cad_extract.py first.",
              file=sys.stderr)
        return 1
    if not bom_path.exists():
        print(f"ERROR: {bom_path} does not exist.", file=sys.stderr)
        return 1

    parts, step_filtered = load_parts(
        parts_path,
        filter_noise=filter_noise,
        strip_rev_suffix=cfg.bom.strip_rev_suffix,
    )
    bom = load_bom(bom_path, strip_rev_suffix=cfg.bom.strip_rev_suffix)
    result = match_parts_to_bom(
        parts, bom,
        fuzzy_cutoff=fuzzy_cutoff,
        step_filtered=step_filtered,
        non_mechanical_keywords=cfg.bom.non_mechanical_keywords,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Match summary:")
    for k, v in result["summary"].items():
        print(f"  {k:30s} {v}")
    print(f"\nMatch JSON written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
