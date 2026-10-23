# V2-TASK014 Unified data package manifest

## Identity

- Owner: `data_contract_engineer`
- Reviewers: `data_workflow_lead`, `data_pipeline_kg_engineer`, affected
  TPDX/DEKG/FHKB producer and consumer owners
- Independent reviewer: `data_quality_reviewer`
- Decision state: `frozen`
- Source/candidate version: existing masking-run manifest; frozen
  `dekg_evidence_v2` and `fhkb_case_v1`; completed `V2-TASK012` Schema 4.2
  contract package selected as the TPDX working baseline
- Dependencies: `V2-TASK003`, `V2-TASK006`, and completed `V2-TASK012`;
  `V2-TASK013` is not a dependency of this contract-design task
- Downstream consumers: masking and ingestion producers, TPDX candidate build,
  DEKG replacement, FHKB indexing, package validators, and Data RC preparation

## Goal

Define a shared, versioned package-manifest contract for FaultDx data assets
while keeping TPDX, DEKG, and FHKB in separate packages with separate record
contracts. Incorporate existing masking manifests as immutable, digest-verified
evidence references rather than copying or replacing their contents.

## Background

The repository has masking-run manifests and separate DEKG/FHKB package
envelopes, but no common package-manifest contract. TPDX also has a more complex
multi-stage pipeline than the other assets: topology, diagnostic assertions,
and replacement/material outputs may be rebuilt, reviewed, and rolled back
independently.

The intended model unifies package identity, source/version, artifacts,
checksums, lineage, masking evidence, contract selection, and package status.
It does not unify route semantics or mix records from all three knowledge
assets into one package. TPDX uses independently rebuildable component
packages referenced by one TPDX release package.

## Inputs

- `AGENTS.md`
- `docs/agents/data_engineering_workflow.md`
- `docs/agents/data_contract_engineer.md`
- `docs/tasks/V2-TASK003_dekg_fhkb_ingestion_contracts/`
- `docs/tasks/V2-TASK006_phase2_masking_identity/`
- `docs/tasks/V2-TASK012_schema_v4_2_diagnostic_chain/`
- `services/ingestion/manifest.py`
- `contracts/evidence/dekg_evidence_v2.json`
- `contracts/evidence/dekg_evidence_v2.schema.json`
- `contracts/case/fhkb_case_v1.json`
- `contracts/case/fhkb_case_v1.schema.json`
- `contracts/schema/tpdx_kg_schema_v4_2.schema.json`

No file under `data/` is an input to the contract-design phase. Before any
later role opens or validates a real package or masking manifest under `data/`,
ask the user for explicit permission for the intended path or bounded scope.

## Scope

- Define `faultdx_data_package_v1` as a common envelope with deterministic
  package identity, release identity, one knowledge asset, one route family,
  one record-contract reference, source identity/version, lineage, artifacts,
  digests, counts, producer identity, and package decision state.
- Require each package instance to belong to exactly one of `TPDX`, `DEKG`, or
  `FHKB`; prohibit a mixed record payload spanning the three assets.
- Define masking evidence as a one-to-many list of immutable manifest
  references containing portable relative paths, SHA-256 digests, run IDs,
  coverage declarations, and masking/review status.
- Keep masking success separate from serving safety, route eligibility,
  review, promotion, and release decisions.
- Define artifact roles, media types, SHA-256 verification, record counts,
  path portability, duplicate/collision behavior, and fail-closed validation.
- Define TPDX component-package types for topology, diagnostic assertions, and
  replacement/material outputs, plus a TPDX release package that references
  accepted component manifests by identity and digest.
- Define compatibility mappings for the existing DEKG and FHKB package fields
  without editing their frozen contracts in place.
- Define migration, rollback, validation order, synthetic examples, affected
  consumers, and the implementation handoff.

## Non-goals

- No inspection or mutation of files under `data/`.
- No masking execution, source registration, package production, graph build,
  index build, runtime binding, or executor change.
- No edit to frozen DEKG, FHKB, TPDX Schema 4.1, Schema 4.2, or masking
  contracts in place.
- No automatic promotion from masking success to serving eligibility or Route
  A truth.
- No single package containing TPDX, DEKG, and FHKB record payloads.
- No Data RC decision or global release collection ownership. A future Data RC
  manifest may reference accepted knowledge-asset packages, but remains owned
  by the workflow lead and independently reviewed.
- No Schema 4.2 lifecycle-state change, activation, or release claim. Task 014
  consumes Schema 4.2 as selected; it does not govern Schema 4.2 itself.

## Proposed write set

The contract-design phase is limited to:

- `docs/tasks/V2-TASK014_unified_data_package_manifest/`
- `contracts/package/faultdx_data_package_v1.json`
- `contracts/package/faultdx_data_package_v1.schema.json`
- `tests/unit/test_faultdx_data_package_contract.py`

Any producer, shared loader, validator service, route-specific adapter, or
existing frozen-contract migration requires a reviewed contract and a later
pipeline/KG implementation handoff with its own explicit write ownership.

## Failure behavior

- Reject unknown package versions, mixed knowledge assets, route/contract
  mismatches, absolute or escaping paths, missing artifacts, digest mismatch,
  duplicate package identity with conflicting content, and invalid component
  references.
- Reject serving-safe or released claims when required masking evidence,
  review evidence, or route-specific policy evidence is absent.
- Reject a masking reference whose declared covered artifacts do not match the
  package artifact identities.
- Reject self-referential or circular component/package dependencies.
- Validation failure must never silently downgrade or promote a package.

## Compatibility and rollback

- Existing masking manifests remain authoritative for their masking runs and
  are referenced without modification.
- Existing frozen DEKG and FHKB packages remain valid under their current
  contracts until separately reviewed adapters or envelope migrations exist.
- TPDX component packages wrap deterministic Schema 4.2 outputs; they do not
  redefine KG record semantics. Schema 4.1 remains a comparison/rollback
  baseline rather than an alternative current package contract.
- Rollback removes the new optional envelope binding and continues using the
  existing route-specific contracts and masking manifests.

## Constraints

- Preserve existing user changes and mixed-worktree safety.
- Do not inspect `data/` file contents without explicit user permission.
- Do not modify `Faultdx_ref/`.
- Do not send unapproved data to external services.
- Preserve Route A/B/C meaning and `Phenomenon`/`MappingRecord` provenance.
- Use portable relative paths and SHA-256 for package integrity; retain older
  hashes only as source-manifest metadata.
- Do not turn a proposal, candidate, or future milestone into a completion
  claim.

## Deliverables

- [x] FROZEN common package contract and executable JSON Schema
- [x] separate TPDX, DEKG, and FHKB package-instance rules
- [x] composite TPDX component and release-package model
- [x] masking-manifest reference and coverage model
- [x] compatibility analysis for existing DEKG/FHKB envelopes and TPDX output
- [x] deterministic identity, digest, dependency, and collision rules
- [x] synthetic positive and negative contract fixtures
- [x] validation order, failure behavior, migration, and rollback
- [x] affected-consumer inventory and pipeline/KG implementation handoff
- [x] exact validation evidence and updated task notes

## Next gate

The `faultdx_data_package_v1` contract is `FROZEN`. Any shared package loader,
producer adapter, filesystem validator, or governed real-package validation
must be assigned to `data_pipeline_kg_engineer` in a separately allocated task
with an explicit write set. Freeze does not authorize runtime binding, graph or
index activation, Data RC promotion, release, or access to `data/` contents.

## 当前执行记录（中文，2026-08-11）

- TPDX 当前统一绑定已完成的 Schema 4.2；Schema 4.1 只作为比较和回滚
  基线，不作为新的 package contract。
- V2-TASK012 已作为本任务的合同输入；本任务不依赖 V2-TASK013。
- 公共 package envelope、JSON Schema、合成正反测试和兼容性说明已经完成。
- 受影响 producer/consumer 已接受合同边界及四项实现条件；N 已完成独立审查
  并给出无排除项的 `READY` 建议；workflow lead 已记录冻结决定。
- `faultdx_data_package_v1` 当前状态为 `FROZEN`。下一道 gate 是另行分配的
  pipeline/KG 实现任务；尚未授权共享 loader、producer adapter、真实 package
  验证、runtime 接入、图导入或发布。
