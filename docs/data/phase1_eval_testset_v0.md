# Phase 1 Eval Testset v0

## 目的

本文档说明 TASK-009 当前可执行的 Phase 1 eval / testset 层。

这批数据的目标不是一次性做成最终 benchmark，而是先把 Phase 1 评估对象、文件拆分方式、字段契约和可执行校验边界固定下来。当前覆盖：

- 意图路由：对齐 TASK-008 routing contract。
- KG 诊断链：先保留 pending / contract 形态，等待 reviewed EC/FP/RC/RA 后升级。
- 设备资产层：先校验 Station / Module / Component / Sub-Component 边界，当前不新增 QPL 节点。
- 案例检索：先固定 related / candidate / fallback 的 expected 形态。
- 文档证据：使用 E3 VLM serving-safe 输出校验证据块和泄漏边界。
- Troubleshooting：先验证证据引用和 few-shot 边界，不把 SOP 或 VLM 输出提升为 KG fact。
- 安全负例：覆盖 raw source、internal VLM、future executor、overclaim、GraphRAG/text2cypher default 等不应进入当前路径的情况。

## 当前状态

当前共有 **67 条 cases**。其中 `routing` 和 `safety_negative` 已先扩到每类 25 条；其他类别保持 smoke seed / contract seed，等待真实数据和执行链路到位后再扩。

目标规模仍然是：

- 每个 eval/testset 文件最终至少 **25 条 cases**。
- 每个文件内覆盖多个 scenario。
- 每个 scenario 至少 **3 条 cases**。
- reviewed / integration 依赖的数据未到位时，不用未审核数据凑 gold set；用 `pending_*`、`contract_only` 或 `serving_safe_fixture` 标注成熟度。

当前不应把 review baseline、semantic candidates、RAG-only cases、troubleshooting SOP、internal VLM canonical output 当作 confirmed KG facts。

## 文件与数量

`data/eval/phase1_eval_testset_v0.json` 是 manifest / 索引文件，不直接存放 cases。实际 cases 按 eval 类型拆分在不同 JSON 文件中，方便每类测试维护自己的 `expected` 字段。

| 文件 | track | case 数 | 当前定位 |
| --- | --- | ---: | --- |
| `data/eval/phase1_eval_testset_v0.json` | manifest | 7 个 testset 入口 | 汇总入口，不直接放 case |
| `data/eval/phase1_routing_eval_v0.json` | `routing` | 25 | TASK-008 route family / route target / source gate |
| `data/eval/phase1_kg_diagnosis_eval_v0.json` | `kg_diagnosis` | 4 | KG 诊断链 contract / pending reviewed mapping |
| `data/eval/phase1_asset_eval_v0.json` | `kg_asset` | 3 | 设备资产层 contract；当前不新增 QPL 节点 |
| `data/eval/phase1_case_retrieval_eval_v0.json` | `case_retrieval` | 3 | related / candidate field case 边界 |
| `data/eval/phase1_document_evidence_eval_v0.json` | `document_evidence` | 3 | E3 VLM serving-safe 文档证据边界 |
| `data/eval/phase1_safety_negative_eval_v0.json` | `safety_negative` | 25 | raw / internal VLM / future executor 等安全负例 |
| `data/eval/troubleshooting_eval_testset_v0.json` | `troubleshooting` | 4 | troubleshooting evidence / few-shot 边界 |

## Schema 形态

TASK-009 使用 **common envelope + track-specific `expected` payload**。这样每类 eval/testset 可以只保留自己需要的 gold 字段，不需要共享一条超宽 schema。

公共字段：

- `case_id`
- `track`
- `query`
- `source_status`
- `data_readiness`
- `gold_status`
- `expected_assertion_level`
- `expected`

各 track 的 `expected` 只写本类测试需要的字段：

| track | `expected` 重点 |
| --- | --- |
| `routing` | `intent`、`route_family`、`route_target`、`kg_eligible`、allowed / blocked sources |
| `kg_diagnosis` | pending chain shape 或 reviewed triples |
| `kg_asset` | Station / Module / Component / Sub-Component contract；当前不要求 QPL |
| `case_retrieval` | related / candidate evidence policy |
| `document_evidence` | serving-safe evidence block、anchor、VLM response 泄漏检查 |
| `troubleshooting` | troubleshooting evidence usefulness，不提升为 KG fact |
| `safety_negative` | blocked unsafe sources、overclaim、leakage |

Routing JSON 中的 `expected.route_target` 对应 TASK-008 当前实现里的 `RoutingDecision.route`。

## TASK-008 Router Contract

Routing cases 按当前 TASK-008 contract 校验：

| route_family | route_target | 含义 |
| --- | --- | --- |
| `route_a_structured` | `reviewed_diagnostic_chain` | reviewed EC / FP / RC / RA 诊断链 |
| `route_a_structured` | `asset_structured_query` | reviewed 设备资产层查询 |
| `route_b_document` | `document_evidence_retrieval` | serving-safe SOP / manual 文档证据 |
| `route_c_case_governance` | `structured_catalog` | 无 reviewed chain 时的 EC / FP catalog fallback |
| `route_c_case_governance` | `case_retrieval` | related field case retrieval |
| `route_c_case_governance` | `fp_review_governance` | review / governance queue |
| `fallback` | `insufficient_context` | 信息不足、不安全或不支持 |

## Scenario 扩展计划

| track | 当前 case 数 | 目标 case 数 | 建议 scenario | 当前状态 |
| --- | ---: | ---: | --- | --- |
| `routing` | 25 | >= 25 | EC catalog fallback、reviewed chain、FP fallback、document query、asset query、unknown/ambiguous、unsafe source | 已达阶段目标 |
| `kg_diagnosis` | 4 | >= 25 | EC-only、pending reviewed chain、review baseline negative、semantic candidate negative、reviewed triples | 等 2026-05-06 后扩 reviewed triples |
| `kg_asset` | 3 | >= 25 | Station/Module/Component hierarchy、no-QPL policy、TRIGGERS/TARGETS/REF_DOC boundary、asset unknown fallback | 等设备资产层数据确认 |
| `case_retrieval` | 3 | >= 25 | similar downtime、field case related evidence、ambiguous case query、candidate-only negative、no-evidence fallback | 等 retrieval/case pool 后扩 |
| `document_evidence` | 3 | >= 25 | SOP block evidence、manual evidence、FAT-SAT evidence、serving-safe anchor、VLM leakage negative、no-evidence fallback | 可基于 E3 serving 继续扩，但语义命中质量等待 retrieval runner |
| `safety_negative` | 25 | >= 25 | raw source、internal VLM canonical、future executor、overclaim、missing evidence、candidate promotion、GraphRAG/text2cypher default | 已达阶段目标 |
| `troubleshooting` | 4 | >= 25 | symptom-to-step、action-to-SOP block、ambiguous query、few-shot usefulness、KG promotion negative | 可部分扩，语义质量等待 retrieval runner |

## Runner 定位

`scripts/run_eval/run_phase1_eval_v0.py` 当前定位是 **eval testset validator / smoke runner**，不是最终端到端 benchmark。

它现在负责：

- 校验 testset JSON 格式和 common envelope。
- 校验 routing cases 和 TASK-008 当前 contract 对齐。
- 校验 KG diagnosis pending / reviewed contract shape。
- 校验 asset layer 当前不引入 QPL 节点。
- 校验 case retrieval related / candidate evidence contract。
- 校验 document / troubleshooting evidence 的 serving-safe source、block anchor、禁止字段泄漏。
- 校验 safety negative 的 blocked source、leakage 和 overclaim expectations。

最终 benchmark 应等待 routing + retrieval + KG + GraphRAG + answer assembly 链路打通后，再接入真实执行结果。

从 repo root 运行全部 testsets：

```powershell
python scripts/run_eval/run_phase1_eval_v0.py
```

只跑某一类：

```powershell
python scripts/run_eval/run_phase1_eval_v0.py data/eval/phase1_routing_eval_v0.json
```

输出 JSON summary：

```powershell
python scripts/run_eval/run_phase1_eval_v0.py --json
```

## 当前验证结果

最近一次执行：

```text
Phase 1 eval v0: 67/67 passed
- routing: 25 passed, 0 failed
- kg_diagnosis: 4 passed, 0 failed
- kg_asset: 3 passed, 0 failed
- case_retrieval: 3 passed, 0 failed
- document_evidence: 3 passed, 0 failed
- safety_negative: 25 passed, 0 failed
- troubleshooting: 4 passed, 0 failed
```

配套单测：

```text
python -m unittest tests.unit.test_phase1_eval_v0 tests.unit.test_query_router
Ran 20 tests, OK
```

## Sprint 5 评估目标

| 维度 | 已做到 | 还缺什么 | 本 sprint 建议补到什么程度 |
| --- | --- | --- | --- |
| 过程稳不稳：routing | Route A/B/C router 已有基础验证 | 缺少按真实 `/api/diagnose` 链路跑的三路 smoke matrix | 每条 route 至少 5-10 条代表 query，验证 route、executor、status、fallback |
| 过程稳不稳：source safety | Route B/C 已有 source boundary 和 candidate/evidence-only | UI/LLM 组装后是否仍不越权还没充分测 | 加 answer-level safety check：Route B 不说 confirmed，Route C 不说 reviewed |
| 过程稳不稳：版本追踪 | 部分 task 有 benchmark 和 notes | 缺统一记录 model/index/kg/prompt/api version | feedback 日志里必须带 route、prompt_version、kg_or_index_version、answer_id |
| 结果对不对：Route A | 有 KG/text2cypher/diagnostic chain 验证 | LLM 组装后的答案是否忠于 KG 还缺评估 | 先评估"是否引用正确 error/cause/action/evidence"，不追求语言完美 |
| 结果对不对：Route B | GraphRAG benchmark 已有 top1/top3/MRR | 生成答案是否过度解释文档证据还缺评估 | 检查 evidence-only 表达，不允许生成确认性诊断 |

## 后续升级

- 2026-05-06 reviewed mapping 到位后，把部分 `kg_diagnosis` cases 从 pending chain shape 升级为 reviewed triples。
- 设备资产层数据最终确认后，把 `kg_asset` cases 从 contract-only 升级为 integration runner。
- retrieval / case pool 到位后，把 `case_retrieval` 从字段契约升级为真实召回质量评估。
- document evidence 和 troubleshooting 接入 retrieval runner 后，再扩到每类 25+，并补充命中质量、证据排序和答案引用校验。
- GraphRAG / text2cypher 相关能力只有在治理和执行边界明确后才接入 benchmark，不作为默认入口。
