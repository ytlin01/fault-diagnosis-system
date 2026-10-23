# V2-TASK005 notes

## Plan

Use explicit active backlinks as the default retention rule for `docs/data/`,
retain the Route B schema-boundary decision for V2-TASK003, archive everything
else without deletion, and relocate V2-TASK001 generated review output under
`docs/outputs/`.

## Retained `docs/data/` set

- `e3_unstructured_vlm_handoff.md`
- `masking_pipeline.md`
- `phase1_eval_testset_v0.md`
- `route_b_graphrag_neo4j_desktop_runbook.md`
- `route_b_graphrag_prototype_v0.md`
- `route_b_graphrag_v1.md`
- `route_b_schema_boundary_decision.md`
- `route_c_case_hybrid_retrieval_eval.md`
- `route_c_case_light_rag_v1.md`
- `route_c_case_rag_v1.md`
- `structured_masking_runbook.md`
- `unstructured_ingestion_plan.md`

## Changed files

- 45 historical files moved from `docs/data/` to `legacy/data/docs/`.
- 12 active-v2-related files retained in `docs/data/` as listed above.
- `outputs/task044_c1stn_domain_review_20260723/` was moved to
  `docs/outputs/v2_task001_c1stn_domain_review_20260723/`, but the untracked
  workbook is no longer present in the current worktree.
- The intended workbook filename is
  `V2-TASK001_C1STN_Domain_Expert_Review.xlsx`.
- Explicit repository references to archived documents and relocated output
  paths were repaired.
- One stale current-onboarding link was corrected from a nonexistent
  data-document path to its actual `docs/onboarding/dekg_fhkb_onboarding/`
  location; its read-only attribute was restored after the edit.
- `legacy/README.md` now indexes the historical data-document archive.

## Validation

- Exact retained-set comparison passed: 12 files.
- Exact archive count passed: 45 files.
- All 57 formerly tracked `docs/data/` files exist at a retained or archived
  destination.
- Archived-path reference scan passed.
- The former root output directory is absent and stale-output path scans pass.
- Revalidation on 2026-07-24 found the intended V2-TASK001 workbook missing
  from the otherwise empty `docs/outputs/` directory. Because it was
  untracked, Git cannot restore it; regeneration requires its approved source
  input and remains outside this cleanup pass.
- Both affected workbook helper scripts compiled in memory.
- Workflow-guard task-path and scoped `git diff --check` validations passed.
- Scoped Git status was reviewed without staging unrelated worktree changes.

## Risks

- Active consumers must follow repaired paths for archived historical context.
- The missing V2-TASK001 workbook remains a generated review artifact, not
  released domain truth; do not mark this task validated until it is safely
  regenerated or deliberately removed from scope.
- Existing unrelated worktree changes remain outside this task.

## State

`implemented`; current revalidation is blocked by the missing untracked
workbook.
