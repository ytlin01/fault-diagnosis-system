# V2-TASK021 notes

## 2026-08-11 - planned

### Plan

- Extend the non-mutating Schema 4.2 import plan with a separately reviewed
  Neo4j shadow-database mutation boundary.
- Require an accepted package, an allowlisted shadow target, preflight audits,
  idempotent reload evidence, and deterministic post-import evidence.
- Preserve the Schema 4.1 database and stop before runtime switching.

### Changed files

- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/brief.md`
- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/acceptance.md`
- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/notes.md`

### Validation

- Confirmed `V2-TASK021` was unused before allocation.
- Preserved the current import planner's deliberate non-connection boundary.
- Recorded target-safety, assertion identity, structural audits, rollback, and
  non-activation gates.
- A bounded PowerShell structure check confirmed that Tasks 019-023 contain
  exactly 15 new files, with `brief.md`, `acceptance.md`, and `notes.md` in each
  package; the same check found no trailing whitespace.
- `python scripts/check_workflow_guard.py` passed: no protected workflow files
  changed.
- No file contents under `data/` were opened, parsed, sampled, grepped, or
  indirectly validated; no database connection was attempted.

### Risks

- No shadow database identity, operations owner, credential source, or package
  path is authorized yet.
- Database rollback testing must use an exact allowlisted target and cannot be
  inferred from an in-memory test.
- Successful graph import does not prove query or diagnostic correctness.

### State

Task decision state: `planned`.
