# FaultDx v2 contract consumer impact matrix

## Decision summary

- TPDX Schema/Ontology 4.2 and `faultdx_data_package_v1` 1.0.0 are `FROZEN`.
- The frozen contracts are approved boundaries, not proof of runtime
  activation, a Serving Build, Data RC approval, deployment, or release.
- The common package envelope is optional until separately reviewed shared
  validation and route-adapter implementation exists.
- A4.2, A4.1, B2.0, and C1.0 are external handoff labels supplied for this
  matrix. The repository contract IDs and paths below are authoritative.

## Handoff-level impact

| Consumer label | Repository binding | Compatibility result | Required action | Current gate |
| --- | --- | --- | --- | --- |
| A4.2 | `tpdx_kg_schema_v4_2` plus `tpdx_kg_ontology_v4_2.md`; optional `faultdx_data_package_v1` envelope | Accepted target contract. Breaking from A4.1 where consumers depend on stored `HAS_STEP`; Schema 4.2 uses only `HAS_STEPS`. | Migrate queries, importers, fixtures, and evaluations; preserve MappingRecord provenance and explicit Cause-to-Action pairing; run consumer compatibility and rollback checks before activation. | Contracts `FROZEN`; runtime activation and release not authorized. |
| A4.1 | Frozen TPDX Schema 4.1 comparison/rollback baseline | Remains valid and unchanged for rollback. It is not the current contract for new packages and must not be silently normalized into A4.2. | Do not repackage or modify. Attach only if required and only after byte-for-byte SHA-256 verification against the approved freeze manifest. | Frozen baseline; no version or activation-gate change. |
| B2.0 | `dekg_evidence_v2`, Route B `document_evidence + evidence_only` | Record semantics remain unchanged. The v1 envelope is an optional, non-rewriting wrapper. DEKG content is not Route A truth or independent corroboration merely because it is packaged or masked. | Keep the frozen route contract unchanged. Implement and review an envelope adapter separately before adoption. | Frozen route contract retained; shared loader and release not authorized. |
| C1.0 | `fhkb_case_v1`, Route C `case_reference + candidate` | Record semantics remain unchanged. The v1 envelope is an optional, non-rewriting wrapper. Cases are not promoted to diagnostic truth by packaging, masking, or historical completeness. | Keep the frozen route contract unchanged. Implement and review an envelope adapter separately before adoption. | Frozen route contract retained; shared loader and release not authorized. |

## Repository consumer impact

| Consumer | Impact | Required evidence before use |
| --- | --- | --- |
| Route A ingestion and TPDX component builders | Must emit self-contained Schema 4.2 payloads and preserve `MappingRecord` backing for every diagnostic projection. A TPDX release may reference zero or one accepted topology, diagnostic, and replacement/material component. | Contract validation, semantic provenance validation, deterministic identity checks, component digest/dependency checks, and separately reviewed implementation ownership. |
| Graph importer and Text2Cypher consumers | Must use `HAS_STEPS`, not legacy `HAS_STEP`; lower-level topology entry points must resolve to the ancestor Module without changing assertion scope. | Query migration tests, negative provenance cases, old/new KG comparison, ambiguity checks, and rollback evidence. |
| Route A evaluation | Must measure the breaking relationship migration and reject unbacked, contradictory, ambiguous, duplicate, or invalid projections. | Independent evaluation evidence; contract validation alone is insufficient for release. |
| Masking and ingestion producers | Must reference immutable masking manifests by path and SHA-256 and provide exact effective coverage for artifacts requiring masking. | Filesystem digest validation and proof that masking, serving safety, route eligibility, review, promotion, and release decisions remain separate. |
| DEKG producer and index preparation | May adopt the optional envelope without rewriting `dekg_evidence_v2`; Route B remains evidence-only. | Separately reviewed adapter and envelope/payload agreement checks for release, source, lineage, masking, and serving claims. |
| FHKB producer and index preparation | May adopt the optional envelope without rewriting `fhkb_case_v1`; Route C remains candidate-only. | Separately reviewed adapter and envelope/payload agreement checks for release, source, lineage, masking, and serving claims. |
| Shared package validator/loader | No production implementation is authorized by contract freeze. | A separately allocated pipeline/KG task, conforming RFC 8785 implementation and vectors, portable-path and SHA-256 checks, collision handling, component resolution, and route-adapter tests. |
| Data RC preparation | May later reference accepted packages but does not inherit release authority from either frozen contract. | Independent Data RC review, integration manifest, exclusions, and explicit release decision. |

## Frozen-archive attachment rules

For A4.1, B2.0, and C1.0:

1. Prefer references to the existing governed frozen artifacts; do not create a
   new archive merely for this handoff.
2. If an archive must be attached, it must be byte-for-byte identical to the
   governed frozen archive and its SHA-256 must match
   `route_abc_contract_freeze_v1.json`.
3. Do not remove or weaken `FROZEN` state.
4. Do not change contract versions, route semantics, or activation gates.

The required `route_abc_contract_freeze_v1.json` is currently absent, so rule
2 cannot yet be verified. This is a handoff blocker for archive verification,
not authorization to generate replacement hashes or rebuild the archives.

## Approval and ownership

Affected producer/consumer acceptance is recorded with four continuing
implementation conditions. Independent reviewer N recorded `READY` with no
exclusions, and the workflow lead recorded the contract freeze decisions.
The next implementation owner is `data_pipeline_kg_engineer`, but only through
a separately allocated task with an explicit write set.
