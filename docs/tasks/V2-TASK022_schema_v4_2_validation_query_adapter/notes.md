# V2-TASK022 notes

## 2026-08-11 - planned

### Plan

- Define query-registry and normalized-result contracts under the contract
  engineer before transferring implementation ownership.
- Implement deterministic parameterized read-only Schema 4.2 queries, an
  allowlisted adapter, a CLI, and explicit abstention states.
- Validate with synthetic cases and the separate Task 021 shadow graph.
- Keep natural-language parsing, arbitrary Cypher, runtime routing, and graph
  mutation outside this task.

### Changed files

- `docs/tasks/V2-TASK022_schema_v4_2_validation_query_adapter/brief.md`
- `docs/tasks/V2-TASK022_schema_v4_2_validation_query_adapter/acceptance.md`
- `docs/tasks/V2-TASK022_schema_v4_2_validation_query_adapter/notes.md`

### Validation

- Confirmed `V2-TASK022` was unused before allocation.
- Recorded serialized contract and implementation ownership.
- Covered the requested diagnostic, topology, provenance, material, state-
  filtering, and structural-audit query families.
- Distinguished no-result, ambiguity, exclusion, abstention, and execution
  failure.
- A bounded PowerShell structure check confirmed that Tasks 019-023 contain
  exactly 15 new files, with `brief.md`, `acceptance.md`, and `notes.md` in each
  package; the same check found no trailing whitespace.
- `python scripts/check_workflow_guard.py` passed: no protected workflow files
  changed.
- No file contents under `data/` were opened, parsed, sampled, grepped, or
  indirectly validated; no graph query was executed.

### Risks

- The normalized result contract and affected-consumer compatibility decision
  do not yet exist.
- Live query evidence depends on a verified Task 021 shadow graph.
- Validation queries cannot establish domain correctness without independent
  labels and applicability rules.

### State

Task decision state: `planned`.
