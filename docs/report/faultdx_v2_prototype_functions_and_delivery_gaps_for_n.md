# FaultDx v2 原型功能与原型后交付缺口（面向 N）

> 版本日期：2026-08-12
>
> 来源分支：`feature/v2-data-pipeline`
>
> 用途：向 N 说明当前原型已经能演示什么、哪些能力尚未达到正式交付，以及 A 数据线与 N 系统线后续需要如何衔接。
>
> 状态口径：本文严格区分 `原型可演示`、`已实现`、`已验证`、`已冻结候选`、`Data RC ready` 和 `released`。代码或页面存在不等于正式交付。

## 1. 一句话结论

FaultDx v2 当前已经形成“用户提问 → 自动选择 Route A/B/C → 展示诊断/证据/案例 → 安全提示与弃答 → 保存对话和反馈”的本地演示闭环。

但是，原型仍主要依赖 smoke、fixture、dry-run 和本地文件，尚未形成“真实治理数据 → Schema 4.2 诊断与材料生产 → 正式数据包 → Neo4j 影子导入 → 受控查询 → 独立验证 → Data RC → N 系统消费 → 部署发布”的正式交付闭环。

因此，目前可以称为“可演示原型”，不能称为“可上线系统”或“Data RC ready”。

## 2. 原型当前具备的功能点

| 序号 | 模块 | 功能点 | 优先级 | 当前状态 | 当前边界 |
|---:|---|---|---|---|---|
| 1 | 诊断交互 | 中文自然语言问题输入 | P0 | 原型可演示 | 可输入设备、报警码、SOP 和相似案例问题 |
| 2 | 智能路由 | Route A/B/C 自动路径选择 | P0 | 原型可演示 | 根据问题类型进入结构化诊断、文档证据、历史案例或 fallback |
| 3 | Route A | 结构化故障诊断展示 | P0 | 原型可演示 | 可展示现象、错误码、原因、措施和步骤；当前主要依赖 smoke/fixture 数据 |
| 4 | Route B | SOP/文档证据检索 | P0 | 原型可演示 | 结果保持 `document_evidence + evidence_only`，不能作为确认诊断 |
| 5 | Route C | 相似历史案例查询 | P1 | 原型可演示 | 结果保持 `case_reference + candidate`，采取行动前需要人工确认 |
| 6 | 结果展示 | 统一诊断结果结构 | P0 | 原型可演示 | 可展示结论、原因、建议动作、证据、来源和风险提示 |
| 7 | 状态安全 | 路径与成熟度提示 | P0 | 已实现原型规则 | 区分 reviewed diagnosis、document evidence、case candidate 和 fallback |
| 8 | 证据展示 | 使用来源与证据片段展示 | P0 | 原型可演示 | 已有来源/证据结构，但尚未完成 Data RC 级端到端 provenance |
| 9 | 安全弃答 | 证据不足时不强行诊断 | P0 | 已实现原型规则 | 返回 `not_available` 或相应安全状态，不制造原因和动作 |
| 10 | 演示样例 | A/B/C 预置案例选择 | P1 | 原型可演示 | 用于内部演示、路径核对和安全行为检查 |
| 11 | 对话管理 | 创建、保存、重命名和删除对话 | P1 | 原型可演示 | 当前使用本地 JSON 文件，不是正式持久化服务 |
| 12 | 用户反馈 | 点赞、点踩、问题标签、正确答案反馈 | P1 | 原型可演示 | 支持回答错误、证据不足、路由错误、过度断言等标签 |
| 13 | 坏案例沉淀 | 自动生成 bad-case candidate | P1 | 原型可演示 | 点踩、过度断言或提供正确答案时进入后续复盘候选 |
| 14 | API | `/api/diagnose` 诊断接口 | P0 | 简化实现 | 当前是薄 API skeleton，主要调用本地 dry-run 路由链 |
| 15 | 本地运行 | Diagnosis Workbench | P0 | 原型可演示 | local-first 内部评审工具，不是生产部署形态 |
| 16 | 降级处理 | 无法识别或无证据时 fallback | P0 | 已实现原型规则 | 不可用路径返回安全的 `not_available` 结果 |

## 3. 已取得但不能误报为产品交付的成果

| 成果 | 当前实际状态 | 不能据此声称 |
|---|---|---|
| TPDX Schema 4.2 | 契约已冻结 | 不能声称已被生产运行时采用或已发布 |
| 统一数据包契约 | 契约已冻结 | 不能声称真实组件包生产器和 Data RC 已完成 |
| CAD 2D A/B/C 管线 | Phase 3 r10 候选已实现、验证并冻结后交 Task016 | 不能声称已进入 KG、serving、Data RC 或 release |
| Route A/B/C Workbench | 可以本地演示和记录反馈 | 不能声称真实数据端到端、生产安全和部署验收已通过 |
| API 与路由链 | 存在本地 skeleton/dry-run 能力 | 不能声称生产级运行时、并发、可靠性和消费者兼容性已完成 |

## 4. 原型后必须继续开发的 P0 事项

| 顺序 | 工作项 | 当前状态 | 达成标准 | 主要责任 |
|---:|---|---|---|---|
| 1 | Schema 4.2 材料解析器及材料候选 | Task017 `planned` | 完成受控配置、解析器、候选/排除/审计/manifest、安全测试并冻结候选 | A 数据线 |
| 2 | 真实诊断记录生产器 | Task019 `planned` | Error Code、Repair SOP 和审核表格可以确定性地产生 Schema 4.2 诊断对象，保留来源、审核和 Cause–Action 配对 | A 数据线 |
| 3 | TPDX 组件包生产与校验 | Task020 `planned` | topology、diagnostic、material 组件可独立校验，并可确定性组装 `tpdx_release` | A 数据线 |
| 4 | Neo4j 影子导入与回滚 | Task021 `planned` | 完成约束/索引、幂等导入、冲突拒绝、图摘要、隔离影子验证和可执行回滚 | A 数据线；需要图数据库运维配合 |
| 5 | Schema 4.2 受控查询适配器 | Task022 `planned` | 仅允许注册的参数化只读查询，明确区分 success/no-result/ambiguous/excluded/abstain/error | A 数据线；N 确认消费契约 |
| 6 | CAD/材料独立验证 | Task016 `planned` | CAD 与材料分别完成可复现性、合同、领域正确性、回归、安全和排除项审查 | 独立质量审查；A 提供冻结候选 |
| 7 | TPDX 独立验证与 Data RC | Task023 `planned` | 冻结所有输入，完成六类评分、旧/新差异、泄漏检查、回滚评估并给出唯一 readiness 决定 | 独立质量审查 + workflow lead |
| 8 | N 消费者适配 | 尚未由本分支完成 | N 明确采用的合同/版本，完成 package、图查询、状态、provenance、错误和 fallback 适配 | N 系统线 |
| 9 | 真实端到端验收 | 未完成 | 从真实批准输入到 UI/API 结果全链路验证，证明结果、证据、状态和安全边界一致 | A/N 联合；独立验证 |
| 10 | 生产部署与发布 | 未完成 | 权限、密钥、持久化、日志、监控、备份、回滚、容量、故障恢复和发布审批全部通过 | N 系统/发布线 |

## 5. 若正式范围包含完整 Route A/B/C，还需完成

下列事项在 TPDX Route A 数据闭环之外，但如果本轮对外承诺完整 A/B/C 产品能力，则同样属于必须项：

- Route B：完成真实 Vision SOP/DEKG producer 运行、完整 E3 inventory、替换包、索引资产和消费者验证；继续保持 evidence-only。
- Route C：完成 Y25/FHKB 真实来源发现、治理登记、历史案例包、索引和独立质量审查；继续保持 candidate-only。
- 验证 Route A/B 同源事实不会被重复计算为独立佐证。
- 验证 Route B/C 结果不会在 UI、API、模型回答或日志中被提升为 confirmed diagnosis。

如果本轮只承诺 TPDX Route A，可以将 Route B/C 的生产化放入后续版本；但原型中的 Route B/C 必须继续明确标记为演示/候选能力。

## 6. N 需要重点确认的系统侧事项

1. 最终采用的 Schema、package、API result 和查询注册表版本。
2. N 的 runtime 如何消费 A 提供的 package、manifest、checksum、lineage、状态与 exclusions。
3. Route A/B/C 在 UI 和答案组装中的展示规则，特别是 reviewed、evidence-only、candidate 和 fallback 的不可混淆性。
4. API 超时、图数据库不可用、模型不可用、无结果、歧义、排除和安全弃答的最终行为。
5. 对话、反馈、bad case 的正式持久化、访问控制、保留期和审计方式。
6. provider、模型调用、敏感字段过滤、prompt 输入边界以及外部调用审批。
7. 部署环境、密钥注入、并发/容量、日志监控、备份恢复和发布回滚。
8. N consumer validation 与 Data RC 的进入条件；在 Data RC 前不得把原型 fixture 当成正式 serving 数据。

## 7. 推荐推进顺序

```text
Task017 材料候选
        +
Task019 诊断候选
        ↓
Task016 CAD/材料独立验证（可在候选齐备后完成）
        ↓
Task020 组件包与 tpdx_release
        ↓
Task021 Neo4j 影子导入和回滚
        ↓
Task022 受控查询与结果契约验证
        ↓
Task023 独立 Data RC 评审
        ↓
N consumer/runtime/UI 适配
        ↓
A/N 真实端到端验收
        ↓
部署与发布审批
```

Task019 与 Task017 可以在所有权不冲突且各自数据权限明确时分别推进；Task020–023 必须遵守其依赖和独立审查边界。

## 8. 建议用于项目拆分表的状态口径

| 表格状态 | 建议含义 |
|---|---|
| 完整交付 | 已实现、验证并完成适用评审；若涉及发布，还必须有明确 release/Data RC 证据 |
| 简化交付 | 主要代码/契约已完成，但真实数据、独立评审或生产集成仍缺失 |
| 演示模式 | 可以用 smoke、fixture、dry-run 或本地文件完成演示，不代表可上线 |
| 待开发/延期 | 尚未达到实现或验收条件，必须继续开发或等待前置依赖 |

## 9. 当前总体判断

- **原型演示：具备。**
- **核心 Schema/包契约：已冻结。**
- **CAD 候选：已冻结，但尚未具备 serving/KG/release 资格。**
- **材料候选、真实诊断 producer、组件打包、影子图、查询适配：未完成。**
- **独立 Data RC：未完成。**
- **N 系统消费、正式运行时和部署发布：未完成。**

当前最准确的对外表述是：

> FaultDx v2 已具备本地 A/B/C 诊断工作台原型和部分冻结的数据契约/候选资产；原型后的数据生产、知识图谱、查询、独立验证、系统集成与上线交付仍需按 Task017、Task019–023 及 N 系统任务继续完成。

## 10. 参考入口

- `apps/ui/diagnosis_workbench/server.py`：本地 Diagnosis Workbench。
- `apps/api/diagnose.py`：薄诊断 API skeleton。
- `services/reasoning/route_graph.py`：Route A/B/C 本地路由执行链。
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/`：冻结 CAD 候选及交接状态。
- `docs/tasks/V2-TASK016_material_cad_independent_validation/`：CAD/材料独立验证。
- `docs/tasks/V2-TASK017_material_parser_integration/`：材料解析器与候选。
- `docs/tasks/V2-TASK019_tpdx_diagnostic_record_producer/`：诊断记录生产器。
- `docs/tasks/V2-TASK020_tpdx_component_package_producer_validator/`：组件包生产与校验。
- `docs/tasks/V2-TASK021_neo4j_shadow_import_rollback/`：影子导入与回滚。
- `docs/tasks/V2-TASK022_schema_v4_2_validation_query_adapter/`：受控查询适配器。
- `docs/tasks/V2-TASK023_tpdx_data_rc_independent_validation/`：独立验证与 Data RC。
- `HANDOFF_INTEGRATION.md`：A/N 稳定集成边界。
