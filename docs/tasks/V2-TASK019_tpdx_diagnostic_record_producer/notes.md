# V2-TASK019 notes

## 2026-08-11 - planned

### Plan

- Implement a governed producer from Error Code, Repair SOP, and reviewed
  table-extraction records to frozen Schema 4.2 diagnostic objects.
- Preserve source anchors, masking, review, promotion, and co-source
  provenance throughout the transformation.
- Require explicit reviewed Cause-to-Action pairs and send ambiguity to human
  review instead of inferring truth.
- Begin with synthetic fixtures and stop before any real-data read, package
  production, graph mutation, or runtime activation.

### Changed files

- `docs/tasks/V2-TASK019_tpdx_diagnostic_record_producer/brief.md`
- `docs/tasks/V2-TASK019_tpdx_diagnostic_record_producer/acceptance.md`
- `docs/tasks/V2-TASK019_tpdx_diagnostic_record_producer/notes.md`

### Validation

- `Get-ChildItem -LiteralPath docs/tasks -Directory` found the existing local
  `V2-TASK018_code_review_agent_workflow` package. It was preserved unchanged,
  and `V2-TASK019` was confirmed unused before allocation.
- Reviewed the durable workflow and pipeline/KG role boundary.
- Recorded the synthetic write set, producer authority, fail-closed behavior,
  independent-review gate, and downstream package boundary.
- A bounded PowerShell structure check confirmed that Tasks 019-023 contain
  exactly 15 new files, with `brief.md`, `acceptance.md`, and `notes.md` in each
  package; the same check found no trailing whitespace.
- `python scripts/check_workflow_guard.py` passed: no protected workflow files
  changed.
- No file contents under `data/` were opened, parsed, sampled, grepped, or
  indirectly validated.

### Risks

- Governed source paths, versions, field authority, and bounded permission are
  not yet recorded.
- Source terminology cannot substitute for domain review or promotion
  evidence.
- Cause-to-Action assertions cannot be emitted when reviewed pairing evidence
  is missing or ambiguous.

### State

Task decision state: `planned`.
