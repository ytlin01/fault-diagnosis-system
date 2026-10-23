# V2-TASK001 subtask — expert-ranking first run

## Goal

Assemble the first reviewed expert-ranking input from gold v2 and execute
the frozen-policy evaluator run, producing a registered report. This is the
first run of the `route_a_expert_ranking_metrics_v1` policy against
attestation-reviewed canonical labels.

## Parent and ownership

- Parent: `V2-TASK001_route_a_shared_gold_eval_framework`
- Input assembly and run owner: `data_quality_reviewer`
- Pairing and abstention decisions: data owner with domain review (same
  in-session decision shape as the canonical-mapping acceptance)
- Candidate-ranking supply: `data_pipeline_kg_engineer` owners of the old/new
  KG adapters (separately owned; this subtask consumes frozen output, never
  implements adapters)
- Provenance review: `data_workflow_lead`

## Inputs

- `data/eval/route_a/v2_task001_c1stn_error_code_reviewed_gold_v2.json`
  (12 mapped cases, 3 explicitly unmapped)
- `data/eval/route_a/v2_task001_c1stn_canonical_mapping_proposal_v1.json`
  and its acceptance event
- `contracts/evaluation/route_a_expert_ranking_input_v1.schema.json`
  (frozen metric policy)
- `services/evaluation/route_a_expert_ranking.py` and
  `scripts/eval/eval_route_a_expert_ranking.py`
- frozen candidate rankings with candidate identity
  (`candidate_id`, `graph_version`, `snapshot_id`, `data_maturity`,
  `config_digest`) supplied by the KG adapter owner

Any direct or indirect read under `data/` requires its own explicit bounded
permission; earlier permissions do not transfer.

## Scope

1. Propose cause/action pairing for the 12 mapped cases (currently
   `pairing_state=not_asserted`) with per-pair evidence; data owner accepts,
   edits, or rejects each pairing.
2. Propose abstention encoding for the 3 unmapped cases
   (RA-SEED-C1STN-EC-002/005/006): `required`, `allowed`, or exclusion with
   a recorded reason.
3. Consume the frozen candidate rankings; verify candidate identity and
   config digest; reject unfrozen or unidentified candidates.
4. Assemble the input, validate against the frozen contract, execute the
   evaluator, and register the report.
5. Report eligible and provisional results separately; abstention-gate
   failures are never hidden behind aggregate scores.

## Non-goals

- No KG adapter, snapshot, or retrieval implementation.
- No static-coverage execution, blind execution, or blind-CLI repair (the
  blind bank stays sealed; its argument-ordering fix is separate work).
- No threshold tuning, metric changes, or nDCG addition (frozen policy).
- No release, serving, or KG-activation claim.

## Write set

- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/subtasks/expert_ranking_first_run/`
- new pairing/abstention/input/report artifacts under
  `data/eval/route_a/` under explicit bounded permission
- corresponding `source_inventory.csv` and `annotation_log.jsonl` appends
  under the same permission

## Decision states

- `planned` (this package) -> `pairing_and_abstention_decided` ->
  `input_assembled` -> `run_executed` -> `report_registered`.

A failed contract validation or unidentified candidate returns the subtask
to `planned` with a recorded blocker.
