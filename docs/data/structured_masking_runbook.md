# FaultDx Phase 1 — Structured Masking Runbook

## 概览

本文档覆盖结构化数据（Excel / CSV）的脱敏流程。

**处理对象**：Y25 Downtime、Error Code 表、FAT/SAT Checklist、Troubleshooting SOP 等。

**产出三视图**：

| 视图 | 目录 | 用途 |
|---|---|---|
| Raw | `data/raw/` | 仅脱敏脚本读取，不入 Git |
| Internal Canonical | `data/processed/` | 本地图谱、检索、Ollama 评估 |
| External Serving | `data/serving_structured/` | API、UI、DeepSearch、网络侧 LLM |

---

## 前置条件

1. **设置 masking salt**（必须）：
   ```
   # .env 中添加
   FAULTDX_MASKING_SALT=your-random-secret-string
   ```

2. **原始数据就位**：`data/raw/` 下放入原始 xlsx/csv 文件

3. **依赖安装**：
   ```
   uv pip install pyyaml openpyxl
   ```

---

## 协作约定

- `FAULTDX_MASKING_SALT` 只保存在本地 `.env`、CI secret 或受控密钥管理中，不进入 Git。
- `data/raw/` 与真实 `.env` 不作为协作产物提交；它们只留在受控环境。
- 结构化 masking 默认由少数受控成员或受控流水线统一执行，而不是要求所有协作者重复运行。
- 统一执行后，应提交可共享产物：
  - `data/processed/`
  - `data/serving_structured/`
  - `data/processed/_manifests/`
  - `data/processed/_lineage/`
- 其他团队成员默认直接消费上述产物，不需要再次运行 masking 脚本，除非他负责规则开发或数据流水线维护。
- `data/processed/` 仍属于内部视图，权限不应等同于 `data/serving_structured/`。
- 如需跨人、跨机器保持 token 稳定，必须使用同一份受控 salt。

---

## 运行步骤

### Step 0: 列出可用数据源

```powershell
# PowerShell
.\scripts\ingest\run_structured_masking.ps1 -ListSources

# 或 Python
python scripts/ingest/run_mask_structured.py --list-sources
```

### Step 1: 查看规则解析（无需数据）

```powershell
.\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -RulesOnly
```

输出每列的分级 (A/B/C)、canonical 动作、serving 动作、review 标记。同时显示 column_aliases 配置。

### Step 1.5: ?????????mapping-before-masking?

????? `data/raw/name_mapping.xlsx`????? masking ??????????????? mapping?

```powershell
# ??? dry-run + ??????
.\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -DryRun -ApplyNameMapping

# ????? mapping ??
python scripts/ingest/run_mask_structured.py --source y25_downtime --dry-run --apply-name-mapping --name-mapping-file data/raw/name_mapping.xlsx
```

`name_mapping.xlsx` ????????? Git????????
- `raw_name`
- `mapped_name`
- `scope`??? `filename,sheetname,content` ??????????
- `match_mode`?`exact` / `contains`?
- `enabled`
- `note`

?? `content` ???????????????????? `masking_rules.yaml` ?? source ????? `name_mapping.content_columns`?

### Step 2: Dry-run 预览（需要数据）

```powershell
# 预览前 5 行
.\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -DryRun

# 预览前 10 行
.\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime -DryRun -Rows 10
```

**Dry-run 输出两部分**：

**A) Header Normalization Report**：
- 每个原始表头 → 规范化结果 → 规则匹配
- 未匹配列（文件中有但规则中没有）
- 未使用规则（规则中有但文件中没有）

**B) Data Preview**：
- 前 N 行的 Raw → Canonical → Serving 对比
- 标注每列的分级和动作

### Step 3: 正式运行

```powershell
.\scripts\ingest\run_structured_masking.ps1 -Source y25_downtime
```

---

## Header Normalization 说明

真实 Excel 表头可能存在不一致，pipeline 自动处理：

| 问题 | 处理 |
|---|---|
| 全角括号 `（）` | 转半角 `()` |
| 全角空格 `　` | 转半角空格 |
| 多余前后空格 | strip |
| 内嵌换行 `\n` | 删除 |
| 连续空格 | 合并为单个 |
| NFKC 兼容形式 | 统一 |

如果规范化后仍无法匹配规则，可在 `masking_rules.yaml` 的 `column_aliases` 中添加变体：

```yaml
column_aliases:
  "異常分類":          # 规则中的规范名
    - "异常分类"       # 简体变体
    - "异常分類"       # 混合变体
```

### 首次运行建议

1. 先 dry-run 查看 Header Report
2. 检查 "Unmatched columns" 和 "Unused rules"
3. 在 `column_aliases` 中补充缺失的映射
4. 再次 dry-run 确认全部匹配
5. 正式运行

---

## 脱敏动作说明

| 动作 | 含义 | 示例 |
|---|---|---|
| `passthrough` / `keep` | 原样保留 | `"CG-ST01"` → `"CG-ST01"` |
| `drop` | 删除整列 | `"张三"` → (列不出现) |
| `redact` | 替换为占位符 | `"张三"` → `"[REDACTED]"` |
| `tokenize` | 确定性伪名化 | `"张三"` → `"TOK_a1b2c3d4e5f6"` |
| `hash` | 单向哈希 | `"SN123456"` → `"HASH_c3d4e5f6a1b2"` |
| `mask` | 部分遮盖 | `"张三丰"` → `"张**"` |
| `rename` | 输出时重命名列 | 列名 `"異常描敘"` → `"description"` |
| `generalize` | 泛化 | `"2025-09-04"` → `"2025-09"` |

---

## Sheet 选择

`sheet_selector` 配置支持四种模式：

```yaml
sheet_selector:
  mode: index            # 固定 sheet 序号（0-based）
  value: 0

sheet_selector:
  mode: name             # 固定 sheet 名称
  value: "Sheet1"

sheet_selector:
  mode: station_match    # 匹配包含工站名的 sheet
  value: "CG"

sheet_selector:
  mode: interactive      # 运行时列出所有 sheet，手动选择
```

---

## 输出目录

```
data/
├── processed/
│   ├── y25_downtime_canonical.json
│   ├── error_codes_standardized_canonical.json
│   ├── _manifests/
│   │   └── y25_downtime_manifest_20260325T143000.json
│   └── _lineage/
│       └── y25_downtime_lineage_20260325T143000.jsonl
├── serving_structured/
│   ├── y25_downtime_serving.json
│   └── error_codes_standardized_serving.json
└── eval/
    └── troubleshooting_sop_serving.json
```

---

## 人工核验清单

### A. Header 检查（dry-run 阶段）
- [ ] 所有列都已匹配规则（无 "Unmatched columns"）
- [ ] 无多余的 "Unused rules"（或已确认文件中确实没有该列）
- [ ] alias 匹配合理

### B. Manifest 检查（正式运行后）
- [ ] `input.row_count == output.canonical.row_count`（行数一致）
- [ ] `review_flag_columns` 列表合理
- [ ] `header_normalization` 中的映射正确

### C. Lineage 抽检
- [ ] 随机抽查 10 行 JSONL
- [ ] A 级字段 canonical=tokenize, serving=drop
- [ ] B 级字段 serving=generalize 或 drop
- [ ] C 级字段全部 passthrough

### D. Serving 安全审计
```powershell
python scripts/ingest/preview_masking.py audit --scan-dir data/serving_structured
```
- [ ] 无邮箱、电话、工号残留
- [ ] DRI 列不存在于 serving 输出

---

## 支持的数据源

| Source Name | 文件 | 特征 |
|---|---|---|
| `y25_downtime` | Val CG DT*.xlsx | 17 列，含 DRI |
| `error_codes_standardized` | CG Error list*.xlsx | 4 列，纯 C 级 |
| `error_codes_raw` | CG Error code.xlsx | 6 列，纯 C 级 |
| `fat_sat_checklist` | CG FAT SAT Check list*.xlsx | 5 列，issue 需 review |
| `troubleshooting_sop` | *Troubleshooting SOP* | 7 列，输出到 eval/ |

