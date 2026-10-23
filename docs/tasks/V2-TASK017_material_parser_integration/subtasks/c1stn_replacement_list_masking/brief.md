# V2-TASK017 subtask — C1STN replacement-list masking

## Goal

Create a governed masked derivative of
`data/raw/C1STN_bom_material/L_ReplacementList.xlsx` (the BOM04 replacement
list, `L_ReplacementList`) as the masking track of the V2-TASK017
material-parser line. The derivative is a separately governed masked artifact:
it is not parser truth, not a serving release, not KG-ingestion input, and not
a Route A promotion of anything.

This subtask adopts the same governed structured-masking method already used
by the `V2-TASK001` masking subtask on this branch:

`inventory -> rules -> inspect -> dry-run -> formal masking -> manifest/lineage -> audit -> derivative registration`

## Parent and ownership

- Parent: `V2-TASK017_material_parser_integration`
- Masking implementation owner: `data_pipeline_kg_engineer`
- Governance owner: `data_workflow_lead` (raw registration recorded by the
  data owner 2026-08-27)
- Independent masked-candidate review: `data_quality_reviewer`

Only one write owner may change the masking source rule or generated masking
artifacts at a time. The data owner executes every command that reads the raw
workbook or generated artifacts; the agent works config-only unless the user
grants a new, path-specific permission.

## Governed source

- Source ID: `raw__C1STN_bom_material__L_ReplacementList`
- Path: `data/raw/C1STN_bom_material/L_ReplacementList.xlsx`
- Inventory state (registered 2026-08-27, verified against
  `data/governance/source_inventory.csv` under a user-granted bounded read):
  raw, `bom_material`, `route_a`, `serving_safe=no`, `unmasked`,
  `reviewed_status=pending`
- Owner classification note: name=`耗材品名`; spec=`耗材規格`;
  linkage=`設備QPL`,`是否與D9X通用`; station=`自動化工站`,`station`;
  sensitive=`品牌`,`單價`,`耗材QPL`,`廠商 PN`,`聯繫人`,`備註`

## Configuration decision (implemented)

A dedicated source named `c1stn_replacement_list` in
`configs/masking_rules.yaml`:

- matches only `C1STN_bom_material/L_ReplacementList.xlsx`
  (`require_all_file_patterns: true`);
- selects sheet `工作表1` explicitly (single-sheet workbook, confirmed by the
  owner dry-run 2026-08-27);
- fixes the verified layout: `header_row: 1` (0-based; row 0 blank/title,
  row 1 headers), `skip_rows_after_header: 1` (field-description row), so data
  starts at Excel row 4 — aligned with `configs/pipelines/replacement_extract.yaml`
  (`header_row: 1`, `data_offset: 2`);
- allowlists exactly ten retained columns; every deferred column
  (`設備QPL`, `是否與D9X通用`, `使用壽命`, `性質`, 5X free-supply terms,
  ZZ safety stock) is dropped via `columns_keep` before masking, per the owner
  classification note;
- classification and actions:
  - Level C passthrough (canonical + serving): `耗材品名`, `耗材規格`,
    `自動化工站`, `station`;
  - Level A tokenize (canonical) / drop (serving): `品牌`, `廠商 PN`,
    `耗材QPL`, `單價`, `聯繫人` — `耗材QPL` and `單價` follow the
    owner-classified sensitive listing and override any global QPL retain;
  - Level A redact (canonical) / drop (serving) with review flag: `備註`
    (free text may embed identifiers);
- names its three governed inventory IDs (`governance_ids`): raw input,
  `processed__canonical__structured__c1stn_replacement_list`, and
  `processed__serving__structured__c1stn_replacement_list`.

## Outputs (planned names)

- canonical:
  `data/processed/canonical/structured/c1stn_replacement_list/c1stn_replacement_list_canonical.json`
- serving candidate:
  `data/processed/serving/structured/c1stn_replacement_list_serving.json`
- manifest under
  `data/processed/canonical/structured/c1stn_replacement_list/_manifests/`
- row-level lineage under
  `data/processed/canonical/structured/c1stn_replacement_list/_lineage/`
- governance summary under
  `data/processed/canonical/structured/c1stn_replacement_list/_governance/`
- one masking-log event in `data/governance/masking_log.jsonl`, joined to the
  manifest and every lineage record by the same `run_id`
- derivative registration of the canonical and serving source IDs in
  `data/governance/source_inventory.csv` after the formal run

Generated contents remain local/governed and must not be committed merely
because masking completed.

## Relationship to the parent parser

- The parser (`replacement_extract.yaml`, `material_layer_v2.py`) binds
  `bom04.source_id` to the same raw registration and keeps its own
  fail-closed leakage validation (`sensitive_columns`).
- The masked canonical/serving derivatives are separate governed artifacts.
  Masking success does not gate, review, promote, or corroborate parser
  candidates, and parser output does not change the masking derivatives. The
  two paths are co-source on the same raw workbook and never count as
  independent evidence of each other.

## Boundaries

- Raw input remains immutable.
- No raw row or dry-run preview value may be pasted into chat, task notes,
  Git, or an external service.
- Tokenize and redact actions require `FAULTDX_MASKING_SALT`, supplied by the
  data owner through a controlled local secret; it is never recorded in Git,
  notes, or artifacts.
- A masked artifact is not automatically serving-safe.
- Formal masking, post-mask audit, and artifact inspection are data-owner-run
  commands under the current permission boundary.
