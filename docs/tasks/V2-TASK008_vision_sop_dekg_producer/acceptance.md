# V2-TASK008 acceptance

## Task and safety

- [x] `V2-TASK008` was unused before task creation.
- [x] Owner, reviewers, scope, non-goals, write set, rollback, and next gate are explicit.
- [x] Implementation and tests use synthetic in-memory fixtures only.
- [x] The prohibited raw PPTX and all other `data/` contents remain unread.

## Partition behavior

- [x] Every canonical block requires exactly one reviewed disposition.
- [x] Route A selected anchors are table-only and become exact adapter exclusions.
- [x] Native text and eligible tables never enter the VLM lane.
- [x] Only reviewed image or figure-chart blocks enter the VLM lane.
- [x] Not-eligible and quarantined blocks are counted separately.
- [x] Co-source identity and non-independent-corroboration inputs are preserved.
- [x] The output contains routing identities, reasons, counts, and digest but no source content.
- [x] Missing, duplicate, unknown, cross-lane, unreviewed, and promotion-bearing input fails explicitly.

## Validation and handoff

- [x] Focused synthetic tests pass.
- [x] Existing DEKG, local-VLM, and relevant serving-projection regressions pass.
- [x] Workflow guard and diff checks pass.
- [x] Notes record exact commands/results and distinguish implementation from a real candidate run.
- [ ] The full unstructured-ingestion suite is green; two unrelated default-output-directory expectations currently disagree with the implementation.
- [ ] An authorized producer supplies exact real-source anchors before candidate generation.
- [ ] An independent quality reviewer issues the release recommendation.
