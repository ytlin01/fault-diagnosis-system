# V2-TASK008 notes

## 2026-07-27 - implemented

### Plan

Implement the source-neutral Gate 2 partition boundary with synthetic fixtures
only. Do not read any `data/` contents or perform the authorized real-source
run.

### Changed files

- `services/ingestion/dekg_source_partition.py` - reviewed block-ledger validator and deterministic routing manifest.
- `tests/unit/test_dekg_source_partition.py` - synthetic success, determinism, and failure coverage.
- `docs/tasks/V2-TASK008_vision_sop_dekg_producer/brief.md`
- `docs/tasks/V2-TASK008_vision_sop_dekg_producer/acceptance.md`
- `docs/tasks/V2-TASK008_vision_sop_dekg_producer/notes.md`

### Validation

- `python -m unittest tests.unit.test_dekg_source_partition tests.unit.test_dekg_fhkb_legacy_adapters tests.unit.test_local_vlm_enrichment` - 22 tests passed.
- Four focused masking/serving-projection tests from `tests.unit.test_unstructured_ingestion` passed.
- `python -m compileall -q services/ingestion/dekg_source_partition.py tests/unit/test_dekg_source_partition.py` - passed.
- `git diff --check` - passed; Git reported only the pre-existing line-ending warning for the approved governance CSV change.
- `python scripts/check_workflow_guard.py` - passed; no protected workflow files changed.
- The combined full unstructured-ingestion regression run executed 33 tests and had two failures in legacy default-output-directory expectations. Current `run_mask_unstructured.py` uses `data/processed/masked/unstructured[/vlm]` and `data/processed/serving/unstructured`, while those tests expect the retired flat directory names. Neither the script nor those tests is in this task's write set.

### Risks

- No exact block ID, source digest, source-derived count, or candidate artifact is claimed.
- The real run remains blocked on explicit raw-read authorization and authorized human review of the generated block ledger.
- VLM, masking, serving projection, adapter execution, and independent review remain subsequent steps.
- The unrelated output-directory test mismatch should be resolved under its owning ingestion task rather than folded into this source-partition change.

### State

`implemented`; not yet `validated`, `reviewed`, or `released`.
