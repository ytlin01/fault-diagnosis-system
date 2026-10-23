"""
services.graph.cad_extract
==========================
STEP → Parts / Mates / KG Triples extraction pipeline.

Ported from cad_tool Phase 1 (origin/cad_tool branch, validated 2026-05-05).
Target schema: diagnostic_schema_v3_2. Outputs Station / Module / Component /
SubComponent nodes and HAS_MODULE / HAS_COMPONENT / HAS_SUBCOMPONENT /
HAS_CONNECTION edges for the device asset layer of the FaultDx knowledge graph.

Module layout
-------------
config      — YAML-backed config loader (replaces cad_tool src/config.py)
parser      — STEP file parser (stdlib only, AP203/AP214/AP242)
hierarchy   — NAUO → product tree resolver
geometry    — world transforms, AABBs, world-space face data  (requires numpy)
relationships — mate inference: sibling + cousin pass
kg_edges    — per-NAUO depth + hierarchy edge classification
triples     — schema v3.2 emitter (Station/Module/Component/SubComponent nodes + edges)
validate    — stdlib JSON-Schema validator
stats       — extraction summary
bom         — BOM XLSX loader + normaliser  (requires pandas + openpyxl)

Entry points (scripts/build_graph/)
------------------------------------
run_cad_extract.py  — full pipeline: parse → hierarchy → geometry →
                       mates → triples → validate → write outputs
run_bom_match.py    — BOM ↔ STEP matcher

Station convention (schema v3.2, Option A)
------------------------------------------
The STEP root assembly product is mapped to one Station node:
  station_id   = cfg["dataset"]          (e.g. "Y24_CSTN_Di")
  station_type = root PRODUCT.name from STEP

One STEP file → one Station. Multi-unit distinction requires a future
station_registry.yaml (not implemented in this phase).

Per-NAUO depth invariant
------------------------
Depth is computed per NAUO along the canonical-parent-NAUO chain, NOT by
BFS-shallowest-depth-per-product. Do not regress this — see kg_edges.py and
docs/agents/cad_extract.md for the full explanation.
"""

from __future__ import annotations
