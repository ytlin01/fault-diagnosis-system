# V2-TASK008_vision_sop_dekg_producer

## Identity

- Owner: `data_pipeline_kg_engineer`
- Reviewers: `data_workflow_lead`, `data_contract_engineer`
- Independent reviewer: `data_quality_reviewer`
- Decision state: `implemented`
- Source/candidate version: governed Vision SOP `v1.3`; candidate not yet generated
- Dependencies: `V2-TASK007`; frozen `dekg_evidence_v2` contract
- Downstream consumers: DEKG adapter, independent data-quality review, N/system line

## Goal

Add the deterministic reviewed partition boundary needed before native
text/table processing and local-VLM image enrichment. Produce no real-source
candidate until an authorized environment regenerates and reviews exact block
anchors.

## Background

Gate 1 froze `evidence_residual` mode, the semantic Route A exclusion boundary,
the three remaining-table decisions, and co-source handling. The existing
DEKG adapter enforces selected-table exclusions but expects an upstream producer
to account for and route canonical blocks first.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_pipeline_kg_engineer.md`
- `docs/tasks/V2-TASK007_vision_sop_dekg_source_reconciliation/gate2_pipeline_handoff.md`
- `services/ingestion/canonical_document.py`
- `services/ingestion/local_vlm.py`
- `services/ingestion/unstructured.py`
- `services/ingestion/dekg_legacy_adapter.py`

The raw Vision SOP and all other files under `data/` are outside this task's
read set. Tests use synthetic in-memory fixtures only.

## Scope

- validate a reviewed, block-complete partition ledger;
- enforce table-only Route A selection and exact adapter exclusion anchors;
- route native text/tables without VLM;
- route only reviewed images/figure-charts to the local-VLM lane;
- record ineligible and quarantined blocks separately;
- produce a deterministic, content-free partition manifest and digest;
- reject missing/duplicate/unknown decisions and promotion claims.

## Non-goals

- opening, hashing, parsing, or previewing the raw PPTX;
- generating exact real-source block IDs or a real candidate package;
- running VLM, masking, serving projection, or the final DEKG adapter;
- changing frozen contracts, Route A facts, runtime retrieval, or graph/index policy;
- independently reviewing or releasing the candidate.

## Write set

- `services/ingestion/dekg_source_partition.py`
- `tests/unit/test_dekg_source_partition.py`
- `docs/tasks/V2-TASK008_vision_sop_dekg_producer/`

## Commands and failure behavior

- Focused validation: `python -m unittest tests.unit.test_dekg_source_partition`
- Regression validation: `python -m unittest tests.unit.test_dekg_fhkb_legacy_adapters tests.unit.test_local_vlm_enrichment tests.unit.test_unstructured_ingestion`
- Workflow validation: `python scripts/check_workflow_guard.py`
- Any unreviewed, incomplete, overlapping, type-invalid, or promotion-bearing
  ledger fails before VLM or DEKG adaptation.

## Rollback

Remove only the three bounded write-set additions above. No generated data,
governance state, frozen contract, or raw input is mutated by this task.

## Risks and next gate

- Exact source anchors remain unavailable until an explicitly authorized
  regeneration and human partition review.
- J's historical selection is lineage context, not a substitute for the new
  reviewed manifest.
- After that authorized run, masking/serving projection and DEKG adaptation
  require validation before independent quality review.

## Deliverables

- [x] deterministic partition implementation
- [x] synthetic success and failure tests
- [x] explicit raw-access and real-run boundary
- [x] validation evidence recorded in `notes.md`
- [ ] authorized real-source manifest and frozen candidate
