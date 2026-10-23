# CAD Extract Pipeline Runbook

> Rehomed from the former CAD Extract agent guide. This is an operational pipeline guide, not an active agent role. Its schema-version snapshot is historical until checked against the current task, contract, config, and tests.

## Purpose

This guide covers `services/graph/cad_extract/` — the STEP → KG triple extraction
pipeline ported from `cad_tool` Phase 1 (validated 2026-05-05 on `Y24_CSTN_Di`).

It is the authoritative reference for any agent touching the CAD extract pipeline.
Read it before modifying any module in `services/graph/cad_extract/` or
`scripts/build_graph/`.

---

## Current State (schema v3.2)

**Done and validated:**
- Hand-rolled STEP parser (`parser.py`) — stdlib only, AP203/AP214/AP242
- Hierarchy resolver (`hierarchy.py`) — `NAUO → PD → PDF → PRODUCT` walk
- Orphan handling: products with no parent and no children are split from roots
- Geometry index (`geometry.py`) — world transforms, AABBs, world-space face data
- Mate inference (`relationships.py`) — sibling + cousin pass, four connection types,
  canonical `nauo_a < nauo_b` ordering, per-instance degree cap, confidence floor
- KG hierarchy edges (`kg_edges.py`) — per-NAUO depth (see critical invariant below)
- Triple emitter (`triples.py`) — schema v3.2 `{nodes, edges}` bundle
  Station / Module / Component / SubComponent nodes, all edge types including
  HAS_MODULE from a real Station node (no QPL placeholder)
- Schema validator (`validate.py`) — stdlib mini JSON-Schema engine, v3.2 clean
- Config loader (`config.py`) — YAML-backed; all thresholds come from
  `configs/cad_extract.yaml`
- BOM loader + matcher (`bom.py`) — indented and flat BOM XLSX, fuzzy matching
- CLI scripts (`scripts/build_graph/run_cad_extract.py`, `run_bom_match.py`,
  `triples_to_cypher.py`, `load_triples_to_neo4j.py`)
  — Neo4j import behavior is defined by these scripts and the active task; there is no separate active Neo4j agent guide.

**Validated on `Y24_C1STN_Di_STP.STEP` (832 MB):**
- 1,221 unique products, 2,751 NAUOs, 12,513 mate edges, max depth 8
- node:Station=1, node:Module=23, node:Component=361, node:SubComponent=2,367
- `validation.json errors=0` under schema v3.2

---

## Critical Invariant: Per-NAUO Depth

**Do not regress this.** It is the single most important correctness property in the
pipeline.

Earlier code used BFS-shallowest-depth-per-product. That broke DAGs where a
sub-assembly is reused at multiple depths: the same product became `M_` on one NAUO
and `C_` on another, producing `HAS_COMPONENT(C_→C_)` edges that violate the schema.
The validator caught 75 such defects on the Di file.

**The fix:** depth is computed **per NAUO** along the canonical-parent-NAUO chain
(`compute_nauo_depths` in `kg_edges.py`):

- Root NAUO (parent_product_ref ∈ `hierarchy.roots`) → depth 1
- Otherwise: `depth(N) = depth(canonical_NAUO[parent_product]) + 1`

`canonical_parent_nauo_by_product` is the smallest-id NAUO that introduces each
non-root product. Both `compute_nauo_depths` and `emit_triples` use it to keep depth
assignments consistent.

**If you find yourself wanting per-product depth, stop and reconsider.** You almost
certainly want per-NAUO depth.

---

## Tree-flattening Rules

- depth-1 NAUO under root → `Module` node (`M_<nauo_id>`)
- depth-2 NAUO → `Component` node (`C_<nauo_id>`)
- depth ≥ 3 NAUO → `SubComponent` node (`SC_<nauo_id>`)
- One node per resolved NAUO
- Hierarchy edges collapse to the canonical-parent NAUO of the parent product
- `HAS_SUBCOMPONENT` from-end is `Component` (depth 2) or `SubComponent` (depth ≥ 3); to-end is always `SubComponent`

**Known edge case:** depth-1 NAUOs whose product is a STEP leaf (no further NAUO
children) get classified as Module despite being atomic parts. On Di that's 5 NAUOs /
3 distinct products. Do not auto-fix — downstream can redefine Module boundaries
based on additional context.

**Known edge case:** The Di file has one 199-child mega-Module (`AE1-387-D274-10000`).
This is correct by the STEP hierarchy. If a future data source provides finer
module-to-QPL mapping, it can redefine the boundaries during ingestion.

---

## Station Convention (schema v3.2, Option A)

The STEP root assembly product maps directly to one Station node per extraction run:

```
station_id   = cfg.dataset       (e.g. "Y24_CSTN_Di", from configs/cad_extract.yaml)
station_type = root PRODUCT.name  (from the STEP file)
station node id = "ST_{station_id}"
```

**Why Option A was chosen (2026-05-06):** DFM data is not in scope for TASK-015,
and there is no QPL/station registry available. The STEP root is the only unambiguous
per-file identity. This avoids null station_id values in schema v3.2.

**Known limitation:** one STEP file → one Station node. Multiple physical units of
the same model cannot be distinguished without a `station_registry.yaml` keyed by
serial number or line position. This is out of scope for the current phase.

---

## Mate Inference Notes

- Sibling pass (same parent NAUO) and cousin pass (cross-subassembly via spatial
  grid) both feed `infer_mates` in `relationships.py`
- Four surface types handled: PLANE, CYLINDRICAL, CONICAL, SPHERICAL, TOROIDAL
- Tangent suppression: `tangent` edges are dropped when `planar_contact` or
  `concentric` was already detected for the same pair (fix applied 2026-05-08).
  Reduced total HAS_CONNECTION from 14,040 → 12,513 on Di.
- Proximity mates are fallback-only: emitted only when no face-based mate was
  detected for an AABB-overlapping pair

All thresholds live in `configs/cad_extract.yaml` and the `MateInferenceConfig`
dataclass. Pass `cfg.mate` to `infer_mates`; do not hardcode any threshold.

---

## Supported STEP Schemas

`FILE_SCHEMA` values seen in project data:
- `CONFIG_CONTROL_DESIGN` (AP203) — SolidWorks 2023 default
- `AUTOMOTIVE_DESIGN` (AP214)
- `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING` (AP242)

All three route through the same `PD → PDF → PRODUCT` resolver. AP203's
`PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE` (subtype of AP214's PDF) is
handled in `build_hierarchy`.

---

## Schema v3.1 → v3.2 Changes

| v3.1 | v3.2 |
|---|---|
| `QPL` node (placeholder or real) | Removed |
| `Module.qpl_id` (string or null) | Replaced by `Module.station_id` (always a real string) |
| `HAS_MODULE.from = null` until DFM | `HAS_MODULE.from = "ST_{station_id}"` (always set) |
| Two `expected_violations` in validator | Zero expected violations in v3.2 |
| Cypher/Neo4j scripts create QPL placeholder | Cypher/Neo4j scripts create Station node |

---

## Output File Reference

All written to `data/processed/{dataset}_matched/` (configurable via YAML):

| File | Producer | Contents |
|---|---|---|
| `parts_list.json` | `run_cad_extract.py` | `[{bom名称, bom型号, bom数量}]` |
| `stats.json` | `run_cad_extract.py` | summary, hierarchy depth, roots, orphans, warnings |
| `mates_list.json` | `run_cad_extract.py` | per-NAUO mate detail (debug sidecar) |
| `hierarchy_edges.json` | `run_cad_extract.py` | per-NAUO `{nauo_id, depth, edge_type, ...}` |
| `triples.json` | `run_cad_extract.py` | schema v3.2 `{schema_version, nodes, edges}` |
| `validation.json` | `run_cad_extract.py` | schema compliance: `errors`, `expected_violations` |
| `bom_match.json` | `run_bom_match.py` | matched / qty_mismatch / fuzzy_candidates / ... |
| `triples.cypher` | `triples_to_cypher.py` | generated Cypher for cypher-shell |

---

## Data Safety

- Raw STEP and BOM files in `data/raw/` are gitignored
- Never commit raw CAD data — files are large and may contain customer IP
- `data/processed/` is gitignored unless the user explicitly asks to commit an example

---

## Config Override Pattern

To run against a different dataset without changing the code:

```yaml
# configs/cad_extract.yaml
dataset: "Y25_CSTN_Va"
```

Or pass `--config` to any script:

```powershell
python scripts/build_graph/run_cad_extract.py --config configs/y25_va.yaml
```

All thresholds in `mate_inference` and `bom_match` sections override module defaults
when passed via `cfg.mate` and `cfg.bom` to the relevant functions.
