# V2-TASK010 notes

## 2026-07-27 - implemented

### Plan

- Use the frozen v2 packages as the only migration authority.
- Do not infer missing v2 provenance from legacy graph nodes.
- Replace the old graph transactionally and make zero `DocumentAsset` a hard
  post-write invariant.
- Keep E3 execution and release gated on corpus inventory, package review,
  backup verification, and independent quality review.

### Changed files

- `services/graph/dekg_evidence_store.py`
- `scripts/build_graph/replace_legacy_dekg_neo4j.py`
- `scripts/export_route_b_graphrag_neo4j.py`
- `tests/services/graph/test_dekg_evidence_store.py`
- `docs/tasks/V2-TASK010_dekg_documentasset_replacement/brief.md`
- `docs/tasks/V2-TASK010_dekg_documentasset_replacement/acceptance.md`
- `docs/tasks/V2-TASK010_dekg_documentasset_replacement/notes.md`

### State

Implementation: `implemented`.

Synthetic validation: pending.

E3 candidate: not generated.

Reviewed: no.

Released: no.

## 2026-07-27 - E3-local execution boundary clarified

### User clarification

The legacy `DocumentAsset` nodes already reside on E3. The replacement must run
when the reviewed version and package bundle are transferred to the E3
workstation; it is not a local-workstation graph mutation.

### Implemented

- Added `--inspect` for read-only E3 legacy/evidence counts without loading a
  package or writing.
- Added `e3_dekg_replacement_handoff.md` with the bounded offline transfer contents,
  target/version fixation, preflight, version-specific backup gate, offline
  package validation, E3 apply, independent read-back, consumer smoke, stop
  conditions, and rollback boundary.
- Kept the apply transaction and zero-legacy invariant unchanged.

### State

E3 transfer procedure and read-only preflight behavior: `validated` with
synthetic tests and CLI loading.

E3 execution: not run.

Released: no.

## 2026-07-27 - synthetic validation passed

### Validation

- `python -m unittest tests.services.graph.test_dekg_evidence_store
  tests.unit.test_dekg_fhkb_legacy_adapters`: 18 tests passed.
- `python -m compileall -q services/graph/dekg_evidence_store.py
  scripts/build_graph/replace_legacy_dekg_neo4j.py
  tests/services/graph/test_dekg_evidence_store.py`: passed.
- Both the replacement CLI and disabled legacy-export CLI help paths load.
- Scoped `git diff --check`: passed.
- `python scripts/check_workflow_guard.py`: passed; no protected workflow file
  changed.
- Official Neo4j documentation confirms that `Session.execute_write()` runs a
  managed transaction which commits on return and rolls back when the callback
  raises; the callback is idempotent because it deletes and recreates the exact
  reviewed set.
- Official Neo4j documentation confirms the named node-property uniqueness
  constraint syntax used for `DEKGEvidence.evidence_id`.

No test or validation command read a file under `data/`.

### Result

Implementation and synthetic validation: `validated`.

E3 deployment candidate: blocked on the complete `V2-TASK009` inventory,
reviewed v2 packages, E3 access, database/version preflight, backup evidence,
and independent quality review.

Reviewed: no.

Released: no.

## 2026-07-28 - E3 handoff naming

### Implemented

- Renamed `e3_transfer_handoff.md` to `e3_dekg_replacement_handoff.md`.
- Renamed the document title to `E3 DEKG replacement handoff`.
- Updated the Task 010 brief and notes references; execution scope and gate
  requirements are unchanged.

### State

Documentation naming: `implemented`.

E3 execution: not run.

Released: no.
