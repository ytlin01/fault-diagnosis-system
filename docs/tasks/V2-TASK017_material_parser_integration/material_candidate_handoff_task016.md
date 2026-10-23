# V2-TASK017 -> V2-TASK016 handoff: frozen replacement-list candidate

## Identity

- From: `V2-TASK017_material_parser_integration` (implementation owner:
  `data_pipeline_kg_engineer`)
- To: `V2-TASK016_material_cad_independent_validation` (independent
  reviewer: `data_quality_reviewer`)
- Date: 2026-09-01
- Handoff state: **frozen candidate, review pending**
- Freeze declaration: the artifacts of run `material_cef539710b861b7d` are
  immutable from this point. Any change — config, code, schema, input, or
  output — requires a new run under a new `run_id` and a new handoff. The
  reviewer must not modify them; findings are recorded in the `V2-TASK016`
  package only.

## Frozen run

- `run_id`: `material_cef539710b861b7d`
- `run_status`: `complete_candidate` (exit 0); `promotion_state: candidate`;
  `graph_activation: false`; rollback: no graph import, no activation.
- Exact command (data-owner executed, salt via `FAULTDX_MASKING_SALT`,
  cleared after):

```powershell
python scripts/build_graph/build_material_layer_v2_candidate.py `
  --config configs/pipelines/replacement_extract.yaml `
  --bom04 data/raw/C1STN_bom_material/L_ReplacementList.xlsx `
  --schema contracts/schema/tpdx_kg_schema_v4_2.schema.json `
  --candidate-out  "data/processed/review_pending/route_a/v2_task017_material_candidate/run1/candidate.json" `
  --exclusions-out "data/processed/review_pending/route_a/v2_task017_material_candidate/run1/exclusions.json" `
  --lineage-out    "data/processed/review_pending/route_a/v2_task017_material_candidate/run1/lineage.jsonl" `
  --audit-out      "data/processed/review_pending/route_a/v2_task017_material_candidate/run1/audit.json" `
  --leak-report-out "data/processed/review_pending/route_a/v2_task017_material_candidate/run1/leak_report.json" `
  --manifest-out   "data/processed/review_pending/route_a/v2_task017_material_candidate/run1/manifest.json"
```

### Input and environment fingerprints (manifest-declared)

| Component | Digest / value |
|---|---|
| Input workbook (`data/raw/C1STN_bom_material/L_ReplacementList.xlsx`) | sha256 `b80f1d845884f5747818e76fe76b44f8aeab239b61b9349663826754167facdf` |
| Config (`configs/pipelines/replacement_extract.yaml`) | sha256 `fda9e16522e884c39543e97343d5d6a9dcf58a13670b065d2e5e7a66070c823f` |
| Schema (`contracts/schema/tpdx_kg_schema_v4_2.schema.json`, `FROZEN`) | sha256 `1fb4d2ad4dea63cb0a875ffb1dd941a4fa86387e6bb92a58f9cb229f253f4310` (matches the brief's freeze record) |
| Code (`services/ingestion/material_layer_v2.py` + `scripts/build_graph/build_material_layer_v2_candidate.py`) | combined sha256 `96adf904dcacab3fbe0237fc7af447fa79bdeb0614b90f727c100e3ec7258c98` |
| Identity rule | `material_identity_v1`; `RP_` + sha256(salt + `name|spec`) |
| Sheet resolution | `工作表1`, header Excel row 2, `fell_back: false` |

### Frozen artifacts (all under
`data/processed/review_pending/route_a/v2_task017_material_candidate/run1/`)

| Artifact | sha256 (manifest-declared) |
|---|---|
| `candidate.json` | `2345af1dadab3c5ef097f37ce0af80d84978044d89d7e3d9c9853562d32cecfb` |
| `exclusions.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `lineage.jsonl` | `5076bd5168230ec258363a1c7ddc8af6ecdb5f3ad0ad61ca1a0bf2ea2945ad` |
| `audit.json` | `12e94732853d80c8f31b03a8411d28f3ad944162d7897a5d2e5aba0b5fa79134` |
| `leak_report.json` | `c890b27b80c1a787d2f7b0ce473d05f08d5974be01ef8067b456ae5785991349` |
| `manifest.json` | (self-describing run manifest, `material-layer-v2-candidate-run-v1`) |

Digests above are as declared by the run manifest. Independent digest
re-computation over the frozen files is part of the `V2-TASK016` review.

## What the candidate contains

- 52 `ReplacementPart` nodes from 53 consumable rows (one exact name+spec
  duplicate merged; 0 alias-collision nodes; 0 spec-missing rows);
  node-only — no relationships (brief decisions 1 and 5).
- 53 station-usage review-queue entries (`consumable_station_usage_unsupported`,
  brief decision 3) — never edges.
- 53 row-level lineage records with source anchors of the form
  `raw__C1STN_bom_material__L_ReplacementList#工作表1!r<N>`.
- Validation: JSON Schema 4.2 passed; semantic validation passed; 23
  forbidden values checked; leak count 0.

## Governance state at handoff

- Raw source registered: `raw__C1STN_bom_material__L_ReplacementList`
  (`source_inventory.csv` line 174; route_a, unmasked, pending).
- Masking track (subtask `c1stn_replacement_list_masking`): formal run
  `maskrun_20260901T034134Z_865c656a` (masking-log event
  `mask_20260901T034134Z_f3949cf9`), counts 53/53/53, audit hits classified
  by the data owner as replacement-material codes (false positives);
  derivatives registered at `source_inventory.csv` lines 175–176; the
  subtask's own independent evidence review remains open.
- Permission trail: real-data executions are data-owner run; agent reads
  under `data/` are bounded and recorded in the task notes; the raw workbook
  remains unopened by the agent.
- The masked derivatives and this parser candidate are co-source on the same
  raw workbook; neither corroborates or promotes the other. Nothing here is
  serving-safe, reviewed Route A truth, graph-imported, or released.

## Reviewer instructions (`V2-TASK016`)

1. Independently re-compute digests of the frozen artifacts and inputs
   against this document and the run manifest.
2. Verify the run joins: one `run_id` across manifest/lineage; input, config,
   schema, and code fingerprints; identity-rule conformance (`RP_` 64-hex,
   spec-in-id per config).
3. Validate contract adherence (Schema 4.2 surface only), provenance/lineage
   anchors, leakage-report completeness, and masking-state gates per the
   `V2-TASK016` acceptance.
4. If required by `V2-TASK016` acceptance, demonstrate byte-equivalent rerun
   determinism into a fresh output directory (known open item — see below).
5. Do not modify the frozen artifacts or rerun into `run1/`. Findings and
   recommendations go in the `V2-TASK016` package; failures bounce back to
   `V2-TASK017` for a new run and a new handoff.
6. Independence: the reviewer must not be the implementation author of the
   reviewed parser.

## Open items known at handoff

- Real-data rerun determinism not yet demonstrated (fresh-dir rerun must
  reproduce `material_cef539710b861b7d`).
- The task acceptance line "Approved BOM03 and BOM04 inputs are supported
  independently" predates decision 5 (BOM03 removed) and awaits rewording.
- The candidate artifacts are not registered in `source_inventory.csv`
  (optional, consistent with prior review-pending candidates).
- Masking subtask independent evidence review open (see subtask notes).
