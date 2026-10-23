# E3 Unstructured Local VLM Handoff Runbook

本文档用于把本地负责人手中的非结构化数据通过 U 盘带到 E3 Ubuntu，并在 E3 上运行 local VLM enrichment 与后续 masking / serving 生成。

核心原则：

- 不上传 raw / processed 数据到 GitHub。
- E3 只接收本次 VLM 运行所需的代码、配置、canonical 输入和本地图片资产。
- VLM enrichment 属于 TASK-006A 的 internal metadata augmentation，不直接生成最终 MappingRecord。
- VLM-aware masking 属于 TASK-006；serving 输出必须经过 masking，并默认剥离 VLM response text、asset path、image path 和 raw response。

## 1. 推荐拷贝方式

建议使用一个 U 盘 bundle 目录，例如：

```text
<USB_ROOT>/FaultDx_E3_bundle/
  FaultDx_main/
```

不要把 E3 运行包放回 `Faultdx_ref/`，也不要把 E3 输出直接写到 Git 工作区外的临时散乱目录。E3 上建议放到：

```bash
~/FaultDx_E3/FaultDx_main
```

## 2. 代码和配置需要拷什么

如果希望 E3 上可以直接跑 VLM enrichment 和后续 masking，推荐拷完整主项目代码工作树，但排除 Git 历史、虚拟环境和不相关数据。

必须包含：

```text
configs/
requirements/
scripts/
services/
docs/data/e3_unstructured_vlm_handoff.md
docs/data/unstructured_ingestion_plan.md
.env.example
AGENTS.md
HANDOFF_README.md
```

关键文件包括：

```text
configs/local_vlm.yaml
configs/masking_rules.yaml
scripts/ingest/run_enrich_unstructured_vlm.py
scripts/ingest/run_mask_unstructured.py
services/ingestion/local_vlm.py
services/ingestion/unstructured.py
services/ingestion/canonical_document.py
services/ingestion/masking_engine.py
services/ingestion/manifest.py
services/ingestion/lineage.py
```

不要拷：

```text
.git/
.venv/
__pycache__/
.env
data/raw/**        # 除本次必须的 MinerU image/table asset source 外
data/processed/**  # 除本次必须的 canonical / asset input 外
data/serving*/**   # 除非是回传结果，不作为 E3 输入
```

`.env` 不要直接从 E2a 或负责人机器复制到 E3。E3 应单独创建自己的 `.env`，尤其是 `FAULTDX_MASKING_SALT`。

## 3. 本次 VLM 必须拷的数据

### 3.1 Base canonical JSON

VLM enrichment 的主要输入是 TASK-006A 已生成的 canonical JSON：

```text
data/processed/unstructured/*.json
```

这些文件是 base internal canonical layer，不是 serving 输出。

### 3.2 Office embedded image assets

如果 DOCX / PPTX canonical 中有 Office 图片块，必须同时拷：

```text
data/processed/unstructured_assets/
```

否则 E3 上只能看到 image block metadata，无法解析实际图片。

### 3.3 MinerU table / image assets

如果 PDF / MinerU canonical 中有 `table_image_ref` 或 MinerU 图片引用，必须同时拷：

```text
data/raw/unstructured_input/mineru_output/
```

这是当前 `configs/local_vlm.yaml` 默认 asset root 之一。虽然它位于 `data/raw/` 下，但这里是 E3 本地 VLM 解析所需的本地图片资产，仍然不能上传 GitHub，也不能发送外部 API。

### 3.4 可选：原始 Office / PDF 文件

只有当 E3 需要重新 ingestion 时，才拷：

```text
data/raw/unstructured_input/
```

如果 E3 只做 VLM enrichment，不需要重新解析 DOCX / PPTX / PDF，则不要拷全量 raw 原文件。

## 4. E2a / 负责人机器打包命令示例

以下命令在当前主项目根目录运行。注意：本节是 **打包端** 命令；如果数据负责人本机是 Windows，可以用 PowerShell / robocopy。E3 Ubuntu 上的接收和运行命令从第 5 节开始，使用 bash。

### 4.1 创建代码包

```powershell
$bundle = "E:\FaultDx_E3_bundle\FaultDx_main"
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

robocopy configs $bundle\configs /E
robocopy requirements $bundle\requirements /E
robocopy scripts $bundle\scripts /E /XD __pycache__
robocopy services $bundle\services /E /XD __pycache__
robocopy docs\data $bundle\docs\data /E

Copy-Item AGENTS.md $bundle\
Copy-Item HANDOFF_README.md $bundle\
Copy-Item .env.example $bundle\
```

这组命令显式拷贝运行所需代码和文档，避免用 `robocopy .` 时把 `.git`、`.env`、本地数据或无关目录一起带走。

### 4.2 拷贝 VLM 输入数据

```powershell
robocopy data\processed\unstructured $bundle\data\processed\unstructured *.json /E
robocopy data\processed\unstructured_assets $bundle\data\processed\unstructured_assets /E
robocopy data\raw\unstructured_input\mineru_output $bundle\data\raw\unstructured_input\mineru_output /E
```

如果需要续跑已有 VLM 输出，也可带上：

```powershell
robocopy data\processed\unstructured_vlm $bundle\data\processed\unstructured_vlm *.json /E
```

不要默认拷贝旧的 masked / serving 输出。E3 跑完后应重新生成并回传。

## 5. E3 Ubuntu 接收与环境准备

### 5.0 从 U 盘复制到 E3

先确认 U 盘挂载位置。常见路径类似：

```bash
lsblk
ls /media/$USER
```

假设 U 盘挂载为 `/media/$USER/FAULTDX_USB`：

```bash
mkdir -p ~/FaultDx_E3
rsync -avh --progress \
  /media/$USER/FAULTDX_USB/FaultDx_E3_bundle/FaultDx_main/ \
  ~/FaultDx_E3/FaultDx_main/
```

进入项目目录：

```bash
cd ~/FaultDx_E3/FaultDx_main
```

### 5.1 Python 环境

E3 建议使用 Python 3.11。

```bash
cd ~/FaultDx_E3/FaultDx_main
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

VLM enrichment / masking 的最小依赖：

```bash
pip install pyyaml python-dotenv pydantic httpx
```

如果 E3 也要跑更多项目模块，再安装完整基础依赖：

```bash
pip install -r requirements/base.txt
```

注意：`requirements/base.txt` 包含 GraphRAG 等较重依赖；只跑 unstructured VLM / masking 时不建议优先安装全量依赖。

### 5.2 Ollama 和模型

确认 E3 已安装 Ollama：

```bash
ollama --version
ollama list
```

推荐 E3 profile 使用：

```text
qwen2.5vl:32b
```

如果 E3 不能联网，需要提前通过批准方式把 Ollama 模型文件带到 E3 的模型目录。

如果 E3 的模型目录不是默认位置，启动 Ollama 前设置。示例：

```bash
export OLLAMA_MODELS=/data/ollama/models
ollama serve
```

如果想后台启动并写日志：

```bash
mkdir -p logs
export OLLAMA_MODELS=/data/ollama/models
nohup ollama serve > logs/ollama.log 2>&1 &
```

`configs/local_vlm.yaml` 中的 `e3.ollama_models_dir` 当前为 `null`。如果 E3 有固定模型目录，可在 E3 本地改为对应路径，或通过环境变量记录：

```bash
export FAULTDX_OLLAMA_MODELS_DIR=/data/ollama/models
```

`FAULTDX_OLLAMA_MODELS_DIR` 主要用于运行记录和 dry-run metadata；真正影响 Ollama 读取模型的是启动 Ollama 时的 `OLLAMA_MODELS`。

## 6. E3 上的运行顺序

### 6.1 先做 dry-run

dry-run 不调用模型，只解析目标图片是否能找到。

```bash
cd ~/FaultDx_E3/FaultDx_main
source .venv/bin/activate

python scripts/ingest/run_enrich_unstructured_vlm.py \
  --profile e3 \
  --input-dir data/processed/unstructured \
  --dry-run \
  --limit 3
```

检查输出：

- `profile` 应为 `e3`
- `model` 应为 `qwen2.5vl:32b`
- `target_count` 应大于 0
- 每个 target 的 `resolved_image_path` 应该不是 `null`

如果 `resolved_image_path = null`，优先检查 U 盘是否漏拷了：

```text
data/processed/unstructured_assets/
data/raw/unstructured_input/mineru_output/
```

### 6.2 小样本真实运行

先跑 1 个 target，确认模型、速度和输出质量：

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py \
  --profile e3 \
  --input-dir data/processed/unstructured \
  --limit 1
```

默认输出目录：

```text
data/processed/unstructured_vlm/
```

### 6.3 全量运行

确认小样本质量后再全量：

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py \
  --profile e3 \
  --input-dir data/processed/unstructured
```

`configs/local_vlm.yaml` 中 E3 profile 的 `limit = 0`，表示不限制 target 数量。

如果要重跑已经执行过的 blocks，使用：

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py \
  --profile e3 \
  --input-dir data/processed/unstructured \
  --force
```

不要默认使用 `--include-raw-response`。该选项会保留 Ollama 原始响应，可能包含很大的 `context` token 数组，只用于 debug，不应进入常规交接输出。

## 7. E3 上运行 masking / serving

VLM enrichment 生成的是 internal canonical，不是 serving-safe 输出。继续运行 TASK-006 masking。

### 7.1 设置 E3 本地 masking salt

```bash
export FAULTDX_MASKING_SALT="replace-with-e3-local-secret"
```

也可以在 E3 本地 `.env` 中写入，但不要把 `.env` 带回 Git 或 U 盘公共目录。

### 7.2 dry-run masking

```bash
python scripts/ingest/run_mask_unstructured.py \
  --input-dir data/processed/unstructured_vlm \
  --dry-run
```

dry-run 中重点看：

- `canonical_policy`
- `serving_policy`
- 是否有异常多的 regex hits
- serving 是否移除 image / asset path 和 VLM response content

### 7.3 正式 masking

```bash
python scripts/ingest/run_mask_unstructured.py \
  --input-dir data/processed/unstructured_vlm
```

默认输出：

```text
data/processed/unstructured_masked_vlm/
data/serving_unstructured_vlm/
data/processed/_manifests/
data/processed/_lineage/
```

## 8. E3 输出需要回传什么

建议从 E3 拷回：

```text
data/processed/unstructured_vlm/
data/processed/unstructured_masked_vlm/
data/serving_unstructured_vlm/
data/processed/_manifests/
data/processed/_lineage/
```

不要回传：

```text
.env
.venv
raw unrelated source files
Ollama model files
debug outputs with --include-raw-response
```

如果 U 盘容量有限，优先回传：

```text
data/serving_unstructured_vlm/
data/processed/unstructured_masked_vlm/
data/processed/_manifests/
data/processed/_lineage/
```

`data/processed/unstructured_vlm/` 可作为内部审查材料回传，但不要把它当作 serving 输出。

## 9. 快速质量检查

### 9.1 检查 VLM 输出是否存在

```bash
find data/processed/unstructured_vlm -maxdepth 1 -name '*.json' -type f
```

### 9.2 检查是否误保留 raw_response

默认不应出现 `raw_response`：

```bash
grep -R --line-number '"raw_response"' data/processed/unstructured_vlm/*.json
```

如果有匹配，确认是否误用了 `--include-raw-response`。

### 9.3 检查 serving 是否暴露本地路径或 VLM response

```bash
grep -R --line-number -E 'resolved_image_path|asset_local_path|image_path|response_text|raw_response' \
  data/serving_unstructured_vlm/*.json
```

正常情况下不应有匹配。

### 9.4 检查 manifests / lineage

```bash
ls -lt data/processed/_manifests | head
ls -lt data/processed/_lineage | head
```

## 10. 常见问题

### dry-run 有 target，但正式运行报 connection refused

Ollama 没启动，或 endpoint 不对。

检查：

```bash
ollama list
ollama serve
```

默认 endpoint 是：

```text
http://localhost:11434
```

### target_count = 0

可能原因：

- canonical JSON 没有 image/table/figure-chart block
- VLM candidate 标记不存在
- image refs 没有被解析
- input-dir 指错目录

先确认：

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py --profile e3 --input-dir data/processed/unstructured --dry-run --limit 10
```

### resolved_image_path = null

通常是漏拷资产目录。检查：

```text
data/processed/unstructured_assets/
data/raw/unstructured_input/mineru_output/
```

### masking 因 salt 缺失失败

这是预期 fail-safe。设置：

```bash
export FAULTDX_MASKING_SALT="replace-with-e3-local-secret"
```

### 输出太大

不要使用 `--include-raw-response`。如果已经生成了 debug 输出，重新运行不带该参数，并只回传正常输出。

## 11. 最小交接检查表

E2a / 数据负责人出发前：

- [ ] 已拷 code/config bundle。
- [ ] 已拷 `data/processed/unstructured/*.json`。
- [ ] 已拷 `data/processed/unstructured_assets/`。
- [ ] 已拷 `data/raw/unstructured_input/mineru_output/`。
- [ ] 未拷 `.env`。
- [ ] 未拷不相关 raw 数据。

E3 运行前：

- [ ] Python 3.11 可用。
- [ ] 最小 Python 依赖已安装。
- [ ] Ollama 可用。
- [ ] `qwen2.5vl:32b` 可用。
- [ ] dry-run target 能解析到本地图片路径。

E3 回传前：

- [ ] VLM enrichment 已完成。
- [ ] Masking dry-run 已检查。
- [ ] Formal masking 已生成 masked canonical 和 serving。
- [ ] serving 输出中没有 local image path、asset path、raw response 或 response_text。
- [ ] manifests / lineage 已一并回传。
