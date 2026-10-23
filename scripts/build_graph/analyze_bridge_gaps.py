#!/usr/bin/env python3
"""Quick analysis of unmatched bridge records and available CAD names."""
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

artifact = json.loads((_REPO_ROOT / "data/processed/structured/diagnostic_asset_bridge_candidates.json").read_text(encoding="utf-8"))
triples = json.loads((_REPO_ROOT / "data/processed/structured/triples_dedup.json").read_text(encoding="utf-8"))

# Build component name -> module name map for context
comp_names = {}
mod_names_by_id = {}
for node in triples["nodes"]:
    props = node.get("properties", {})
    label = node.get("label")
    if label == "Module":
        mod_names_by_id[node["id"]] = props.get("name", node["id"])
    elif label in ("Component", "SubComponent"):
        comp_names[node["id"]] = props.get("name", node["id"])

module_only = [r for r in artifact["records"] if r["mapping_status"] == "module_only"]
unmapped = [r for r in artifact["records"] if r["mapping_status"] == "unmapped"]

print(f"=== MODULE_ONLY ({len(module_only)}) ===")
for r in module_only[:20]:
    fp = r["standard_fp"]
    mod_hits = r["evidence"]["module_hits"]
    mod_display = [h["display_name"] for h in mod_hits]
    aliases = [a for h in mod_hits for a in h.get("matched_aliases", [])]
    print(f"  FP:      {fp}")
    print(f"  Module:  {mod_display}  |  alias matched: {aliases}")
    print()

print(f"\n=== UNMAPPED ({len(unmapped)}) ===")
for r in unmapped:
    print(f"  {r['standard_fp']}")

print(f"\n=== ALL COMPONENT NAMES IN CAD ({len(comp_names)}) - first 60 ===")
for nid, name in list(comp_names.items())[:60]:
    print(f"  {nid}  {name}")
