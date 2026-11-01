# V2-TASK001_route_a_shared_gold_eval_framework

## Goal

Create one KG-independent Route A golden set and one reusable evaluation framework that can evaluate both the frozen old KG and the new KG through graph-specific adapters.

The framework is calibrated on the old KG first. The new KG is evaluated later with the same cases, labels, scoring rules, and normalized result contract.

## Priority

**P0 — start before V2-TASK002 through TASK-048.**

Framework and gold-design work may proceed immediately. The final new-KG comparison depends on V2-TASK003, but the old-KG baseline does not.

## Agent

- Data Quality Reviewer (`docs/agents/data_quality_reviewer.md`) — primary owner
- Data Workflow Lead (`docs/agents/data_workflow_lead.md`) — source provenance, review status, and gold governance
- Data Pipeline and KG Engineer (`docs/agents/data_pipeline_kg_engineer.md`) — graph adapters and query execution boundary
- Domain reviewers — independent labels and adjudication
- System/release owner — later go/no-go consumption

## Background

Existing Route A evaluation work covers several different layers:

- TASK-018A: Text2Cypher executor scenarios and live graph structural audit;
- TASK-029A: fixture-based answer structure and behavior;
- current uncommitted Route A scripts: provisional ranking and answer-to-KG groundedness checks.

These are useful inputs but do not yet provide one independently labeled domain golden set for a fair old-KG/new-KG comparison. A gold set copied from either graph's returned candidates would measure agreement with that graph, not independent diagnostic correctness.

## Required Reading

1. `AGENTS.md`
2. `HANDOFF_README.md`
3. `docs/agents/data_engineering_workflow.md`
4. `docs/agents/data_quality_reviewer.md`
5. `docs/agents/data_workflow_lead.md`
6. `docs/agents/data_pipeline_kg_engineer.md`
7. `docs/data/phase1_eval_testset_v0.md`
8. `legacy/tasks/TASK-018A_route_a_text2cypher_eval/brief.md`
9. `legacy/tasks/TASK-029A_route_a_structural_eval/`
10. `scripts/eval/eval_route_a.py`
13. `scripts/eval/eval_route_a_accuracy.py`
14. `scripts/eval/eval_route_a_faithfulness.py`
15. `scripts/eval/cli_route_a_query.py`

## Scope

### A. Evaluation model

Keep these scorecards distinct:

1. **Pipeline correctness** — whether each KG adapter retrieves and normalizes what its frozen graph contains.
2. **Domain correctness** — whether the returned diagnosis matches independently reviewed truth.
3. **Answer faithfulness and safety** — whether assembly adds unsupported claims or changes review status.

### B. Shared golden set

Define one graph-independent case contract containing stable domain concepts, acceptable causes/actions/chains, abstention expectations, source provenance, annotation maturity, and adjudication status.

Graph-specific node IDs, Cypher, labels, and relationship names must not define domain truth. They belong in versioned adapter mapping artifacts.

### C. Reusable execution boundary

Define one normalized Route A evaluation result contract. Implement or adapt:

- an old-KG adapter;
- a new-KG adapter;
- one shared scorer and report generator.

Both adapters must receive the same query/context and expose comparable ranked entities, chains, provenance, status, warnings, and operational metadata.

### D. Calibration and comparison sequence

1. Validate golden-case schema and split integrity.
2. Calibrate metric calculations on hand-checked cases.
3. Mutation-test the evaluator with controlled failures.
4. Freeze and run the old-KG baseline.
5. After V2-TASK003, add the new-KG adapter without changing shared labels.
6. Freeze configurations and run paired old/new validation.
7. Run the sealed blind partition only after the release candidates are frozen.

## Constraints

- Do not use either KG's output as the authority for domain labels.
- KG output may populate an annotation candidate worksheet, but a reviewer must accept, reject, or replace each candidate using independent evidence.
- Keep development, validation, and blind scenario partitions separate; split by underlying scenario, not query wording.
- Do not tune on the blind partition.
- Keep unreviewed labels explicitly provisional and exclude them from domain-correctness release claims.
- Do not treat Route B evidence or Route C cases as confirmed Route A truth.
- Do not overwrite or silently absorb the current uncommitted eval scripts; inventory and reuse them where their semantics match.
- Do not access or commit raw sensitive data.
- Evaluation configuration must be versioned and reproducible.

## Deliverables

- [ ] Golden-case schema and annotation guide
- [ ] Scenario registry and coverage matrix
- [ ] Development / validation / blind split protocol
- [ ] Independent annotation and adjudication workflow
- [ ] Stable domain concept and alias policy
- [ ] Normalized Route A evaluation-result contract
- [ ] Shared scorer and report format
- [ ] Old-KG adapter and frozen baseline report
- [ ] Evaluator mutation/calibration evidence
- [ ] New-KG adapter and paired comparison report after V2-TASK003
- [ ] Blind-test run manifest and leakage audit
- [ ] `notes.md` with changed files, validation, risks, and next steps

## Non-goals

- Improving KG data merely to raise evaluation scores
- Replacing existing structural, contract, or faithfulness tests
- Route B or Route C benchmark redesign
- New-KG data integration, which belongs to V2-TASK003
- Declaring provisional or graph-derived labels to be domain truth
