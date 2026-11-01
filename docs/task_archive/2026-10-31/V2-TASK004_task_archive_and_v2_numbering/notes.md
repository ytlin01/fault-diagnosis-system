# V2-TASK004 notes

## Plan

Preserve historical task evidence under `legacy/tasks/`, keep continuing work
under sequential `V2-TASK###` identifiers, and synchronize the protected
workflow system without touching data contents or unrelated implementation.

## Mapping

- `TASK-044_route_a_shared_gold_eval_framework` ->
  `V2-TASK001_route_a_shared_gold_eval_framework`
- `TASK-045_workflow_state_separation` ->
  `V2-TASK002_workflow_state_separation`
- `TASK-046_dekg_fhkb_ingestion_contracts` ->
  `V2-TASK003_dekg_fhkb_ingestion_contracts`
- this migration -> `V2-TASK004_task_archive_and_v2_numbering`

All other task packages formerly under `docs/tasks/` moved to `legacy/tasks/`.

Additional archive consolidation:

- `docs/agents/legacy/` -> `legacy/agents/`
- `docs/runbooks/legacy/` -> `legacy/runbooks/`
- retired repository-root artifacts -> `legacy/root/`
- retired `L_onboarding.md` -> `legacy/onboarding/L_onboarding.md`
- `.venv/**/legacy/` directories remain untouched because they are installed
  dependency internals rather than repository archives.
- incomplete worktree-only data-layout and CAD Schema 4.0 edits ->
  `legacy/unowned_migrations/`, preserving their original relative paths

## Changed files

- Historical packages moved from `docs/tasks/` to `legacy/tasks/`.
- Retired role guides and runbooks moved into the root `legacy/` archive.
- `legacy/README.md` added as the archive index.
- Root-level historical files and retired onboarding guidance moved into the
  root archive.
- Local diagnostic and vendor-inspection archive payloads excluded from Git;
  their contents were not inspected or promoted into versioned evidence.
- Continuing packages renamed under `docs/tasks/`.
- Explicit legacy paths and continuing task identifiers updated.
- Workflow entry points, task template, PR template, CODEOWNERS, and workflow
  guard updated for `V2-TASK###`.
- The workflow now supplies Git name/status records so the guard can allow
  deletion of retired task paths while continuing to reject added or modified
  non-V2 active task paths.
- Current-task helper script filenames updated from `task044` to `v2_task001`.
- Twenty-two unowned migration edits were copied into
  `legacy/unowned_migrations/`, hash-verified before repository whitespace
  normalization, and then removed from the active paths by restoring those
  paths from the current branch `HEAD`.

## Validation

- Verified all 162 formerly tracked task files exist at their mapped
  `legacy/tasks/` or active `docs/tasks/V2-TASK###_*` destinations.
- Verified all active task directory names through `V2-TASK006` match
  `V2-TASK###_<lowercase_name>`; 51 historical packages are under
  `legacy/tasks/`.
- Verified all 13 retired agent files and all 6 retired runbook files exist at
  `legacy/agents/` and `legacy/runbooks/`.
- Scanned repository-owned directories for nested `legacy` folders: none
  remain. Four `.venv` dependency-internal matches were excluded intentionally.
- Scanned active repository text for stale current-task IDs, old active task
  paths, old helper-script names, and the former nested legacy paths: passed.
- Compiled `scripts/check_workflow_guard.py` in memory: passed.
- Workflow guard accepted acknowledged `V2-TASK004`, rejected an old
  `docs/tasks/TASK-999_*` path, and accepted a valid V2 task path.
- Workflow guard passed against the actual staged migration set, accepted a
  deleted legacy task path and a legacy-to-V2 rename, and rejected an added
  legacy task path.
- Scoped `git diff --check`: passed; only existing CRLF normalization warnings
  were emitted.
- Scoped Git status was reviewed without staging or modifying unrelated
  worktree changes.
- Verified the six root-level archived artifacts exist; five are exact blob
  moves and `result_design_v2_decision.md` differs only by its repaired
  archived-document path.
- Verified `L_onboarding.md` is preserved under `legacy/onboarding/`.
- Verified local diagnostic and vendor-inspection payloads are ignored while
  `legacy/data/diagnostic/.gitkeep` remains eligible for versioning.
- Verified all 22 archived migration snapshots matched their pre-restore
  working-copy SHA-256 hashes before one trailing-space-only normalization.
  The active files returned to `HEAD`; the stale Schema 4.0 and partial
  data-layout attempts remain reference-only.

## Risks

- Historical prose may still use bare `TASK-*` identifiers intentionally; the
  archive move does not rewrite historical conclusions.
- Existing unrelated worktree changes remain outside this migration.

## State

`validated`
