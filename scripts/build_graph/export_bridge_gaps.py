#!/usr/bin/env python3
"""Export unmapped fault devices and unmatched CAD components for manual review."""
import json
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

artifact = json.loads((_REPO_ROOT / "data/processed/structured/diagnostic_asset_bridge_candidates.json").read_text(encoding="utf-8"))
triples = json.loads((_REPO_ROOT / "data/processed/structured/triples_dedup.json").read_text(encoding="utf-8"))

# Build node and hierarchy lookups
nodes = {n["id"]: n["properties"] for n in triples["nodes"]}
mod_of_comp = {}
for e in triples["edges"]:
    if e["type"] == "HAS_COMPONENT":
        mod_of_comp[e["to"]] = e["from"]

# --- Unmapped fault devices grouped by device prefix ---
groups: dict[str, list[str]] = defaultdict(list)
for r in artifact["records"]:
    if r["mapping_status"] != "unmapped":
        continue
    prefix = r["standard_fp"].split("_")[0]
    groups[prefix].append(r["standard_fp"])

unmapped_devices = [
    {
        "device_prefix": prefix,
        "count": len(fps),
        "fault_phrases": sorted(set(fps)),
        "suggest_component_id": None,
        "notes": "",
    }
    for prefix, fps in sorted(groups.items(), key=lambda x: -len(x[1]))
]

# --- Unmatched CAD components (no TRIGGERS edge pointing to them) ---
matched_comp_ids = {r["component_id"] for r in artifact["records"] if r.get("component_id")}

unmatched_components = []
for n in triples["nodes"]:
    if n["label"] != "Component":
        continue
    props = n.get("properties", {})
    cid = props.get("component_id")
    if not cid or cid in matched_comp_ids:
        continue
    mod_id = mod_of_comp.get(n["id"], "")
    mod_name = nodes.get(mod_id, {}).get("name", mod_id) if mod_id else ""
    unmatched_components.append({
        "component_id": cid,
        "name": props.get("name", ""),
        "module_id": mod_id,
        "module_name": mod_name,
        "suggest_fault_prefix": None,
        "notes": "",
    })

unmatched_components.sort(key=lambda x: (x["module_name"], x["name"]))

output = {
    "_instructions": (
        "Fill in 'suggest_component_id' for each unmapped fault device, "
        "or 'suggest_fault_prefix' for each unmatched component. "
        "Then run scripts/build_graph/build_diagnostic_asset_bridge.py "
        "after updating configs/diagnostic_asset_bridge_aliases.yaml."
    ),
    "unmapped_fault_devices": unmapped_devices,
    "unmatched_cad_components": unmatched_components,
}

out_path = _REPO_ROOT / "data/processed/structured/bridge_gap_review.json"
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"Written: {out_path}")
print(f"Unmapped device groups: {len(unmapped_devices)}")
print(f"Unmatched CAD components: {len(unmatched_components)}")
