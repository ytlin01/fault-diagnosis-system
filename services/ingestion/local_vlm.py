"""Local VLM enrichment helpers for unstructured canonical documents.

This layer is intentionally a post-ingestion metadata augmentation step. It
does not rewrite canonical text or create final MappingRecord facts.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_LOCAL_VLM_PROMPT = """你是 FaultDx 的本地视觉解析助手。请只基于图片内容和给定上下文做结构化观察，不要推断成最终业务结论。

本步骤是 metadata augmentation only，不创建最终 MappingRecord，不覆盖原始 OCR/解析文本。

请用中文输出简短 JSON，字段包括：
- image_summary: 图片/表格的整体内容
- extracted_text: 能可靠读出的关键文字、错误码、表头或标注
- candidate_entities: 可能有用的设备、工站、错误码、动作、部件名称
- uncertainty: 看不清或不确定的内容
- review_notes: 给人工复核或后续 MappingRecord 候选生成的建议

如果图片中文字过小、表格跨列复杂或 OCR 不稳定，请明确写入 uncertainty。"""


@dataclass(frozen=True)
class LocalVlmTarget:
    block_id: str
    block_index: int
    block_type: str
    image_ref: str
    image_rel_path: str
    resolved_image_path: str | None
    source_file: str | None
    page: int | None
    existing_text_preview: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class OllamaLocalVlmClient:
    """Small standard-library Ollama client for local-only VLM calls."""

    def __init__(
        self,
        *,
        model: str,
        endpoint: str = "http://localhost:11434",
        timeout_seconds: int = 120,
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, *, image_path: Path, prompt: str) -> dict[str, Any]:
        image_bytes = image_path.read_bytes()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [base64.b64encode(image_bytes).decode("ascii")],
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"local VLM request failed: {exc}") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        parsed = json.loads(raw)
        return {
            "provider": "ollama",
            "model": self.model,
            "endpoint": self.endpoint,
            "duration_ms": elapsed_ms,
            "response": parsed.get("response", ""),
            "raw": parsed,
        }


def collect_local_vlm_targets(
    document: dict[str, Any],
    *,
    asset_roots: list[Path],
    limit: int | None = None,
    force: bool = False,
) -> list[LocalVlmTarget]:
    """Collect image/table blocks that can be sent to local VLM enrichment."""
    targets: list[LocalVlmTarget] = []
    for block in document.get("blocks", []):
        local_vlm = block.get("enrichment", {}).get("local_vlm", {})
        has_candidate_flag = local_vlm.get("candidate") is True
        if not has_candidate_flag and not _block_has_image_ref(block):
            continue
        if local_vlm.get("executed") is True and not force:
            continue

        image_ref = _first_image_ref(block)
        if not image_ref:
            continue
        image_rel_path = _image_ref_to_rel_path(image_ref)
        resolved_path = resolve_local_image_path(
            document,
            block,
            image_ref=image_ref,
            asset_roots=asset_roots,
        )
        anchor = block.get("source_anchor", {})
        target = LocalVlmTarget(
            block_id=str(block.get("block_id", "")),
            block_index=int(block.get("block_index", -1)),
            block_type=str(block.get("block_type", "")),
            image_ref=image_ref,
            image_rel_path=image_rel_path,
            resolved_image_path=str(resolved_path) if resolved_path else None,
            source_file=anchor.get("source_file") or document.get("source", {}).get("file"),
            page=anchor.get("page"),
            existing_text_preview=str(block.get("text", ""))[:500],
        )
        targets.append(target)
        if limit is not None and len(targets) >= limit:
            break
    return targets


def enrich_document_with_local_vlm(
    document: dict[str, Any],
    *,
    client: OllamaLocalVlmClient,
    asset_roots: list[Path],
    prompt_template: str = DEFAULT_LOCAL_VLM_PROMPT,
    limit: int | None = None,
    force: bool = False,
    existing_text_limit: int = 1200,
    include_raw_response: bool = False,
) -> dict[str, Any]:
    """Run local VLM on eligible blocks and attach metadata results in-place."""
    targets = collect_local_vlm_targets(
        document,
        asset_roots=asset_roots,
        limit=limit,
        force=force,
    )
    by_block_id = {block.get("block_id"): block for block in document.get("blocks", [])}
    run_summary = {
        "provider": "ollama",
        "model": client.model,
        "endpoint": client.endpoint,
        "targets_found": len(targets),
        "executed": 0,
        "skipped_missing_image": 0,
        "errors": 0,
        "metadata_only": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    for target in targets:
        block = by_block_id.get(target.block_id)
        if not isinstance(block, dict):
            continue
        local_vlm = block.setdefault("enrichment", {}).setdefault("local_vlm", {})
        local_vlm.update({
            "candidate": True,
            "metadata_only": True,
            "image_ref": target.image_ref,
            "resolved_image_path": target.resolved_image_path,
        })
        if not target.resolved_image_path:
            local_vlm.update({
                "executed": False,
                "status": "skipped_missing_image",
                "reason": "Image file could not be resolved from canonical asset refs and configured asset roots.",
            })
            run_summary["skipped_missing_image"] += 1
            continue

        prompt = build_local_vlm_prompt(
            block,
            base_prompt=prompt_template,
            existing_text_limit=existing_text_limit,
        )
        try:
            result = client.generate(image_path=Path(target.resolved_image_path), prompt=prompt)
        except Exception as exc:  # pragma: no cover - network/model failures are environment-specific.
            local_vlm.update({
                "executed": False,
                "status": "error",
                "error": str(exc),
                "attempted_at": datetime.now(timezone.utc).isoformat(),
            })
            run_summary["errors"] += 1
            continue

        local_vlm.update({
            "executed": True,
            "status": "ok",
            "provider": result["provider"],
            "model": result["model"],
            "endpoint": result["endpoint"],
            "duration_ms": result["duration_ms"],
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "prompt_contract": "metadata augmentation only; not final MappingRecord",
            "response_text": result["response"],
            "response_metrics": _ollama_response_metrics(result["raw"]),
        })
        if include_raw_response:
            local_vlm["raw_response"] = result["raw"]
        else:
            local_vlm.pop("raw_response", None)
        run_summary["executed"] += 1

    document.setdefault("normalization", {}).setdefault("local_vlm", {}).update(run_summary)
    return document


def _ollama_response_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "done": raw.get("done"),
        "done_reason": raw.get("done_reason"),
        "total_duration": raw.get("total_duration"),
        "load_duration": raw.get("load_duration"),
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "prompt_eval_duration": raw.get("prompt_eval_duration"),
        "eval_count": raw.get("eval_count"),
        "eval_duration": raw.get("eval_duration"),
    }


def build_local_vlm_prompt(
    block: dict[str, Any],
    *,
    base_prompt: str = DEFAULT_LOCAL_VLM_PROMPT,
    existing_text_limit: int = 1200,
) -> str:
    anchor = block.get("source_anchor", {})
    context = {
        "block_id": block.get("block_id"),
        "block_type": block.get("block_type"),
        "page": anchor.get("page"),
        "source_file": anchor.get("source_file"),
        "existing_extracted_text": str(block.get("text", ""))[:existing_text_limit],
        "table_caption": block.get("table", {}).get("caption") if isinstance(block.get("table"), dict) else None,
    }
    return f"{base_prompt}\n\n上下文 JSON：\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def resolve_local_image_path(
    document: dict[str, Any],
    block: dict[str, Any],
    *,
    image_ref: str,
    asset_roots: list[Path],
) -> Path | None:
    rel_path = _image_ref_to_rel_path(image_ref)
    source_file = (
        block.get("source_anchor", {}).get("source_file")
        or document.get("source", {}).get("file")
        or ""
    )
    source_parent = _source_parent(source_file)
    candidate_rels = _candidate_relative_paths(rel_path, source_parent)

    direct = Path(rel_path)
    if direct.is_absolute() and direct.is_file():
        return direct

    candidates: list[Path] = []
    for root in asset_roots:
        root = root.resolve()
        for candidate_rel in candidate_rels:
            candidates.append(root / Path(candidate_rel))

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _block_has_image_ref(block: dict[str, Any]) -> bool:
    return _first_image_ref(block) is not None


def _first_image_ref(block: dict[str, Any]) -> str | None:
    refs: list[Any] = [
        block.get("table_image_ref"),
        block.get("image_path"),
        block.get("asset_ref"),
    ]
    table = block.get("table")
    if isinstance(table, dict):
        refs.extend([table.get("image_path"), table.get("image_ref")])
    for ref in refs:
        if isinstance(ref, str) and _looks_like_image_ref(ref):
            return ref.strip()
    return None


def _looks_like_image_ref(value: str) -> bool:
    rel_path = _image_ref_to_rel_path(value)
    if not rel_path or rel_path.endswith("/"):
        return False
    suffix = Path(rel_path).suffix.lower()
    return suffix in {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def _image_ref_to_rel_path(image_ref: str) -> str:
    value = image_ref.strip()
    if value.startswith("asset://local/"):
        value = value[len("asset://local/"):]
    return value.replace("\\", "/").lstrip("/")


def _source_parent(source_file: str) -> str:
    if not source_file:
        return ""
    normalized = source_file.replace("\\", "/")
    return str(PurePosixPath(normalized).parent).strip(".")


def _candidate_relative_paths(rel_path: str, source_parent: str) -> list[str]:
    paths: list[str] = []
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    if source_parent:
        paths.append(str(PurePosixPath(source_parent) / rel_path))
        if "/images/" in rel_path:
            paths.append(str(PurePosixPath(source_parent) / rel_path.split("/images/", 1)[1]))
    paths.append(rel_path)

    deduped: list[str] = []
    for path in paths:
        if path and path not in deduped:
            deduped.append(path)
    return deduped
