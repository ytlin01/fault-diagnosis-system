# FaultDx Phase 2 — Data Engineering

FaultDx 主仓库用于承载正式开发、协作评审、评估、发布与内测上线工作。当前分支（`feature/v2-data-pipeline`）专用于 Phase 2 数据工程、数据治理与知识图谱摄取；Phase 1 基线保留在 `phase1_v1`。

## Team Red Lines

- 业务开发不要顺手修改 `AGENTS.md`、`HANDOFF_README.md`、`docs/agents/`、task 模板和 `.github/` 中的 workflow 文件。
- 如需修改上述协作规则文件，请先按治理类变更处理，并补充原因、影响范围和同步更新项。
- 任何结果要优先沉淀到仓库文档和 `docs/tasks/V2-TASK###_<name>/notes.md`，不要只留在聊天记录里。

## Repository Role

- `faultdx_main/` 是唯一主项目工作区。
- `Faultdx_ref/` 仅作为参考工作区，存放参考 repo 与分析材料，不属于本主仓库内容。
- 当前分支目标是建设可治理、可复现、面向 GPU 版 FaultDx 的 Phase 2 数据与知识图谱管线。

## Phase 2 Data Engineering Focus

- 以 `data/governance/source_inventory.csv` 与 `masking_log.jsonl`、`annotation_log.jsonl`、`index_registry.jsonl`、`eval_run_log.jsonl` 管理跨 `raw/`、`processed/`、`serving/`、`eval/` 的治理记录
- 不再使用 `data/data_governance.xlsx` 作为治理文件；如未来需要 review export，必须从上述 canonical records 生成，且不得作为 mutation target
- 建设 schema v4.0、结构化与非结构化摄取、脱敏、验证和知识图谱导入流程
- 围绕 `Phenomenon`、`MappingRecord` 保持数据、评估与下游检索契约一致
- 为 GPU 版 FaultDx 交付可追踪、可复现且可治理的数据资产

## 当前重点（数据闭合）

- 数据四分区重组（`raw/` / `processed/` / `serving/` / `eval/`）与治理层建设
- Route A 数据扩展：FP 现象查询、Layer B 电子/控制/网络层、材料层
- 诊断-资产 Bridge 从单一匹配升级为候选集；`TRIGGERS` 优先级语义
- 故障排查 SOP 评审，确定其可用于 benchmark 与 evidence 的范围
- Route B / C 数据决策推迟至完整数据流到位后再定

## Top-Level Layout

- `apps/`: API 与 UI 入口
- `services/`: ingestion、schema、graph、retrieval、reasoning、skills、logging、eval 等服务边界
- `libs/`: 公共能力、provider 封装、prompts、contracts
- `configs/`: 环境与治理配置
- `data/`: 原始、处理中、服务层和评估数据目录
- `docs/`: 架构、数据、报告、运行手册、发布、agent 协作说明
- `tests/`: 单元、集成、回归测试
- `scripts/`: bootstrap、ingest、graph、eval、release 流程脚本
- `references/`: 主仓库内部的参考说明，不存放参考 repo 代码

## Security Baseline

- 原始敏感数据不得提交进 Git。
- 原始敏感数据不得直接暴露给外部 API 或第三方模型服务。
- 本地路径、密钥、模型地址、临时凭据一律通过环境变量或部署配置注入。

## Collaboration Baseline

- 普通开发默认围绕 `docs/tasks/V2-TASK###_<name>/` 推进，而不是围绕聊天窗口推进。
- `AGENTS.md`、`HANDOFF_README.md`、`docs/agents/`、task 模板与 `.github/` 中的 workflow 文件属于协作规则入口，不应在普通开发中顺手修改。
- 如需调整协作规则、任务模板或 handoff 方式，应将其作为治理类修改单独说明。

更多仓库协作规范见 `AGENTS.md`。

## Branch-safe commit and push

Work on this branch stays on `feature/v2-data-pipeline`. The worktree may contain
unrelated user changes, so inspect and stage only the files owned by the current
task. Do not rebase onto, merge into, or push directly to `main`.

```bash
# Confirm branch and preserve the existing mixed worktree.
git status --short --branch

# Review the current task's exact write set.
git diff -- path/to/file1 path/to/file2

# Stage explicit paths only. Never use `git add .` or `git add -A` here.
git add -- path/to/file1 path/to/file2
git diff --cached

# Commit one scoped change group after its required validation passes.
git commit -m "data: describe the scoped change"

# Push only the current data-pipeline branch.
git push origin feature/v2-data-pipeline
```

Keep governance, contract/schema, pipeline/KG, and evaluation changes in
separate commits. Do not create or push `integration/v2` until Data Contract
Freeze and Data RC review authorize that step.
