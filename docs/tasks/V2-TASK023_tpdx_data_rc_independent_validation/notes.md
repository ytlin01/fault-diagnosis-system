# V2-TASK023 notes

## 2026-08-11 - planned

### Plan

- Keep final review independent of diagnostic production, packaging, Neo4j
  import, and query-adapter implementation.
- Freeze inputs and preregister applicability, labels, leakage controls,
  exclusions, safety gates, metrics, and decision rules before scoring.
- Report pipeline, graph, diagnostic, query, provenance/review-state, and
  safety/abstention results separately.
- Include paired old/new outcomes, all failures and exclusions, and rollback
  evidence in exactly one readiness recommendation.
- Stop before runtime activation, deployment, or global release.

### Changed files

- `docs/tasks/V2-TASK023_tpdx_data_rc_independent_validation/brief.md`
- `docs/tasks/V2-TASK023_tpdx_data_rc_independent_validation/acceptance.md`
- `docs/tasks/V2-TASK023_tpdx_data_rc_independent_validation/notes.md`

### Validation

- Confirmed `V2-TASK023` was unused before allocation.
- Reviewed the independent quality-review role and separated its write set
  from all candidate owners.
- Recorded the required inputs, six evaluation layers, paired regression
  categories, decision rules, rollback, and non-activation boundary.
- A bounded PowerShell structure check confirmed that Tasks 019-023 contain
  exactly 15 new files, with `brief.md`, `acceptance.md`, and `notes.md` in each
  package; the same check found no trailing whitespace.
- `python scripts/check_workflow_guard.py` passed: no protected workflow files
  changed.
- No file contents under `data/` were opened, parsed, sampled, grepped, or
  indirectly validated.

### Risks

- Review cannot start until Tasks 019-022 provide frozen, fingerprinted
  candidates and Task 016 provides its independent CAD/material outcome.
- Independent labels, applicability rules, and bounded permission remain open.
- `READY_WITH_EXCLUSIONS` is valid only when exclusions are enforceable and no
  blocking provenance or safety gate fails.

### State

Task decision state: `planned`.
