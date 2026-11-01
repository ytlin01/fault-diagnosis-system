# Route A golden expert-annotation CLI

`scripts/eval/annotate_route_a_golden.py` is a local, interactive tool for
recording expert annotation decisions. It is intentionally separate from KG
retrieval: it displays only a governed annotation queue and controlled domain
vocabularies, never graph rankings or adapter output.

## Queue contract

The CLI accepts a JSON object with:

- `schema_version: "route_a_annotation_queue_v1"` and a `queue_id`;
- `cases`, each with `case_id`, `scenario_id`, `partition`, `query`,
  `query_language`, and coverage tags (`query_type`, `difficulty`, and
  `equipment_scope`);
- optional `cause_catalog` entries (`cause_id`, `display_name`); and
- optional `cause_action_pair_catalog` entries (`cause_id`, `action_id`,
  `display_name`).

A provisional masked-source seed may also include `source_context`. The CLI
labels and displays it as `source_suggested_only`; it is candidate worksheet
material, never an accepted cause/action label. Graph IDs, graph nodes, Cypher,
rankings, and retrieval results are prohibited from this context.

The catalogs are controlled domain vocabularies. They must not be generated
from KG results. Queue content must be approved and masked when required.

## Run

```powershell
python scripts/eval/annotate_route_a_golden.py `
  --queue <approved-queue.json> `
  --output <local-review-log.jsonl> `
  --reviewer-id <reviewer-id> `
  --role domain_reviewer
```

The output is append-only JSONL. Each record includes the selected causes and
cause/action pairs, source anchors, decision, maturity, abstention expectation,
and timestamp. It is a review record, not a direct mutation of the golden set.

Blind cases are hidden and rejected by default. Access requires an explicit
`--allow-blind` flag and the governed label-access process; that flag does not
replace access control.

## Enforced governance checks

The local validator rejects:

- unknown query-type or difficulty coverage tags;
- duplicate case IDs and scenario variants assigned across partitions;
- catalogued cause/action pairs whose cause is outside the cause catalog;
- selected cause/action pairs whose cause was not selected;
- `adjudicated` maturity set by anyone other than an adjudicator;
- provisional blind labels, even when blind access was explicitly enabled;
- reviewed/adjudicated labels whose anchors are pending or not allowed for
  evaluation; and
- label-bearing required abstentions or unexpected abstentions without a
  selected cause.

## Promotion boundary

Only independently anchored `reviewed` or `adjudicated` decisions may later be
adjudicated into `route_a_golden_case_v1` and exported to a reviewed
expert-ranking run. Provisional records support workflow and calibration only.
