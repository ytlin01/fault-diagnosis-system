# FaultDx Phase 1 — Masking Pipeline Runbook

## 概览

本 pipeline 将 `data/raw/` 中的原始数据通过代码化脱敏，产出三视图：

| 视图 | 目录 | 消费者 |
|---|---|---|
| Raw View | `data/raw/` | 仅脱敏脚本读取；不入 Git |
| Internal Canonical | `data/processed/` | 本地图谱、检索、Ollama 评估 |
| External Serving | `data/serving_structured/` / `data/serving_unstructured/` | API、UI、DeepSearch、网络侧 LLM |

## 目录结构

```
data/
├── raw/                              # 原始数据（不入 Git）
│   ├── *.xlsx / *.csv
│   └── minerU_output/                # MinerU 抽取结果
├── processed/                        # Internal Canonical View
│   ├── {source}_canonical.json
│   ├── unstructured/
│   │   └── {doc}_canonical.*
│   ├── _manifests/
│   │   └── {source}_manifest_{ts}.json
│   └── _lineage/
│       └── {source}_lineage_{ts}.jsonl
├── serving_structured/               # External Serving (结构化)
│   └── {source}_serving.json
├── serving_unstructured/             # External Serving (非结构化)
│   └── {doc}_serving.*
└── eval/                             # 评估集
    └── troubleshooting_sop_serving.json
```

## 前置条件

1. **设置 masking salt**（必须，否则 pipeline 拒绝运行）：
   ```bash
   # 在 .env 中添加（不入 Git）
   FAULTDX_MASKING_SALT=your-random-secret-string-here
   ```

2. **原始数据就位**：将原始 xlsx/csv 文件放入 `data/raw/`

3. **Python 环境**：确保 venv 中有 `pyyaml`、`openpyxl` 依赖

## 运行步骤

### 1. 查看规则解析结果（无需数据）

```bash
python scripts/ingest/preview_masking.py rules --source y25_downtime
```

输出每列的分级、canonical 动作、serving 动作、review 标记。

### 2. Dry-run 预览（需要数据）

```bash
python scripts/ingest/run_mask_structured.py --source y25_downtime --dry-run --rows 5
```

不写文件，在终端显示前 N 行的 before/after 对比。

### 3. 正式运行

```bash
python scripts/ingest/run_mask_structured.py --source y25_downtime
```

### 4. 非结构化文档脱敏

```bash
python scripts/ingest/run_mask_unstructured.py --input-dir data/raw/minerU_output
```

## 人工核验清单

### A. Manifest 检查
- [ ] 打开 `data/processed/_manifests/{source}_manifest_{ts}.json`
- [ ] 确认 `input.row_count == output.canonical.row_count`
- [ ] 确认 `review_flag_columns` 列表是否合理

### B. Lineage 抽检
- [ ] 打开 `data/processed/_lineage/{source}_lineage_{ts}.jsonl`
- [ ] 随机抽查 10 行
- [ ] 确认 A 级字段的 action 为 `tokenize`（canonical）或 `drop`（serving）
- [ ] 确认 B 级字段在 serving 中已泛化
- [ ] 确认 C 级字段完整保留

### C. Serving 输出安全检查
- [ ] 打开 `data/serving_structured/{source}_serving.json`
- [ ] 确认无 DRI 列残留
- [ ] 确认无邮箱、电话、工号等 A 级字段
- [ ] 运行 audit 扫描：
  ```bash
  python scripts/ingest/preview_masking.py audit --scan-dir data/serving_structured
  ```

### D. 非结构化输出检查
- [ ] 对比 canonical 与 serving 版本
- [ ] 确认 `[EMAIL_REDACTED]`、`[PHONE_REDACTED]` 等占位符已正确替换
- [ ] 检查是否有漏网的敏感信息

## 配置说明

### masking_rules.yaml 结构

```
version: 2
field_classification:    # 全局字段分级（A/B/C）
level_defaults:          # 每级默认的 canonical/serving 动作
tokenizer:               # hash/token 算法和盐值配置
sources:                 # 每个数据源的列级规则
  {source_name}:
    file_patterns: [...]
    column_rules:
      {column}: { level, canonical_action, serving_action, ... }
unstructured:            # 非结构化正则模式
  patterns: [...]
```

### DRI 列处理规则

| 视图 | 默认动作 | 可配置选项 |
|---|---|---|
| Internal Canonical | `tokenize` | `drop` |
| External Serving | `drop` | — |

DRI 列按整列处理，不做人名 pattern 匹配。在 `column_rules` 中配置 `canonical_action` 即可切换。

## 代码模块说明

| 模块 | 职责 |
|---|---|
| `services/ingestion/field_actions.py` | 原子脱敏动作：redact, hash, tokenize, generalize, drop, passthrough |
| `services/ingestion/masking_engine.py` | 规则加载、列级规则解析、行级脱敏编排 |
| `services/ingestion/manifest.py` | Dataset manifest 生成 |
| `services/ingestion/lineage.py` | 逐行审计日志（JSONL） |
| `services/ingestion/unstructured.py` | MinerU 输出的正则脱敏 |
| `scripts/ingest/run_mask_structured.py` | 结构化脱敏入口 |
| `scripts/ingest/run_mask_unstructured.py` | 非结构化脱敏入口 |
| `scripts/ingest/preview_masking.py` | 预览 / 审计工具 |

## 后续待实现

- [ ] `run_mask_structured.py` 完整 I/O 实现
- [ ] `run_mask_unstructured.py` 完整 I/O 实现
- [ ] `preview_masking.py` 的 preview 和 audit 子命令实现
- [ ] Vendor 名称泛化映射表（B 级 generalize to_type）
- [ ] Line 名称泛化映射表
- [ ] `.env.example` 添加 `FAULTDX_MASKING_SALT` 条目
