# V2-TASK015 continuation handoff - 2026-08-08

## Current position

Task015 is through the Phase 3 implementation and independent code-review
checkpoint. The implementation is code-review ready, but the current data
candidate is `blocked_by_b02` and is not ready for promotion or release.

- Phase 1 - inventory and governance: implemented and validated.
- Phase 2 - classification/canonicalization rules: directly approved by the
  user and complete. The stale standalone contract/schema files were removed;
  the approved behavior remains enforced by code and tests.
- Phase 3 - deterministic A/B/C pipeline: implemented, tested, and independently
  reviewed. B01/B02 were regenerated; C01 correctly fails closed; C02 was not
  run.
- Phase 4 - governed 2D-to-3D reconciliation: not started and not the current
  focus.
- Phase 5 - frozen candidate and Task016 handoff: not started.

The immediate continuation is governed review of the existing 60 B02 blockers,
followed by candidate regeneration. Do not weaken parser/audit rules or create
new contract artifacts merely to pass the gate.

## Authoritative reading order

Follow `AGENTS.md`, then:

1. `docs/agents/data_engineering_workflow.md`
2. the durable role guide for the active work
3. `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/brief.md`
4. `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/acceptance.md`
5. `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/notes.md`
6. `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/reconciliation_report_2026-08-08.md`

The notes and reconciliation report contain the detailed history, hashes,
changed-file record, and superseded candidate counts; do not duplicate them
here.

## Live workspace checkpoint

- Branch: `feature/v2-data-pipeline`
- HEAD at handoff creation: `7d248ce`
- Upstream state: ahead 6, behind 1.
- Worktree is mixed and dirty. Preserve all user and unrelated changes; never
  use `git add .`, reset, or broad cleanup.
- Task015 implementation directories are currently untracked in this worktree,
  including `configs/pipelines/`, `scripts/pipelines/`,
  `services/ingestion/cad_2d_pipeline_v2/`, and `tests/unit/cad_2d_v2/`.
- Unrelated modified files include `services/reasoning/route_graph.py` and
  `tests/unit/test_route_graph.py`; do not modify them for Task015.
- No Task015 commit or push has been performed.

## Approved Task015 rules

The user directly approved:

- classifications are `ASM`, `PRT`, and `exclude`;
- excluded drawings never enter BOM or KG output;
- explicitly reviewed multi-view drawings may share one definition;
- a multi-page drawing remains one definition;
- individual BOM occurrences remain distinct and retain source/PDF provenance.

Do not reintroduce the deleted standalone Phase 2 contract/schema unless the
user explicitly reverses that decision.

## Current Phase 3 evidence

The current reviewed artifacts are the existing local candidate directories:

- B00: `B00_phase3r5`
- B01: `B01_phase3r9`
- B02: `B02_phase3r9`

They live under the existing ignored Task015 pipeline-candidate directory in
`data/processed/review_pending/route_a/`. Do not add generated candidates to
Git and do not create another review file unless required.

Current result:

- B01: 38 parents - 32 governed historical plus 6 fresh PDF-derived; 2 reviewed
  ASM unresolved; 17 explicit extraction findings.
- B02: 62 findings, 60 blocking.
- Blocking categories: 38 suspicious identifiers, 7 blank extracted part
  numbers, 6 ambiguous continuations, 3 classification/empty-BOM findings,
  2 invalid quantities, 2 historical blank part numbers, and 2 unreliable
  header findings.
- Two item-sequence-gap findings are nonblocking.
- C01 recomputed the same inputs and failed closed with `count=60`.
- C02 was intentionally not run.

The earlier 261-blocker result is historical and superseded by r9.

## Review conclusions

- Independent adversarial code review found no remaining high/blocking parser
  defect. Wide optional-column overlap and between/post-row continuation cases
  now fail safely.
- Independent quality review reproduced B01/B02 exactly and verified manifests,
  provenance, determinism, and the C01 gate.
- Pipeline safety evidence is acceptable and the implementation is code-review
  ready.
- The data candidate remains `NOT_READY` until all 60 blockers receive governed
  source/domain review and a regenerated frozen candidate passes independent
  review.

Latest validation:

```text
.venv\Scripts\python.exe -m pytest tests/unit/cad_2d_v2 -q
41 passed
```

Compilation and `git diff --check` also passed.

## Next action

Use the existing B02 r9 findings as the review queue. Resolve each blocker by
source evidence or an explicit governed decision. In particular:

1. Confirm or normalize the 38 identifiers; do not relax the identifier rule
   globally.
2. Resolve blank, ambiguous-continuation, invalid-quantity, and unreliable-header
   findings from their existing source/PDF anchors; do not invent cell values or
   concatenate rows automatically.
3. Record reviewed overrides only through the existing governed override path.
4. Regenerate B01/B02 once decisions are complete.
5. Run C01 only after B02 has no unresolved blocking findings; run C02 only if
   C01 succeeds.
6. Obtain another independent quality review before freezing or handing the
   candidate to Task016.

The user explicitly asked to focus on Task015 and is concerned about repository
weight. Prefer editing existing evidence and queues over creating extra files.

## Data and safety boundary

Recorded bounded permission allows local Task015 reads/writes under:

- `data/governance/`
- relevant Task015 `data/processed/` paths
- `reference_work/AAA*`

Access to `data/raw/` is explicitly denied. Never open, parse, hash, sample,
copy, or indirectly process raw-zone content. Never send protected drawing
content or identifiers to external services. Keep generated/protected artifacts
out of Git.

Do not modify `Faultdx_ref/`. Preserve the immutable completed 54-record review
artifact and all unrelated worktree changes.

## Suggested skills

- `pdf` for bounded local visual verification when resolving source-anchored
  BOM findings.
- `handoff` when the 60-finding review or the next major Task015 gate is
  completed.
