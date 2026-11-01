# Old-KG candidate supply — notes

## 2026-08-21 - executed through candidates_supplied (zero-coverage baseline)

### Graph verification and export

- Live old KG (user-started) verified read-only: diagnostic-layer counts
  match the 2026-05-18 audit exactly (116 ErrorCode / 116 Fault / 236
  Cause / 218 Action / 376 ActionStep). TRIGGERS diverged (7 components vs
  11) and the divergence is explained, not unresolved: the audit's B02 note
  named 4 orphan `DR_*` components whose removal was deferred; they are
  verifiably absent now, and TRIGGERS is never traversed by the 15 gold
  queries (all anchor on error codes).
- `data/eval/route_a/old_tpdx_chain_rows_v1.json` - 236 frozen
  Cause-[:RESOLVED_BY]->Action rows with EC context, snapshot
  `sha256:bd3d0981...`. No mutating query ran.

### Findings (both registered as evidence)

1. **Coverage gap**: 0/13 gold error codes exist as ErrorCode nodes in the
   old KG. The graph's 116-code universe (C01/C02/W99/V03 families) is
   disjoint from the gold seed sample on this set. Retrieval anchors on
   the extracted code and returns not-found for every gold case.
2. **Vocabulary gap**: graph cause/action texts are raw field narratives
   (numbered steps, dated incidents, one cause is "Pending"); exact
   normalized text mapping matches 0/97 causes and 0/90 actions.

### Mapping acceptance

Data owner reviewed the zero-match proposal in session after elaboration
and accepted it as-is; approved mapping written
(`old_tpdx_canonical_mapping_approved_v1.json`, approved=true, zero
matches by design of the exact-text rule). Every crosswalk bridge would be
a human domain decision; none was automated or invented.

### Input assembly and run

- Input `v2_task001_c1stn_expert_ranking_input_old_kg_v1.json`:
  15 cases, 0 with ranked results, 15 abstained; candidate identity
  `old_tpdx_baseline_v1` / `neo4j_cad_kg_v3_2` / snapshot
  `sha256:bd3d0981...` / `assumed_label_provisional` / config digest of
  `configs/route_a_expert_ranking_old_kg_v1.json`. Passes the frozen
  contract validator.
- Report `v2_task001_c1stn_expert_ranking_report_old_kg_v1.json`:
  primary `cause_action_pair_recall_at_3=0.0`; 12 abstention-gate
  failures (the not_expected cases abstained); 3 required-abstention
  passes; no composite score. Registered as eval run
  `eval_20260821T043050Z_8480f9a6`.

### Validation

- 27 new unit tests (mapping 10, candidate ranking 17) plus the TASK001
  suite - 49 tests in the touched modules, all green; CLI smoke passed.
- Deterministic rebuilds verified byte-identical for the assembled input
  and the report.
- Governance reparse: 178 inventory rows unique, 15 annotation events,
  4 eval runs; workflow guard and git diff --check pass.

### Changed files

- New: subtask package; `services/evaluation/old_tpdx_expert_ranking_mapping.py`;
  `services/evaluation/route_a_candidate_ranking.py`;
  `scripts/eval/export_old_tpdx_chain_rows.py`;
  `scripts/eval/build_old_tpdx_canonical_mapping_v1.py`;
  `scripts/eval/build_route_a_expert_ranking_input_v1.py`;
  `configs/route_a_expert_ranking_old_kg_v1.json`;
  `tests/unit/test_old_tpdx_expert_ranking_mapping.py`;
  `tests/unit/test_route_a_candidate_ranking.py`;
  5 new artifacts under `data/eval/route_a/` + governance appends.

### Risks and resolved decision

- The baseline is a coverage measurement, not a ranking-quality
  measurement; it must not be quoted as old-KG diagnostic quality.
- Resolved 2026-08-21 (data owner, in session): bounded seed read
  computed the overlap — **3 of 215 distinct seed codes (1.4%)**, all in
  the N03 family. The old KG additionally carries V(26)+W(21) code
  families absent from the current seed and is missing 98.6% of seed
  codes; the two EC universes are different vintages/scopes, not subsets.
  All 3 shared codes carry divergent fault content (e.g.
  N03OOOO-01-03: seed = barcode-scanner connect timeout, graph fault =
  Hive通讯异常) and 2 of 3 include placeholder `pending` causes (verified
  read-only). A covered-case baseline on this overlap would be noise.
- Decision: `old_kg_baseline_concluded_not_signal_bearing`, registered as
  `old_kg_seed_overlap_analyzed`. The zero-coverage report stands as the
  accurate measurement; the framework is proven end-to-end. Requirement
  carried to V2-TASK003: new-KG ingestion must normalize to the reviewed
  cause/action vocabulary or ship a reviewed crosswalk.

### State

Subtask decision state: `candidates_supplied` (graph_verified ->
chain_exported -> mapping_approved -> candidates_supplied all reached);
baseline conclusion recorded, subtask complete.

## 2026-08-20 - planned

### Plan

- Rebuild the old-TP-DX adapter (mapping service recoverable from prior
  bytecode design), export frozen chain rows from the live old KG, propose
  the exact-text canonical mapping for data-owner approval, and supply
  per-case candidate rankings through the real retrieval path for the
  `expert_ranking_first_run` subtask.

### Current inputs in place

- Gold v3: 15 cases, `pairing_state=asserted` (5 cases / 11 pairs, 12
  `not_expected` + 3 `required` abstention).
- Live old KG started by the user (bolt://127.0.0.1:7687); read-only
  access via existing `.env` credentials.
- Existing retrieval path: `canonicalize_query` ->
  `execute_text2cypher(intent=diagnostic_chain)` with error_code anchor
  priority.
- Evaluator and its CLI are ready; run registration convention exists
  (`eval_run_log.record`).

### Design decisions frozen in this package

- Ranking rule: executor row order; dedup by normalized cause text with
  first-seen action union; top 5; unmapped causes keep rank as
  `unmapped:<digest8>` pseudo-ids; no scores. Hashed into `config_digest`
  via `configs/route_a_expert_ranking_old_kg_v1.json`.
- Mapping: exact normalized text only; proposed -> data-owner approval
  before any scored use; graph element IDs stay inside the mapping
  artifact.
- Candidate maturity: `assumed_label_provisional` (mandated for the old
  KG).
- Abstention observed, never tuned.

### Open blockers

- [ ] Bounded permission for live read-only Neo4j queries, gold v3 read,
      new `data/eval/route_a/` artifacts, and governance appends.

### State

Subtask decision state: `planned`.
