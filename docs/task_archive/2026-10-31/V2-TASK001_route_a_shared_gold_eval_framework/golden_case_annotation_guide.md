# V2-TASK001 Route A golden-case annotation guide

## Purpose and status

`contracts/evaluation/route_a_golden_case_v1.schema.json` is a **DRAFT**
graph-independent domain-gold contract. This guide governs creation of labels
for the shared old-KG/new-KG comparison. It does not authorize a data read,
create a golden label, or freeze an evaluation policy.

The contract records diagnostic-domain expectations, not graph node IDs,
Cypher, adapter mappings, retrieval output, or generated answer text.

## Annotation unit

One case represents one underlying scenario. Query variants must retain the
same `scenario_id`; variants do not create independent evidence or additional
split capacity. Each case records:

- its partition, query language, equipment scope, query type, and difficulty;
- an abstention expectation;
- one or more acceptable cause labels and acceptable cause/action pairs;
- source anchors for every accepted label; and
- reviewer decisions and adjudication status.

Use stable domain identifiers for `cause_id` and `action_id`. A later adapter
may map them to a graph-specific identifier, but that mapping is not part of
the gold set.

## Evidence and independence rules

1. Annotate from independently governed evidence. A KG response may be placed
   in a candidate worksheet, but never copied into `expected` as authority.
2. Every accepted cause or cause/action pair needs at least one source anchor
   with source review state and allowed-use metadata.
3. Do not use Route B document evidence or Route C case candidates as confirmed
   Route A truth. Preserve their different route status when they are relevant
   to an annotation discussion.
4. `candidate_worksheet_only` and `graph_derived_prohibited` are not eligible
   for reviewed domain-correctness reporting.
5. `reviewed` and `adjudicated` labels require `independent_evidence` and at
   least one review record. Only those two maturity states may be exported to a
   reviewed expert-ranking run.

## Review and adjudication

An annotator proposes a label and anchors. A domain reviewer independently
records `accept`, `reject`, `replace`, or `abstain`. Disagreement is retained;
an adjudicator resolves it only with anchored evidence. Do not overwrite the
earlier review record.

Use `provisional` or `assumed_label_provisional` when this workflow is
incomplete. Such cases may support framework or calibration work, but not a
reviewed domain-correctness or release claim.

## Split and blind controls

Assign the partition before adapter evaluation and before tuning. Split by
`scenario_id`, never query wording. The blind partition must contain reviewed
or adjudicated labels and remain unavailable to graph construction, retrieval,
prompt tuning, and calibration. The case contract does not replace access
control: keep blind labels in a governed location separate from the query-only
blind execution input.

## Export to expert ranking

Export only the following domain fields into
`route_a_expert_ranking_input_v1`:

- `case_id`, `scenario_id`, `partition`, and `label_maturity`;
- `expected.abstention`;
- the accepted `cause_id` values; and
- the accepted `(cause_id, action_id)` pairs.

The exporter must preserve provenance in the golden-case artifact, enforce the
ranking contract's top-5 result limit, and reject a reviewed-ranking claim when
any exported case is not `reviewed` or `adjudicated`.

## Required review before freeze

The data workflow lead verifies provenance, allowed use, partition handling,
and route boundaries. The data contract engineer reviews compatibility with the
expert-ranking input. Domain reviewers approve label semantics. The quality
reviewer independently verifies split integrity, label independence, and the
calibration/mutation plan. `FROZEN` requires those approvals; schema validity
alone is insufficient.
