# V2-TASK014 notes

## 2026-07-31 - planned

### Plan

- Define one common package envelope standard while producing separate package
  instances for TPDX, DEKG, and FHKB.
- Reference existing masking manifests as immutable, SHA-256-verified evidence
  with explicit artifact coverage; do not replace or duplicate their contents.
- Model TPDX as independently rebuildable topology, diagnostic-assertion, and
  replacement/material component packages referenced by a TPDX release
  package.
- Preserve route-specific record schemas, promotion rules, and release gates.
- Stop before producer implementation, runtime binding, real-data access, or
  Data RC aggregation.

### Changed files

- `docs/tasks/V2-TASK014_unified_data_package_manifest/brief.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/acceptance.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation

- Confirmed the active branch is `feature/v2-data-pipeline` and preserved the
  existing mixed worktree.
- Confirmed task directories `V2-TASK001` through `V2-TASK013` exist and
  allocated the next unused identifier, `V2-TASK014`.
- Reviewed the durable workflow, contract-engineer role guide, task template,
  frozen DEKG/FHKB contract task, masking identity task, and the planned TPDX
  Schema 4.2 pipeline task.
- Confirmed the new task does not overlap `V2-TASK013`: Task 013 owns the TPDX
  Schema 4.2 candidate pipeline; Task 014 owns the common package-envelope
  contract and compatibility design.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.

### Risks

- Existing DEKG and FHKB contracts repeat package-level fields but are frozen;
  they must not be edited in place merely to adopt a common envelope.
- The current masking manifest uses historical MD5 values for input files.
  Package integrity should add SHA-256 over the immutable masking manifest and
  packaged artifacts without rewriting historical evidence.
- TPDX Schema 4.2 is not frozen. The common envelope must select a contract
  explicitly and must not imply Schema 4.2 activation.
- Package decision state, masking state, serving safety, route eligibility,
  review state, and release state can diverge and require separate fields and
  validation rules.
- A cross-asset Data RC manifest is adjacent but remains workflow-lead and
  independent-review authority, not part of this contract-design task.

### State

Task decision state: `planned`.

## 2026-08-01 - DRAFT contract implemented and validated

### Plan

- Start at the approved common-envelope design step; do not repeat completed
  Schema 4.2 contract work or depend on a Task 013 pipeline candidate.
- Select the completed `V2-TASK012` Schema 4.2 package as the sole current TPDX
  contract while retaining Schema 4.1 only as a comparison/rollback baseline.
- Define package identity, integrity, masking evidence, decision-state,
  component-composition, compatibility, migration, rollback, and fail-closed
  rules without implementing a producer or reading real data.
- Prove the contract boundary with synthetic TPDX, DEKG, and FHKB packages and
  negative security/governance cases.

### Implemented

- Added the `faultdx_data_package_v1` DRAFT contract with one-package/one-asset
  profiles for TPDX, DEKG, and FHKB.
- Bound TPDX packages to `tpdx_kg_schema_v4_2`, DEKG packages to
  `dekg_evidence_v2`, and FHKB packages to `fhkb_case_v1` with closed route and
  package-type allowlists.
- Defined deterministic package and artifact identities, a non-self-referential
  content digest, portable paths, SHA-256 artifact integrity, collision
  behavior, and validation order.
- Added immutable masking-manifest references with effective, exact artifact
  coverage and kept masking, serving, route, review, promotion, package, and
  release states independent.
- Added independently rebuildable TPDX topology, diagnostic, and
  replacement/material component packages plus a record-free TPDX release
  package that references accepted component manifests by identity and digest.
- Documented frozen DEKG/FHKB compatibility mappings, phased migration,
  rollback, affected consumers, and the later pipeline/KG implementation
  handoff.
- Added synthetic validation covering valid TPDX/DEKG/FHKB packages and TPDX
  composition, plus mixed assets, route/contract mismatch, unsafe promotion,
  masking gaps/overlap, path escape, missing artifacts, digest mismatch,
  identity collision, invalid component status/digest, circular dependencies,
  unsafe release, and unknown fields.

### Changed files

- `contracts/package/faultdx_data_package_v1.json`
- `contracts/package/faultdx_data_package_v1.schema.json`
- `tests/unit/test_faultdx_data_package_contract.py`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/brief.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/acceptance.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation

- `python -m json.tool contracts/package/faultdx_data_package_v1.json` passed.
- `python -m json.tool
  contracts/package/faultdx_data_package_v1.schema.json` passed.
- `python -m py_compile tests/unit/test_faultdx_data_package_contract.py`
  passed.
- The sandbox Python did not expose `jsonschema`; `jsonschema==4.26.0` and its
  dependencies were installed into the system temporary directory only. No
  repository dependency or environment file was changed.
- With that temporary directory on `PYTHONPATH`, `python -m unittest
  tests.unit.test_faultdx_data_package_contract` passed all 16 tests with zero
  skips, including Draft 2020-12 metaschema and executable-instance checks.
- With the same temporary validation environment, `python -m unittest
  tests.unit.test_faultdx_data_package_contract
  tests.unit.test_dekg_fhkb_contracts
  tests.unit.test_tpdx_schema_v4_2_contract` passed all 45 tests with zero
  skips.
- `python scripts/check_workflow_guard.py` passed for the exact six-file Task
  014 write set: no protected workflow file changed.
- `git diff --check` passed.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.
- Frozen DEKG, FHKB, TPDX Schema 4.1, selected Schema 4.2, masking contracts,
  producers, runtime, graph, and index code were not modified.

### Risks and exclusions

- The DRAFT defines cross-file digest, filesystem-boundary, duplicate-package,
  and dependency-cycle behavior. The synthetic tests include a reference
  validator, but a production shared validator/loader remains a later,
  separately reviewed pipeline/KG implementation.
- Package canonicalization requires RFC 8785 JSON Canonicalization Scheme. The
  synthetic identity fixtures use only strings and integers and include a fixed
  package-ID vector; the later production implementation must use a conforming
  canonicalizer and add broader Unicode/number vectors.
- Schema 4.2 is selected as the TPDX working baseline, but Task 014 does not
  alter its recorded contract lifecycle state or claim freeze, activation, or
  release.
- Existing DEKG and FHKB envelopes remain valid and unchanged. Adoption of the
  common envelope requires separately reviewed adapters and consumer rollout.
- Affected producer/consumer acceptance and independent quality review remain
  open. No shared producer or loader implementation is authorized yet.

### State

Contract and executable JSON Schema: `implemented` and `validated`.

Contract decision state: `DRAFT`.

Affected-consumer review: `pending`.

Independent quality review: `pending`.

Released: `no`.

## 2026-08-01 - review handoff prepared

### Reviewed for handoff

- Non-data repository search found no existing shared package loader or
  producer binding to migrate in this task. Existing DEKG/FHKB adapters and
  tests continue to emit and validate their frozen route-specific packages.
- TPDX consumers currently reference Schema 4.2 contract/validator artifacts
  in the contract-test and governance paths; the package envelope adds an
  optional outer binding and does not alter those consumers.
- Legacy Schema 4.1 references remain in comparison/rollback and historical
  contract tests/docs. They are not selected by the Task 014 TPDX profile and
  were not modified.
- The three package profiles have distinct route families and contract IDs:
  TPDX/Route A/Schema 4.2, DEKG/Route B/dekg_evidence_v2, and
  FHKB/Route C/fhkb_case_v1. No Task 013 reference remains in the active
  contract.

### Handoff validation

- After adding the profile/route binding guard, the Task 014 unit suite passed
  all 17 tests with zero skips.
- The combined Task 014, DEKG/FHKB, and Schema 4.2 contract suite passed all 46
  tests with zero skips.
- Workflow guard, `git diff --check`, and exact Task 014 trailing-whitespace
  checks passed again.

### Review questions for the workflow lead and affected consumers

- Is the package identity tuple stable enough for producer rebuilds and
  collision handling, with mutable artifact/decision fields intentionally
  excluded?
- Do the exact-one effective masking coverage and independent decision-state
  rules match the masking and serving gates owned by consumers?
- Are the TPDX component acceptance, same-release, digest, and cycle rules
  sufficient for independently rebuildable topology, diagnostic, and
  replacement/material packages?
- Is the migration sequence safe as an optional envelope adoption, with no
  in-place rewrite of frozen DEKG/FHKB or Schema 4.2 artifacts?
- Which producer/consumer owner will own the later shared validator/loader
  implementation after this contract reaches `REVIEWED_PROPOSAL`?

### State

Review packet: `ready_for_affected_consumer_review`.

Affected-consumer acceptance: `pending`.

Independent quality review: `pending`.

Workflow-lead freeze/no-freeze decision: `pending`.

## 2026-08-11 - affected-consumer pre-review remediation

### Plan

- Start the affected producer/consumer review at the executable contract
  boundary without reading `data/` or modifying Task 015 paths.
- Compare the common envelope with the frozen DEKG/FHKB payload contracts and
  the now-frozen Schema 4.2 TPDX baseline.
- Close contract-owner defects before requesting formal consumer acceptance;
  do not self-record the affected-consumer or independent-review decisions.

### Review findings and remediation

- The DRAFT documented DEKG/FHKB compatibility mappings, but its synthetic
  reference validation did not prove that duplicated envelope and route-payload
  fields agreed. A wrapper could therefore carry a different release, source,
  lineage, masking, or serving claim from its enclosed frozen payload while
  both JSON documents remained independently valid.
- Added a semantic binding check requiring exact agreement for `release_id`,
  `source_id`, `source_version`, `manifest_digest` versus
  `lineage.source_manifest_digest`, `lineage_ref`, and `serving_safe`.
  Route-payload `masking_status` must also be compatible with the effective
  masking evidence covering the package's record payload.
- The DRAFT required a lineage source-manifest path and digest but the
  synthetic reference validator did not verify the referenced bytes. Added
  portable-path, existence, and SHA-256 verification before artifact
  validation.
- Updated the governed contract description and validation order to make both
  checks required implementation behavior rather than test-only assumptions.

### Changed files

- `contracts/package/faultdx_data_package_v1.json`
- `tests/unit/test_faultdx_data_package_contract.py`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation

- Baseline combined contract suite passed 46 tests before remediation.
- `.venv\Scripts\python.exe -m unittest
  tests.unit.test_faultdx_data_package_contract
  tests.unit.test_dekg_fhkb_contracts
  tests.unit.test_tpdx_schema_v4_2_contract` passed 48 tests after remediation,
  with zero failures or skips.
- Added negative coverage for every bound route-payload field, incompatible
  masking state, and a missing or digest-mismatched lineage source manifest.
- Existing TPDX, DEKG, and FHKB contract files were not modified.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.

### Risks and open review decisions

- Formal affected producer/consumer acceptance remains open; this contract-
  owner remediation is not acceptance on their behalf.
- Independent quality review and the workflow-lead freeze/no-freeze decision
  remain open.
- The review must explicitly decide whether one TPDX release may reference
  multiple accepted packages of the same component type or requires at most
  one topology, diagnostic, and replacement/material component. The current
  DRAFT rejects duplicate package IDs but intentionally does not invent a
  component-type cardinality rule.
- A production shared validator/loader and broader RFC 8785 Unicode/number
  vectors remain separately owned implementation work after contract review.

### State

Contract-owner affected-consumer pre-review: `implemented` and `validated`.

Contract decision state: `DRAFT`.

Affected producer/consumer acceptance: `pending`.

Independent quality review: `pending`.

Workflow-lead freeze/no-freeze decision: `pending`.

## 2026-08-11 - TPDX component cardinality decision accepted

### Decision

- The user accepted the contract recommendation that a v1 TPDX release may
  reference at most one accepted package of each component type: topology,
  diagnostic, and replacement/material.
- Any component type may be absent when it is not applicable, but two packages
  of the same type fail closed even when their package IDs differ.
- Multiple packages of one type are deferred to a later contract version that
  defines partition identity, non-overlap rules, and deterministic composition
  order. No triple generation or ingestion was required for this package-
  composition decision.

### Changed files

- `contracts/package/faultdx_data_package_v1.json`
- `contracts/package/faultdx_data_package_v1.schema.json`
- `tests/unit/test_faultdx_data_package_contract.py`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation

- The JSON Schema enforces zero-or-one reference for each allowed component
  type within a `tpdx_release`.
- The semantic reference validator independently rejects duplicate component
  types.
- A negative synthetic release with two different diagnostic component package
  IDs is rejected by both validation layers.
- No file under `data/` was opened, parsed, sampled, grepped, or validated.

### State

TPDX v1 component cardinality: `reviewed` and `implemented`.

Contract decision state: `DRAFT`; the specific cardinality decision does not
substitute for full affected-consumer or independent quality acceptance.

## 2026-08-11 - affected-consumer acceptance recorded

### Decision

- The user accepted the affected-consumer review recommendation and its four
  implementation conditions.
- The accepted boundary covers deterministic identity and collision behavior;
  frozen TPDX/DEKG/FHKB contract bindings; envelope/payload agreement; masking
  and serving-state separation; zero-or-one TPDX component cardinality;
  optional non-rewriting migration; rollback to unchanged route contracts; and
  later shared-validator ownership by `data_pipeline_kg_engineer`.
- The acceptance does not authorize real package production, runtime binding,
  graph ingestion, release, or Data RC promotion.

### Accepted implementation conditions

1. Real package IDs must not be issued until a conforming RFC 8785
   implementation passes broader Unicode and number vectors.
2. The common envelope remains optional until the shared validator and each
   route adapter are separately implemented and reviewed.
3. Production integration requires a separately allocated pipeline/KG task
   with an explicit owner and write set.
4. Contract acceptance must not be interpreted as runtime activation, graph
   ingestion, or release.

### Changed files

- `docs/tasks/V2-TASK014_unified_data_package_manifest/acceptance.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation evidence accepted

- The affected-consumer review covered current producer, adapter, import, and
  retrieval boundaries without reading `data/`.
- The combined package-contract, frozen route-contract, legacy-adapter, TPDX
  migration/import, and masking-manifest suites passed 76 synthetic tests.
- Existing route-specific producers and consumers remain unchanged because no
  production common-envelope loader is currently bound.

### State

Affected producer/consumer acceptance: `accepted_with_implementation_conditions`.

Independent quality review: `pending`.

Workflow-lead freeze/no-freeze decision: `pending`.

Contract decision state: `DRAFT` until the remaining review gates are closed.

## 2026-08-11 - independent review accepted and package contract frozen

### Reviewed and decided

- The user confirmed that N's independent quality review is complete and
  authorized Task 014 to advance to `FROZEN`.
- N's recorded recommendation is `READY` with no exclusions and no contract-
  freeze blocker.
- The workflow-lead freeze decision is recorded for
  `faultdx_data_package_v1` version `1.0.0`.
- The four affected-consumer implementation conditions remain binding after
  freeze; they are implementation gates rather than contract-review
  exclusions.

### Changed files

- `contracts/package/faultdx_data_package_v1.json`
- `tests/unit/test_faultdx_data_package_contract.py`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/brief.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/acceptance.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation

- `.venv\Scripts\python.exe -m json.tool` passed for the contract JSON and
  executable JSON Schema.
- The combined package-contract, frozen DEKG/FHKB and Schema 4.2 contract,
  legacy-adapter, TPDX migration/import, and masking-manifest suites passed 76
  tests with zero failures or skips.
- Python compilation of the Task 014 test module passed.
- Scoped `git diff --check` passed for the six-file freeze write set.
- No file under `data/` was opened, parsed, sampled, grepped, or indirectly
  validated.

### Boundaries and risks

- `FROZEN` approves the v1 package-envelope contract only. It does not produce
  or release a package, activate a loader, bind a runtime consumer, import a
  graph, build an index, make a Data RC decision, or authorize `data/` access.
- Real package IDs remain prohibited until a conforming RFC 8785 implementation
  passes broader Unicode and number vectors.
- The common envelope remains optional until separately reviewed shared-
  validator and route-adapter implementation exists.
- Production work requires a separately allocated pipeline/KG task with an
  explicit owner and write set.

### State

Contract and executable JSON Schema: `implemented`, `validated`, and `frozen`.

Affected producer/consumer acceptance: `accepted_with_implementation_conditions`.

Independent quality review: `READY`, no exclusions.

Workflow-lead decision: `FROZEN`.

Task decision state: `frozen`.

Released: `no`.

## 2026-08-01 - 中文审查准备记录

### 本阶段完成

- 已按用户确认，将 Schema 4.2 作为 TPDX 的当前统一 package contract
  绑定；没有修改 Schema 4.2 本身。
- 已确认 V2-TASK012 是已完成的合同输入，V2-TASK013 不属于 V2-TASK014
  依赖。
- 已完成非 `data/` 范围内的 producer/consumer 盘点：目前没有已存在的
  shared package loader 或 package envelope producer 需要直接迁移。
- 已确认 DEKG/FHKB 仍由各自冻结合同和 adapter 管理；公共 envelope 是
  可选外包装，不改变 Route B/Route C 的记录语义。
- 已确认旧 Schema 4.1 引用只位于比较、回滚或历史测试/文档范围，没有被
  新 package profile 选用。

### 本阶段验证

- Task 014 合同测试：17 项通过，零跳过。
- Task 014、DEKG/FHKB、Schema 4.2 联合合同测试：46 项通过，零跳过。
- 两个 package JSON、Draft 2020-12 Schema、Python 编译、workflow guard、
  `git diff --check` 和精确尾随空格检查均通过。
- 没有打开、解析、抽样、grep 或间接验证任何 `data/` 文件。

### 仍待外部审查的决定

- workflow lead 是否接受 package identity、masking coverage、组件依赖和
  回滚规则。
- TPDX/DEKG/FHKB producer/consumer owner 是否接受各自 route 与 contract
  绑定方式。
- 独立 quality reviewer 是否确认失败模型、重复/冲突处理和安全边界。
- 在上述决定完成前，不得把合同从 `DRAFT` 改成 `REVIEWED_PROPOSAL`，也不
  得实现 shared loader、producer integration 或真实 package 验证。

### 当前状态

- 合同实现和验证：`已完成`。
- 审查交接包：`已准备`。
- 受影响 consumer 接受：`待处理`。
- 独立质量审查：`待处理`。
- freeze/no-freeze 决定：`待处理`。
- release：`未发生`。

## 2026-08-01 - 中文交接前收口

### 本轮执行

- 已将 brief 中实际完成的十项合同交付物标记为完成，包括公共 DRAFT、
  三资产 package profile、TPDX component/release、masking coverage、
  兼容性、确定性 digest、合成 fixture、失败行为、consumer inventory 和
  验证证据。
- 没有把受影响 producer/consumer 的接受状态或独立质量审查误标为完成。
- 没有实现 shared loader、producer adapter、runtime binding、graph/index
  接入或真实 package 验证。

### 交接结论

当前合同已经达到“可交给外部审查”的状态，但还不能进入
`REVIEWED_PROPOSAL`、`FROZEN` 或 `RELEASED`。下一步必须由指定 owner 和
独立 reviewer 记录正式意见；本实现者不代写该结论。

### 外部审查记录模板

- workflow lead：`待填写`
- 受影响 producer/consumer owner：`待填写`
- 独立 quality reviewer：`待填写`
- 审查输入版本：`faultdx_data_package_v1 DRAFT`，测试版本：`46 项联合合同测试`
- 审查发现、失败案例和排除项：`待填写`
- 独立结论：`READY / READY_WITH_EXCLUSIONS / NOT_READY（待填写）`
- 必须修复的问题：`待填写`
- 下一责任人：`待填写`
- freeze/no-freeze：`待填写`

## 2026-08-11 - current authoritative freeze state

This entry supersedes the unfilled 2026-08-01 review templates above without
rewriting their historical record.

- Affected producer/consumer decision:
  `accepted_with_implementation_conditions`.
- Independent reviewer N: `READY`, no exclusions.
- Workflow-lead decision: `FROZEN`.
- Contract: `faultdx_data_package_v1` version `1.0.0`, `FROZEN`.
- Validation: 76 tests passed; JSON parsing, Python compilation, and scoped
  `git diff --check` passed.
- Next owner: `data_pipeline_kg_engineer`, only through a separately allocated
  implementation task and explicit write set.
- Runtime activation, real package production, graph/index ingestion, Data RC,
  release, and `data/` access remain unauthorized.

## 2026-08-11 - post-freeze handoff documents generated

### Plan

- Generate the two handoff documents requested by the user from the frozen
  Schema 4.2 and package v1 contract records.
- Preserve the distinction between contract freeze and runtime activation,
  Serving Build, Data RC, deployment, or release.
- Record the absent `route_abc_contract_freeze_v1.json` as a verification gap
  rather than inventing freeze-manifest hashes.

### Implemented

- Added a scoped contract-package changelog covering the frozen Schema 4.2 and
  `faultdx_data_package_v1` 1.0.0 decisions, compatibility, breaking migration,
  continuing implementation conditions, and current artifact hashes.
- Added a consumer impact matrix for the external A4.2, A4.1, B2.0, and C1.0
  handoff labels and the affected repository producers, importers, evaluators,
  route adapters, package validator, and Data RC preparation boundary.
- Did not change any contract, schema, runtime, pipeline, test, or `data/`
  artifact.

### Changed files

- `CHANGELOG.md`
- `consumer_impact_matrix.md`
- `docs/tasks/V2-TASK014_unified_data_package_manifest/notes.md`

### Validation

- `python scripts/check_workflow_guard.py` passed for the exact three-file
  handoff-document write set: no protected workflow files changed.
- Scoped `git diff --check` passed for the tracked task-note change.
- Exact path, SHA-256, Markdown trailing-whitespace, and missing-freeze-manifest
  checks passed for both handoff documents. The four recorded hashes match the
  current tracked artifacts, and those artifacts match `HEAD`.
- `route_abc_contract_freeze_v1.json` remains absent; archive verification
  against its approved hashes was not possible and is explicitly blocked.
- No file under `data/` was opened, parsed, sampled, grepped, or indirectly
  validated.

### State

Handoff documents: `implemented` and `validated`.

Contract state: `FROZEN`, unchanged.

Released: `no`.

## 2026-08-11 - N contract-review folder prepared

### Plan

- Create a bounded onboarding folder for N's contract review.
- Copy, without moving or modifying the originals, the four frozen contract
  artifacts and the two handoff documents requested by the user.
- Keep the folder limited to the six highlighted files; do not infer or create
  the absent contract-freeze manifest.

### Implemented

- Created `docs/onboarding/N_contract_review/`.
- Added flat copies of the four contract artifacts, `CHANGELOG.md`, and
  `consumer_impact_matrix.md`.
- Preserved every source file in its original repository location.

### Validation

- Exact file-count validation passed: the folder contains six files and no
  subdirectories.
- SHA-256 comparison passed for every source/destination pair, and all six
  original files remain present.
- The three copied JSON files parse successfully.
- `python scripts/check_workflow_guard.py` passed for the exact seven-file
  review-folder and task-note write set: no protected workflow files changed.
- Scoped `git diff --check` passed for the tracked task-note change.
- `route_abc_contract_freeze_v1.json` was not added or inferred.
- No file under `data/` was opened, parsed, sampled, grepped, or indirectly
  validated.

### State

N contract-review folder: `implemented` and `validated`.

Contract state: `FROZEN`, unchanged.

Released: `no`.
