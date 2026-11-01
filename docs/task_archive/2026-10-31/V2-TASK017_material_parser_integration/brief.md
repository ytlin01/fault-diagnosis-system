# V2-TASK017 Material parser integration

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_contract_engineer`, `data_workflow_lead`, independent
  `data_quality_reviewer`
- Decision state: `planned`
- Source/candidate version: S material-layer handoff parser and synthetic suite;
  frozen TPDX Schema 4.2 contract (`FROZEN` 2026-08-10)
- Dependencies: completed material-schema compatibility review confirmed by the
  user; its authoritative artifacts and decision are recorded under
  "Authoritative compatibility decision" below (recorded 2026-08-27)
- Downstream consumers: Route A material KG candidate, graph import boundary,
  asset/diagnostic joins, and `V2-TASK016` independent validation

## Goal

Selectively reimplement S's governed material parser against the current
reviewed material/TPDX contract boundary for the single governed BOM04
replacement-list input (L_ReplacementList), producing deterministic,
manifested, reviewable material nodes, candidates, exclusions, and
security evidence without carrying forward the obsolete Phase 1 schema or
task system.

## Background

S's cleaned material handoff contains an XLSX parser, a 22-test synthetic suite,
safe configuration examples, and historical Schema v4.0 documents. The user
confirmed that material-schema compatibility review is already complete.
Historical parser behavior remains reference input only: current implementation
must use the recorded compatibility decision and the frozen Schema 4.2
contract, preserve `MappingRecord` provenance and Route A promotion rules, and
must not silently revive Schema v4.0 as a second contract.

## Authoritative compatibility decision (recorded 2026-08-27)

No standalone material-titled compatibility artifact exists in the repository.
The authoritative basis for the material contract surface is the frozen
Schema 4.2 pair, designated by the V2-TASK012 freeze decision as the durable
technical and compatibility decision record:

- `contracts/schema/tpdx_kg_schema_v4_2.schema.json` (SHA-256
  `1fb4d2ad4dea63cb0a875ffb1dd941a4fa86387e6bb92a58f9cb229f253f4310`)
- `contracts/schema/tpdx_kg_ontology_v4_2.md` (SHA-256
  `27e9bf79098a5e29787425f6c3b4287de022db6809014bd1544c6b94f7c9fd2b`)
- Freeze provenance: the V2-TASK012 notes entry "2026-08-10 - independent
  review accepted and Schema 4.2 frozen"; the `CHANGELOG.md` 2026-08-10
  freeze record and artifact-integrity snapshot; `consumer_impact_matrix.md`
  (independent reviewer N `READY`, workflow-lead freeze). Both digests were
  re-verified against the current working tree on 2026-08-27. The earlier
  "working baseline" wording in this brief is superseded: the contract is
  `FROZEN`.

Approved material node/relationship surface (Schema 4.2 ontology section 4):
node `ReplacementPart` (required `replacement_part_id` matching
`^RP_[a-f0-9]{64}$`, `canonical_name`, `identity_rule_version`; optional
`specification`, `aliases`, `replacement_policy`) and relationships
`REPLACEMENT_FOR` (ReplacementPart -> Module/Component/SubComponent) and
`REQUIRES_PART` (Action -> ReplacementPart), each carrying only `source`,
`extracted_from`, and optional `confidence`. No other material node or
relationship is approved.

Data-owner decisions recorded in session on 2026-08-27 (binding for this
task's implementation):

1. Strict Schema 4.2 surface: one `ReplacementPart` label for both BOM03
   spare rows and BOM04 consumable rows; no invented vocabulary
   (`replacement_policy` remains null); no Schema v4.0 labels or
   relationships revived.
2. The v4.0 `MENTIONED_IN` stage is dropped entirely; the v2 parser performs
   no fault-text mention scanning.
3. Consumables are emitted as `ReplacementPart` nodes; their station-usage
   linkage has no Schema 4.2 surface and is recorded as review-queue
   candidates only, never as edges.
4. Edges require exact endpoint resolution; partial, unresolved, or
   ambiguous matches go to the review queue, not to confidence-scored edges.
5. Scope reduction (recorded 2026-08-27, same session, superseding the
   BOM03 half of decisions 1 and 4): the parser processes only the governed
   BOM04 replacement list (L_ReplacementList, registered as
   `raw__C1STN_bom_material__L_ReplacementList`). The BOM03 spare-BOM path,
   topology endpoint resolution, and `REPLACEMENT_FOR` edge emission were
   removed from the config, service, runner, and tests. Output is
   `ReplacementPart` nodes only; decisions 2, 3, and the review-queue
   semantics are unchanged. Reintroducing edges requires a new recorded
   decision and a governed topology source.
6. Masking of the governed BOM04 input is tracked as subtask
   `c1stn_replacement_list_masking` under this package (user decision,
   recorded 2026-09-01). The dedicated masking source
   `c1stn_replacement_list` in `configs/masking_rules.yaml` produces
   separately governed masked canonical and serving derivatives; masking
   never gates, promotes, or corroborates parser candidates.

Schema v4.0 to Schema 4.2 mapping (historical handoff -> approved surface):

| v4.0 handoff | Schema 4.2 disposition |
|---|---|
| `Consumable` + `Spare` nodes, `CONS_`/`SPARE_` 12-hex ids | single `ReplacementPart` node, `RP_` 64-hex salted id |
| spec folded into id hash only | stored as nullable `specification` property |
| `IS_SPARE_FOR` (deepest-hierarchy match) | removed with the BOM03 path (decision 5, 2026-08-27); node-only output |
| `USES_CONSUMABLE` (Station/Module -> Consumable) | dropped; review-queue candidate (no 4.2 surface) |
| `MENTIONED_IN` (material -> Fault text) | dropped entirely |
| inline edge provenance (`source_file_id`, `source_row`, `*_hash`) | edge props `source`/`extracted_from`; full lineage in sidecar records |
| partial-match edges at confidence 0.6/0.7 | exact match or review queue |

The handoff's synthetic test suite passed locally on 2026-07-31. Real BOMs,
base triples, aliases, salts, outputs, and match metrics were not inspected.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- authoritative completed material-schema compatibility decision, once named
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`
- `contracts/schema/tpdx_kg_ontology_v4_2.md`
- S's cleaned material handoff manifest, parser, tests, runbook, and safe
  examples from the user-provided local handoff package
- approved governed BOM03/BOM04, base-triple, alias, and salt inputs only after
  exact paths and permission are recorded

Before inspecting the contents of any file under `data/`, ask the user for
explicit permission for the intended path or bounded scope. Local handoff data
or production-like inputs require the same governed handling even when stored
outside this repository.

## Scope

- Record the authoritative completed compatibility decision and translate it
  into parser input/output validation rules.
- Reimplement BOM04 replacement-list (`L_ReplacementList`) extraction without
  copying obsolete contract assumptions.
- Preserve deterministic canonicalization, configured salted identities,
  source row/sheet lineage, missingness, collision audit, and stable ordering.
- Emit a node-only candidate (no material relationships); station usage stays
  a review-queue candidate per decision 3.
- Send unresolved, ambiguous, or unsafe joins to a candidate/review queue rather
  than inventing graph edges.
- Fail closed on forbidden-value leakage, missing required salt, invalid schema,
  unsafe output, or ungoverned inputs.
- Produce rerunnable candidate, candidate-review, exclusion, merge-audit,
  leakage-report, and run-manifest artifacts.
- Add synthetic positive, negative, drift, determinism, and security tests.
- Prepare the candidate handoff for `V2-TASK016` without importing it into the
  released graph.
- Track governed masking of the BOM04 input as subtask
  `c1stn_replacement_list_masking`, producing masked canonical/serving
  derivatives that stay separate from parser candidates.

## Non-goals

- No redesign of the already-reviewed material contract.
- No restoration of historical Schema v4.0 as an active parallel contract.
- No reading of real BOMs, aliases, base triples, or outputs before bounded
  permission and governance-zone confirmation.
- No inference of quantity, brand, supplier, lifecycle, station, asset, fault,
  cause, action, or step semantics not supported by approved source fields.
- No Neo4j promotion, runtime activation, release, or Data RC claim.
- No direct copy of historical task packages into the active v2 task system.

## Write set

Initial synthetic implementation writes are limited to:

- `docs/tasks/V2-TASK017_material_parser_integration/`
- `docs/tasks/V2-TASK017_material_parser_integration/subtasks/c1stn_replacement_list_masking/`
- `configs/pipelines/replacement_extract.yaml`
- `configs/masking_rules.yaml`, limited to the `c1stn_replacement_list`
  source block (masking subtask)
- `services/ingestion/material_layer_v2.py`
- `scripts/build_graph/build_material_layer_v2_candidate.py`
- `tests/unit/test_material_layer_v2.py`

No `data/` path is written by task implementation. The raw registration row
for `raw__C1STN_bom_material__L_ReplacementList` in
`data/governance/source_inventory.csv` is a data-owner governance write
(2026-08-27); the agent's read of that single row was separately permitted
on 2026-09-01. Every other real-data read or write still requires explicit
bounded permission recorded in this package before it happens.

## Failure behavior and rollback

- Invalid or unsafe runs exit nonzero and do not publish a candidate.
- Ambiguous but structurally safe records are excluded into a governed review
  artifact with reason codes and source anchors.
- Historical parser and Schema v4.0 artifacts remain unchanged as reference
  material; rollback is removal of the separate v2 candidate path with no
  change to the current graph.

## Deliverables

- [x] compatibility decision and exact active contract references recorded
- [x] deterministic v2 material parser and controlled configuration
- [x] candidate, review queue, exclusions, audits, leakage report, and manifest
- [x] exact local commands and fail-closed behavior
- [x] synthetic regression, drift, determinism, and security tests
- [x] independent-review handoff to `V2-TASK016`
  (`material_candidate_handoff_task016.md`, run `material_cef539710b861b7d`)
- [x] exact changed files, validation, risks, and state recorded in `notes.md`

## Next gate

Discuss and freeze the implementation boundary for synthetic work first. Real
data execution waits for explicit bounded permission, governed input/output
paths, controlled salt ownership, and approved base triples and aliases.
