# Expert-ranking first run — notes

## 2026-08-21 - run executed and report registered (zero-coverage baseline)

The candidate blocker resolved via the `old_kg_candidate_supply` subtask:
frozen old-KG adapter output with full candidate identity. The first run
under frozen `route_a_expert_ranking_metrics_v1` executed and registered:

- Input `v2_task001_c1stn_expert_ranking_input_old_kg_v1.json` (15 cases,
  0 with ranked results, 15 abstained - all gold error codes absent from
  the old KG); passes `validate_expert_ranking_input`.
- Report `v2_task001_c1stn_expert_ranking_report_old_kg_v1.json`:
  primary `cause_action_pair_recall_at_3=0.0`; abstention gate 12
  failures / 3 passes; explicit failure list; no composite score.
- Eval run `eval_20260821T043050Z_8480f9a6` in `eval_run_log.jsonl`.

Interpretation recorded with the report: this is a coverage baseline, not
a ranking-quality measurement. Findings and next decision live in the
`old_kg_candidate_supply` notes (seed-vs-old-KG EC overlap; covered-case
gold cycle; narrative-text vocabulary crosswalk).

### State

Subtask decision state: `report_registered` (all five states reached).
Follow-up signal-bearing run depends on the covered-case gold decision.

## 2026-08-19 - pairing and abstention decided; expected labels exported

### Plan

- Build a deterministic pairing and abstention proposal over gold v2's
  accepted canonical labels, review it with the data owner in session, and
  materialize the acceptance as the gold v3 expected-labels export.

### Implemented and validated

- `services/evaluation/route_a_pairing_proposal.py` - deterministic
  proposal builder; pairs = case-level cross product of accepted causes x
  accepted actions with per-pair basis (`shared_alias_evidence` when cause
  and action cite the same alias pattern in the accepted mapping proposal,
  `case_level_cross_product` otherwise); unmapped cases proposed
  `abstention=required` with their recorded unmapped reasons. Fails closed
  on wrong queue/proposal ids, missing cases, or canonical-label drift
  between gold v2 and the accepted mapping proposal.
- `scripts/eval/build_route_a_pairing_proposal_v1.py` - CLI.
- `tests/unit/test_route_a_pairing_proposal.py` - 9 unit tests.
- `data/eval/route_a/v2_task001_c1stn_pairing_abstention_proposal_v1.json`
  (SHA-256 `af90688f4c92db3c517beb97ae8a66b821212c1299211052c30711362a6f6d3c`) -
  15 cases: 11 proposed pairs across 5 cases (6 shared-evidence, 5
  cross-product flagged for binding review), 7 mapped cases with no
  reviewed action to pair, 3 unmapped cases proposed abstention=required.

### Accepted - pairing and abstention proposal v1

On 2026-08-19 the data owner reviewed the proposal in session and accepted
it as proposed:

- all 11 pair bindings including the 5 case-level cross-product pairs
  (acceptable pairs are case-level: any accepted cause with any accepted
  action);
- the 7 action-less mapped cases stay pair-less with recorded reasons;
- abstention `required` for EC-002/005/006.

Evidence is the data owner's session answers; no written review artifact
exists. Recorded as `pairing_abstention_proposal_accepted` in the
annotation log; inventory row flipped to `reviewed`.

### Implemented and validated - gold v3 with asserted pairing

- `services/evaluation/route_a_reviewed_gold.py` - added `build_gold_v3`
  (validates gold v2 and the accepted pairing proposal, rejects
  out-of-catalog pair ids and invalid abstention encodings).
- `scripts/eval/build_route_a_reviewed_gold_v3.py` - CLI.
- `tests/unit/test_route_a_reviewed_gold.py` - 5 new tests (12 total).
- `data/eval/route_a/v2_task001_c1stn_error_code_reviewed_gold_v3.json`
  (SHA-256 `471004a59a018d451f33d2a515d948b3b2c52ab426f9f0052e1c896e2d642e90`) -
  15 cases with `pairing_state=asserted`: 5 cases with 11 asserted
  `acceptable_action_pairs`, 7 `no_reviewed_action_to_pair`, 3
  `unmapped_abstention_required`; abstention encodings 12 `not_expected` /
  3 `required`; queue state
  `reviewed_by_attestation_mapping_and_pairing_confirmed`.
- Governance: gold v3 registered as `reviewed` in the inventory;
  `route_a_gold_v3_created` annotation event with digests.

### Validation

- `python -m unittest` across the TASK001 suite (reviewed gold, golden
  annotation, golden seed, expert-ranking contract, static coverage,
  canonical mapping, expert ranking, pairing proposal) - 58 tests passed.
- Deterministic rebuilds reproduced both artifact SHA-256 values exactly.
- Inventory recheck: 173 data rows, unique source IDs; annotation-log
  reparse: 12 valid events.
- `python scripts/check_workflow_guard.py` and `git diff --check` passed.

### Open blockers

- [x] Cause/action pairing proposal accepted by the data owner (2026-08-19).
- [x] Abstention encoding accepted for EC-002/005/006 (required).
- [ ] Frozen candidate rankings supplied by the KG adapter owner with full
      candidate identity (`candidate_id`, `graph_version`, `snapshot_id`,
      `data_maturity`, `config_digest`).
- [x] Bounded `data/` permissions granted in session (proposal scope and
      gold v3 scope; `data/raw` excluded by the owner's instruction and
      untouched).

### Risks and notes

- Pair acceptance is case-level; a stricter per-pair binding would need a
  new reviewed decision and a gold v4, not an edit of gold v3.
- The 7 pair-less mapped cases cannot contribute to the frozen primary
  metric `cause_action_pair_recall_at_3`; they still score cause recall and
  MRR. Attaching actions to them is an open domain decision, deliberately
  not taken.
- Candidate output was never used to choose or tune pairs, abstention
  encodings, or cutoffs.

### State

Subtask decision state: `pairing_and_abstention_decided`. Next:
`input_assembled` waits on candidate supply.

## 2026-08-18 - planned

### Plan

- Pair the 12 mapped gold-v2 cases and encode abstention for the 3 unmapped
  ones as reviewable proposals, then execute the first frozen-policy
  evaluator run against supplied candidate rankings.

### Current inputs in place

- Gold v2: 15 cases, 12 mapped, 3 unmapped with recorded reasons,
  `pairing_state=not_asserted`.
- Evaluator rebuilt and tested against the frozen contract
  (`route_a_expert_ranking_metrics_v1`).

### Open blockers

- [ ] Cause/action pairing proposal accepted by the data owner.
- [ ] Abstention encoding accepted for EC-002/005/006.
- [ ] Frozen candidate rankings supplied by the KG adapter owner with full
      candidate identity.
- [ ] Bounded `data/` permission for the new eval artifacts and governance
      appends.

### Validation

- Subtask package created with brief, acceptance, and notes; no data
  content was read; parent task notes updated with the subtask pointer.

### State

Subtask decision state: `planned`.
