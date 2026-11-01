# V2-TASK024 acceptance

## Governance and authority

- [ ] Both source PDFs are registered with source ID, snapshot/version, owner,
  sensitivity, masking state, lineage, route eligibility, and retention.
- [ ] The two PDFs remain evidence-only references; no legacy report statement
  is treated as a Schema 4.2 promotion or release decision.
- [ ] `mapped`, extraction success, semantic similarity, and historical
  completeness cannot set `reviewed`, `serving_safe`, or promotion state.
- [ ] Unmapped, ambiguous, conflicting, duplicate, and quantity-mismatch cases
  have reason-coded review or exclusion records.
- [ ] Co-source facts are not counted as independent corroboration across
  Route A and Route B.

## Contract and canonicalization

- [ ] Published Route A assertions use Schema 4.2 `MappingRecord` authority,
  reviewed state, serving safety, promotion evidence, source snapshot, and
  deterministic IDs.
- [ ] Alias matches emit all relevant candidates when the text contains
  multiple physical signals; longest-alias selection is not a final truth rule.
- [ ] Short aliases such as `PLC` are guarded against false positives and are
  routed to ambiguity or human review where context is insufficient.
- [ ] Cause-to-Action edges require explicit reviewed
  `cause_action_pair_id`; no Cartesian product is generated.
- [ ] Historical `HAS_STEP` is migrated only through a reviewed adapter to
  `HAS_STEPS`; both are not published as parallel truth edges.

## Pipeline and graph quality

- [ ] Equivalent synthetic inputs and configuration produce byte-equivalent
  test outputs and manifests.
- [ ] Topology hierarchy, parent links, IDs, aliases, connection types,
  endpoint resolution, duplicate detection, cycles, and dangling edges are
  checked independently.
- [ ] BOM version suffix normalization is deterministic; exact matches,
  quantity mismatches, and unresolved items remain distinct outcomes.
- [ ] The report's historical count inconsistencies are represented as review
  cases rather than silently reconciled.

## Query and evaluation safety

- [ ] Historical Q1-Q5 intents are mapped to a named, parameterized,
  read-only Schema 4.2 query registry before consumer use.
- [ ] `success`, `no_result`, `ambiguous`, `excluded`, `abstain`, and `error`
  remain observably distinct.
- [ ] Candidate and unreviewed content is filtered without leaking excluded
  content.
- [ ] Test labels are independent of the candidate under review, and split
  leakage is checked.
- [ ] Old/new outcomes report both-pass, both-fail, old-pass/new-fail,
  old-fail/new-pass, excluded, and non-applicable cases.

## Delivery validation

- [ ] `test_set_v1.jsonl` parses as one valid JSON object per line.
- [ ] Every test case has a unique ID, applicability, synthetic fixture,
  expected result, failure reason or gate, and source-basis reference.
- [ ] No file under `data/` is modified by this task.
- [ ] No graph import, runtime activation, release, commit, or push is claimed.
