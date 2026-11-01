# V2-TASK001 subtask — old-KG candidate supply

## Goal

Produce the frozen candidate rankings for the 15 gold v3 cases from the old
TP-DX KG (live local Neo4j, `neo4j_cad_kg_v3_2`) with full candidate
identity, and hand them to the `expert_ranking_first_run` subtask as frozen
adapter output. This subtask owns the adapter; the first-run subtask
consumes its output and never implements adapters (its non-goals).

## Parent and ownership

- Parent: `V2-TASK001_route_a_shared_gold_eval_framework` (scope C:
  reusable execution boundary; deliverable "Old-KG adapter and frozen
  baseline report")
- Adapter implementation and export owner: `data_pipeline_kg_engineer`
- Mapping approval: data owner with domain review (in-session decision
  shape used for the canonical-mapping and pairing acceptances)
- Input assembly, evaluator run, and report registration remain owned by
  the `expert_ranking_first_run` subtask (`data_quality_reviewer`)
- Provenance review: `data_workflow_lead`

## Inputs

- `data/eval/route_a/v2_task001_c1stn_error_code_reviewed_gold_v3.json`
  (expected labels, `pairing_state=asserted`)
- Live old KG at `bolt://127.0.0.1:7687` (user-started; read-only queries
  only; credentials from `.env`, never printed)
- `contracts/evaluation/route_a_expert_ranking_input_v1.schema.json`
  (frozen candidate-identity and result shape)
- `services/retrieval/route_a_executor.py::execute_text2cypher` with
  `services/canonicalization/prekg.py::canonicalize_query` (the existing
  old-KG retrieval path; error_code anchor priority)

Any direct or indirect read under `data/` requires its own explicit bounded
permission; earlier permissions do not transfer. `data/raw` is excluded by
standing owner instruction.

## Scope

1. Verify the live old KG against the last recorded audit state
   (2026-05-18: 116 ErrorCode / 116 Fault / 236 Cause / 218 Action / 376
   ActionStep / 11 TRIGGERS components) with read-only count queries;
   record divergence. No mutating loader runs without a separate decision.
2. Export frozen chain rows (distinct Cause-[:RESOLVED_BY]->Action with
   ErrorCode context, deterministically ordered) and record the snapshot
   digest (`sha256:` over sorted compact JSON).
3. Rebuild the old-TP-DX canonical mapping service (exact normalized text
   match only — NFKC presentation forms + casefold, never fuzzy) and
   propose the mapping of graph cause/action texts to the reviewed
   vocabulary; the proposal is unusable for scored evaluation until the
   data owner approves it in session.
4. Freeze the adapter config (`configs/route_a_expert_ranking_old_kg_v1.json`):
   ranking rule (executor row order, dedup by normalized cause text
   preserving first-seen actions, top 5, unmapped causes keep their rank
   slot as `unmapped:<digest8>` pseudo-ids, no scores), retrieval knobs,
   chain query, expected audit counts. `config_digest` = sha256 of the
   config file.
5. Supply per-case candidate rankings through the real retrieval path
   (canonicalize -> execute_text2cypher(diagnostic_chain)); abstention is
   observed, never tuned — required-abstention cases that over-answer are
   recorded as gate failures.

## Non-goals

- No KG data mutation, loader runs, schema changes, or new-KG work
  (V2-TASK003/022/023 own those).
- No metric, cutoff, or policy changes (frozen `route_a_expert_ranking_metrics_v1`).
- No graph-derived label acceptance: graph output never edits gold v3.
- No blind-bank access or blind execution.
- No fuzzy/semantic matching anywhere in the mapping.

## Write set

- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/subtasks/old_kg_candidate_supply/`
- `services/evaluation/old_tpdx_expert_ranking_mapping.py`,
  `services/evaluation/route_a_candidate_ranking.py`,
  `scripts/eval/export_old_tpdx_chain_rows.py`,
  `scripts/eval/build_old_tpdx_canonical_mapping_v1.py`,
  `scripts/eval/build_route_a_expert_ranking_input_v1.py`,
  `configs/route_a_expert_ranking_old_kg_v1.json`, and unit tests
- new artifacts under `data/eval/route_a/` (chain rows, mapping proposal,
  approved mapping, candidate rankings / assembled input) under explicit
  bounded permission
- corresponding governance appends under the same permission

## Decision states

`planned` -> `graph_verified` -> `chain_exported` -> `mapping_approved` ->
`candidates_supplied`.

A counts divergence from the recorded audit, a failed contract validation,
or an unidentified/unapproved mapping returns the subtask to `planned`
with a recorded blocker.
