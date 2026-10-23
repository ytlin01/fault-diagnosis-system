# Unstructured Ingestion, VLM, and Masking Plan

This document is the current operating guide for TASK-006A and TASK-006. Detailed execution history stays in task notes; this file keeps the overall design, masking rules, directory boundaries, and Local/E3 command set.

## Scope

TASK-006A owns document ingestion and VLM enrichment. It produces internal canonical views only.

TASK-006 owns masking, serving view generation, manifests, and lineage. It consumes TASK-006A outputs and does not parse raw documents.

The pipeline follows this order:

```text
raw document or MinerU output
  -> base canonical
  -> optional VLM-enriched canonical
  -> masked canonical
  -> serving view
```

The pipeline must not copy reference repo code, commit raw sensitive documents, or send raw/unmasked data to unapproved external services.

## Directory Map

Each directory represents a different governance state.

| Directory | Owner | Purpose |
| --- | --- | --- |
| `data/raw/unstructured_input/` | TASK-006A input | Local raw Office/PDF/MinerU input. May contain sensitive data. Never commit. |
| `data/processed/unstructured/` | TASK-006A | Base internal canonical JSON, without VLM response text. |
| `data/processed/unstructured_assets/` | TASK-006A | Extracted Office images used by VLM asset resolution. |
| `data/processed/unstructured_vlm/` | TASK-006A | Internal VLM-enriched canonical JSON. Not serving-safe. |
| `data/processed/unstructured_masked/` | TASK-006 | Masked canonical output for non-VLM inputs. |
| `data/processed/unstructured_masked_vlm/` | TASK-006 | Masked canonical output for VLM-enriched inputs. |
| `data/serving_unstructured/` | TASK-006 | Serving view for non-VLM inputs. |
| `data/serving_unstructured_vlm/` | TASK-006 | Route B external serving source. Keeps serving-safe text/table content and serving-safe image-derived `vlm_text` blocks only. |
| `data/processed/_manifests/` | TASK-006 | Run manifests. |
| `data/processed/_lineage/` | TASK-006 | Pattern and policy lineage logs. |

Recommended VLM flow:

```text
data/raw/unstructured_input
  -> data/processed/unstructured
  -> data/processed/unstructured_vlm
  -> data/processed/unstructured_masked_vlm
  -> data/serving_unstructured_vlm
```

Recommended non-VLM flow:

```text
data/processed/unstructured
  -> data/processed/unstructured_masked
  -> data/serving_unstructured
```

## Canonical Model

The current schema is `unstructured_canonical_v1`.

Core block types:

- `text`
- `table`
- `image`
- `figure-chart`
- `asset-placeholder`

Important block fields:

- `block_id`, `block_index`, `block_type`
- `source_anchor`
- `parser`
- `sensitivity_hint`
- `serving_eligible`
- `retrieval_eligible`
- `graph_eligible`
- `needs_review`
- `text`
- `table`
- `enrichment.local_vlm`

DOCX/PPTX are parsed with lightweight native extraction. PDFs should go through MinerU first. MinerU table source images are preserved as asset references for later VLM enrichment, not as reviewed business facts.

`name_mapping.xlsx` is applied after reading and before masking. For unstructured text it defaults to contains-style matching because aliases usually appear inside longer paragraphs.

## Local VLM Boundary

Local VLM enrichment is metadata augmentation only.

It may add information under:

```text
enrichment.local_vlm
```

It must not:

- overwrite base OCR/parser text
- directly create final `Phenomenon` or `MappingRecord`
- become serving content without masking and review
- call a non-local endpoint unless the input has been approved and de-identified

Default VLM output keeps:

- `response_text`
- `response_metrics`

Default VLM output does not keep:

- `raw_response.context`
- full raw Ollama response

Use `--include-raw-response` only for deliberate local debugging and keep those outputs out of serving paths.

## Masking Rules

Unstructured regex patterns live in:

```text
configs/masking_rules.yaml
```

Current unstructured pattern rules:

| Pattern | Action | Notes |
| --- | --- | --- |
| `email` | redact | Replaces with `[EMAIL_REDACTED]`. |
| `phone_cn` | redact | Replaces with `[PHONE_REDACTED]`. |
| `phone_intl` | redact | Replaces with `[PHONE_REDACTED]`. |
| `device_serial` | hash | Uses `FAULTDX_MASKING_SALT`; broad pattern, review false positives. |
| `employee_id` | redact | Replaces with `[ID_REDACTED]`; review false positives against equipment codes. |

`FAULTDX_MASKING_SALT` is required when any hash/token action is active. `run_mask_unstructured.py` loads repo-root `.env` like structured masking; shell environment variables take precedence over `.env`.

Masked canonical keeps internal review value:

- masked block `text`
- masked `table.html`
- masked `enrichment.local_vlm.response_text`
- `response_metrics`
- block/page metadata

Masked canonical removes debug/local-only fields:

- `raw_response`
- `resolved_image_path`

Serving view is stricter. It keeps only serving-safe content and removes raw asset, local path, endpoint, and raw VLM response fields:

- `asset_ref`
- `asset_local_path`
- `asset_source_path`
- `asset_sha256`
- `image_ref`
- `image_path`
- `resolved_image_path`
- `table_image_ref`
- `raw_response`
- `response_text`
- `response_metrics`
- `endpoint`

Serving may keep compact VLM status metadata such as `candidate`, `executed`, `status`, `reason`, `metadata_only`, and `prompt_contract`.

For visual blocks, Route B uses a derived serving-safe representation:

- raw `image` / `figure-chart` blocks do not pass through as serving assets
- if masked OCR-like text or masked `enrichment.local_vlm.response_text` is available, TASK-006 emits a derived `block_type: "vlm_text"` block
- the derived block keeps text evidence plus safe provenance such as `derived_from_block_id`, `derived_from_block_type`, and source anchors
- the derived block may keep compact VLM status metadata, but not raw response bodies, metrics blobs, endpoints, local paths, or image asset refs

This makes `data/serving_unstructured_vlm/` the only Route B external source for image-derived document evidence. `data/processed/unstructured_masked_vlm/` remains internal review material.

## Configuration Files

Masking config:

```text
configs/masking_rules.yaml
```

Local VLM runtime config:

```text
configs/local_vlm.yaml
```

Current profiles:

- `e2a`: small local validation, default model `qwen2.5vl:7b`, limit `3`
- `e3`: larger local batch run, default model `qwen2.5vl:32b`, limit `0` for all targets

Before moving to E3, review and edit `configs/local_vlm.yaml` if the E3 machine differs:

```yaml
profiles:
  e3:
    model: qwen2.5vl:32b
    endpoint: http://localhost:11434
    ollama_models_dir: null
    startup_command: ollama serve
    output_dir: data/processed/unstructured_vlm
    asset_roots:
      - data/processed/unstructured_assets
      - data/raw/unstructured_input/mineru_output
      - data/raw/unstructured_input
    limit: 0
    timeout_seconds: 300
    existing_text_limit: 1200
    allow_non_local_endpoint: false
```

If E3 uses a specific Ollama model directory, set `profiles.e3.ollama_models_dir` for run reporting, and set Ollama's own `OLLAMA_MODELS` environment variable before starting Ollama. E3 is an Ubuntu machine, so use bash:

```bash
export OLLAMA_MODELS=/data/ollama/models
ollama serve
```

`FAULTDX_OLLAMA_MODELS_DIR` may also be set if you want the Python script's runtime report to show the same model directory, but it does not start or configure Ollama by itself.

If the model name differs on E3, change `profiles.e3.model` or pass `--model`.

Do not set `allow_non_local_endpoint: true` unless the endpoint is approved and the inputs are safe for that endpoint.

## Command Set: Local E2a

Run all commands from the repo root.

Preview ingestion:

```powershell
python scripts\ingest\run_ingest_unstructured.py --synthetic --dry-run
```

Regenerate base canonical and Office image assets:

```powershell
python scripts\ingest\run_ingest_unstructured.py --input-dir data\raw\unstructured_input --output-dir data\processed\unstructured --asset-output-dir data\processed\unstructured_assets --apply-name-mapping --name-mapping-file data\raw\name_mapping.xlsx
```

Dry-run E2a VLM target resolution:

```powershell
python scripts\ingest\run_enrich_unstructured_vlm.py --profile e2a --input-dir data\processed\unstructured --dry-run --limit 3
```

Run a small E2a VLM sample:

```powershell
python scripts\ingest\run_enrich_unstructured_vlm.py --profile e2a --input-dir data\processed\unstructured --limit 3 --force
```

Dry-run masking for VLM outputs:

```powershell
python scripts\ingest\run_mask_unstructured.py --input-dir data\processed\unstructured_vlm --dry-run
```

Write masked canonical and serving outputs for VLM outputs:

```powershell
python scripts\ingest\run_mask_unstructured.py --input-dir data\processed\unstructured_vlm
```

Expected outputs:

```text
data/processed/unstructured_masked_vlm/
data/serving_unstructured_vlm/
data/processed/_manifests/
data/processed/_lineage/
```

## Command Set: E3 Ubuntu VLM Enrichment

E3 is Ubuntu/Linux and may not have a code agent, so use this checklist directly. Use bash commands, not PowerShell.

1. Confirm `configs/local_vlm.yaml` E3 settings.

Check at least:

- `profiles.e3.model`
- `profiles.e3.endpoint`
- `profiles.e3.ollama_models_dir`
- `profiles.e3.asset_roots`
- `profiles.e3.limit`
- `profiles.e3.timeout_seconds`

2. Start Ollama on E3.

If the config says `startup_command: ollama serve`:

```bash
ollama serve
```

If E3 needs a custom model store:

```bash
export OLLAMA_MODELS=/data/ollama/models
ollama serve
```

Keep this terminal running.

Alternatively, start it in the background and write logs:

```bash
mkdir -p logs
export OLLAMA_MODELS=/data/ollama/models
nohup ollama serve > logs/ollama.log 2>&1 &
```

3. Confirm the model is available.

In a second terminal:

```bash
ollama list
```

If needed, pull the E3 model:

```bash
ollama pull qwen2.5vl:32b
```

4. Dry-run VLM target resolution.

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py --profile e3 --input-dir data/processed/unstructured --dry-run
```

5. Optional single-file smoke test.

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py --profile e3 --file data/processed/unstructured/HIVE_Error_Code_8f5115f98988_canonical.json --limit 1 --force
```

6. Run E3 batch enrichment.

```bash
python scripts/ingest/run_enrich_unstructured_vlm.py --profile e3 --input-dir data/processed/unstructured --force
```

7. Verify outputs exist.

```bash
ls -lh data/processed/unstructured_vlm
```

8. Run masking after E3 enrichment.

Dry-run:

```bash
python scripts/ingest/run_mask_unstructured.py --input-dir data/processed/unstructured_vlm --dry-run
```

Write outputs:

```bash
python scripts/ingest/run_mask_unstructured.py --input-dir data/processed/unstructured_vlm
```

9. Verify masked and serving outputs.

```bash
ls -lh data/processed/unstructured_masked_vlm
ls -lh data/serving_unstructured_vlm
```

## Cleanup Guidance

Do not delete:

- `data/processed/unstructured/`
- `data/processed/unstructured_assets/`
- `data/processed/unstructured_vlm/` if it is the latest VLM input for masking
- latest `data/processed/unstructured_masked_vlm/`
- latest `data/serving_unstructured_vlm/`

Old mixed-location outputs with these patterns are stale and can be deleted after confirming the new directories are populated:

```text
data/processed/unstructured/*_canonical_vlm_canonical.json
data/serving_unstructured/*_canonical_vlm_serving.json
```

Old experiment manifests and lineage may be deleted if a newer run has replaced them.

## Open Risks

- Regex patterns can still miss names in free text or over-mask equipment/error codes.
- VLM response text can repeat sensitive information, so it stays out of serving by default.
- Images, screenshots, QR codes, and dense tables need review before serving.
- Source filenames and anchors may still reveal project context; decide later whether serving should generalize them.
