# FaultDx v2 contract package changelog

## Scope

This changelog covers only the governed contract artifacts listed below. It is
not a repository-wide product changelog and does not claim runtime activation,
a Serving Build, Data RC approval, deployment, or release.

## 2026-08-11 - `faultdx_data_package_v1` 1.0.0

Status: `FROZEN`.

### Added

- A common package envelope for one `TPDX`, `DEKG`, or `FHKB` knowledge asset
  without merging their record contracts or route semantics.
- Deterministic package identity and content-digest rules, portable relative
  paths, SHA-256 integrity checks, lineage, producer identity, artifact
  metadata, decision state, and fail-closed collision behavior.
- Immutable masking-manifest references with explicit artifact coverage.
  Masking, review, serving safety, route eligibility, promotion, and release
  remain separate decisions.
- Independent TPDX topology, diagnostic, and replacement/material component
  packages plus a release package that may reference at most one accepted
  component of each type.
- Route bindings that preserve TPDX Route A reviewed structured facts, DEKG
  Route B `evidence_only`, and FHKB Route C `candidate` semantics.
- Compatibility, rollback, validation order, and the later implementation
  handoff to `data_pipeline_kg_engineer` through a separately allocated task.

### Freeze conditions retained

1. Real package IDs must not be issued until an RFC 8785 implementation passes
   the required Unicode and number vectors.
2. The common envelope remains optional until a shared validator and each
   route adapter are separately implemented and reviewed.
3. Production integration requires a separately allocated pipeline/KG task
   with an explicit owner and write set.
4. Contract freeze does not mean runtime activation, graph/index ingestion,
   package production, Data RC approval, or release.

## 2026-08-10 - TPDX KG Schema and Ontology 4.2

Status: `FROZEN`.

### Added

- A complete, self-contained Route A Schema 4.2 contract and ontology.
- MappingRecord-backed diagnostic projections:
  `Phenomenon-[:HAS_CODE]->ErrorCode`,
  `Phenomenon-[:HAS_CAUSE]->Cause`,
  `Cause-[:HAS_ACTION]->Action`, and
  `Action-[:HAS_STEPS]->ActionStep`.
- Deterministic assertion-edge identity, one backing `mapping_record_id` per
  projection, and endpoint-membership checks that preserve source provenance.
- A required `cause_action_pair_id` for reviewed Cause-to-Action pairings;
  producers must not infer a Cartesian product from independent memberships.
- Standalone topology, diagnostic, replacement, identity, exclusion,
  migration, rollback, validation, and lifecycle definitions.

### Breaking change from Schema 4.1

- The stored Action-to-ActionStep relationship changed from `HAS_STEP` to
  `HAS_STEPS`. Schema 4.2 does not dual-publish both names.
- Consumers must migrate queries, importers, fixtures, and evaluations to
  `HAS_STEPS`, validate MappingRecord backing, and reject ambiguous or invalid
  projections before activation.

### Compatibility and rollback

- Frozen Schema 4.1 remains unchanged as the historical comparison and
  rollback baseline. It is not an alternative current package contract for
  new consumers.
- Existing frozen DEKG and FHKB record contracts remain unchanged. The common
  envelope is an optional wrapper and requires no record rewrite.

## Artifact integrity snapshot

These are SHA-256 hashes of the four tracked artifacts in the current
repository checkout. All four match `HEAD`. They are not a substitute for
verification against an approved freeze manifest.

| Artifact | SHA-256 |
| --- | --- |
| `contracts/schema/tpdx_kg_ontology_v4_2.md` | `27e9bf79098a5e29787425f6c3b4287de022db6809014bd1544c6b94f7c9fd2b` |
| `contracts/schema/tpdx_kg_schema_v4_2.schema.json` | `1fb4d2ad4dea63cb0a875ffb1dd941a4fa86387e6bb92a58f9cb229f253f4310` |
| `contracts/package/faultdx_data_package_v1.json` | `737d14c7608a8ef086346780702b9f58daf8c006d61b6444cd593c828f01ab9f` |
| `contracts/package/faultdx_data_package_v1.schema.json` | `e386857c88a7848f47b55e541cfa8558cf38031883fe170b983d2da9eb96e1d5` |

## Known handoff gap

`route_abc_contract_freeze_v1.json` is not present in this repository. Until
the approved manifest is supplied, its expected SHA-256 values and the
byte-for-byte identity of any A4.1, B2.0, or C1.0 archive attachment cannot be
verified. No hash or freeze evidence is inferred in this changelog.
