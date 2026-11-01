# V2-TASK024 notes

## 2026-08-18 - planned

### Plan

- Use the two user-authorized PDFs as evidence to define a governance baseline
  and a synthetic, machine-readable test set.
- Bind all proposed publication gates to the frozen Schema 4.2 contract and
  the durable inventory -> governance -> schema/canonicalization ->
  pipeline/KG -> evaluation/release-review workflow.
- Preserve uncertainty from the reports: `validated=false`, unmapped records,
  alias conflicts, BOM quantity mismatches, missing Layer B data, and legacy
  query vocabulary are not promoted by this task.
- Keep all fixtures synthetic and stop before real-data writes, graph mutation,
  runtime activation, Data RC, commit, or push.

### Changed files

- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/brief.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/acceptance.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/notes.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/data_governance_plan.md`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/test_set_v1.jsonl`
- `docs/tasks/V2-TASK024_diagnostic_asset_governance_testset/test_set_v1.md`

### Implemented

- Added a draft governance plan covering source inventory, lineage, masking,
  canonicalization, MappingRecord promotion, Layer B gaps, BOM joins, graph
  quality, query safety, and release gates.
- Added 32 synthetic cases spanning governance/provenance, alias and mapping
  behavior, diagnostic contract rules, topology/BOM quality, query safety, and
  independent evaluation.
- Kept all fixtures synthetic and recorded historical inconsistencies as
  review cases instead of silently correcting or promoting them.

### Validation

- Read both user-authorized PDFs completely and visually inspected all 15
  rendered pages.
- Compared the proposed gates with the durable workflow, contract-engineer
  and quality-reviewer boundaries, and existing Tasks 019-023.
- No raw or unmasked source data was copied into the deliverables.
- Rendered pages showed no source-layout defects that affect the extracted
  evidence used here.
- A bounded structure check found exactly six task files and no trailing
  whitespace.
- JSONL validation passed: 32 cases, 32 unique IDs, and all required fields
  present on every case.
- Worktree scope check shows only the new V2-TASK024 directory under this task;
  pre-existing user changes elsewhere were preserved.
- Pending: independent review of applicability, labels, and governance
  decisions.

### Delivery state

- `planned`: the task was scoped as a governance-plan and synthetic-test-set
  delivery.
- `implemented`: the Chinese handoff plan and 32-case synthetic test set were
  created.
- `validated`: structure, JSONL parsing, unique IDs, required fields, and
  workflow protection checks passed.
- `reviewed`: not claimed by this delivery.
- `released`: not claimed; this is a completed handoff artifact, not a
  production release.

### Risks

- Source owners, sensitivity classifications, masking evidence, and review
  identities are not supplied by the reports and remain open governance fields.
- The reports contain historical count and vocabulary inconsistencies; they
  are recorded as test cases and reconciliation work, not corrected silently.
- The test set is a synthetic contract/gate baseline, not an independent domain
  gold set and not evidence that the current graph is production-ready.

### State

Delivery state: `handoff_artifact_complete`.
Production state: `not_released`.
