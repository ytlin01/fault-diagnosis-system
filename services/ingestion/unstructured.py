"""Unstructured document masking for MinerU and canonical block output.

This module is local-processing only. It supports JSON, Markdown, and plain
text produced by MinerU or the first-pass canonical document ingestion layer.
It does not call external APIs and does not interpret raw sensitive assets.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from services.ingestion.field_actions import _get_salt, _make_token


CANONICAL_SCHEMA_VERSION = "unstructured_canonical_v1"

CANONICAL_DROP_FIELD_NAMES = {
    "raw_response",
    "resolved_image_path",
}

SERVING_DROP_FIELD_NAMES = {
    "asset_ref",
    "asset_local_path",
    "asset_source_path",
    "asset_sha256",
    "image_ref",
    "image_path",
    "resolved_image_path",
    "table_image_ref",
    "raw_response",
    "response_text",
    "response_metrics",
    "endpoint",
}

SERVING_LOCAL_VLM_ALLOWED_KEYS = {
    "candidate",
    "executed",
    "status",
    "reason",
    "metadata_only",
    "prompt_contract",
}

SERVING_SAFE_IMAGE_SOURCE_TYPES = {
    "image",
    "figure-chart",
}

SERVING_DROPPED_RAW_ASSET_BLOCK_TYPES = {
    "image",
    "figure-chart",
    "asset-placeholder",
}


def detect_format(file_path: Path) -> str:
    """Detect a supported unstructured masking input format."""
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in (".md", ".markdown"):
        return "markdown"
    return "txt"


class MaskingPattern:
    """A single compiled regex pattern with its masking action."""

    def __init__(
        self,
        name: str,
        regex: str,
        action: str,
        replacement: str | None = None,
        tokenizer_config: dict | None = None,
    ):
        self.name = name
        self.compiled = re.compile(regex)
        self.action = action
        self.replacement = replacement or f"[{name.upper()}_REDACTED]"
        self.tokenizer_config = tokenizer_config or {}
        self.match_count = 0

    def apply(self, text: str) -> tuple[str, int]:
        """Apply this pattern to text. Returns (masked_text, num_matches)."""
        if self.action == "redact":
            result, count = self.compiled.subn(self.replacement, text)
        elif self.action == "hash":
            salt = _get_salt()

            def _hash_repl(match: re.Match) -> str:
                return _make_token(
                    match.group(0),
                    salt=salt,
                    prefix=self.tokenizer_config.get("prefix", "HASH_"),
                    length=self.tokenizer_config.get("hash_length", 12),
                )

            result, count = self.compiled.subn(_hash_repl, text)
        else:
            result, count = text, 0

        self.match_count += count
        return result, count


def compile_patterns(rules: dict) -> list[MaskingPattern]:
    """Build MaskingPattern list from the unstructured section of rules."""
    unstructured_cfg = rules.get("unstructured", {})
    tokenizer_cfg = rules.get("tokenizer", {})
    patterns = []
    for pattern_cfg in unstructured_cfg.get("patterns", []):
        patterns.append(MaskingPattern(
            name=pattern_cfg["name"],
            regex=pattern_cfg["regex"],
            action=pattern_cfg["action"],
            replacement=pattern_cfg.get("replacement"),
            tokenizer_config=tokenizer_cfg,
        ))
    return patterns


def mask_text(text: str, patterns: list[MaskingPattern]) -> tuple[str, list[dict]]:
    """Apply all patterns to a text string sequentially."""
    records: list[dict] = []
    for pattern in patterns:
        text, count = pattern.apply(text)
        if count > 0:
            records.append({
                "pattern": pattern.name,
                "action": pattern.action,
                "matches": count,
            })
    return text, records


def mask_json_value(value: Any, patterns: list[MaskingPattern]) -> tuple[Any, list[dict]]:
    """Recursively walk a JSON-like structure, masking all string values."""
    all_records: list[dict] = []

    if isinstance(value, str):
        return mask_text(value, patterns)
    if isinstance(value, dict):
        result = {}
        for key, nested in value.items():
            masked_value, records = mask_json_value(nested, patterns)
            result[key] = masked_value
            all_records.extend(records)
        return result, all_records
    if isinstance(value, list):
        result = []
        for item in value:
            masked_item, records = mask_json_value(item, patterns)
            result.append(masked_item)
            all_records.extend(records)
        return result, all_records
    return value, []


def read_and_mask_file(file_path: Path, patterns: list[MaskingPattern]) -> tuple[Any, list[dict], str]:
    """Read one supported file and return masked payload, records, and format."""
    source_format = detect_format(file_path)
    if source_format == "json":
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        masked_payload, records = mask_json_value(payload, patterns)
        return masked_payload, records, source_format

    text = file_path.read_text(encoding="utf-8")
    masked_text, records = mask_text(text, patterns)
    return masked_text, records, source_format


def sanitize_masked_canonical_payload(masked_payload: Any) -> tuple[Any, dict[str, Any]]:
    """Remove raw/debug-only fields from a masked canonical document.

    The masked canonical view remains an internal artifact, so it can keep
    structured text and VLM response text for review. It should not carry raw
    model responses or machine-local absolute paths.
    """
    policy = {
        "applied": False,
        "fields_dropped": {},
        "reason": None,
    }
    if not _is_canonical_document(masked_payload):
        policy["reason"] = "not a canonical block document"
        return masked_payload, policy

    sanitized = deepcopy(masked_payload)
    field_counts = _drop_fields_recursive(
        sanitized,
        CANONICAL_DROP_FIELD_NAMES,
    )
    policy["applied"] = True
    policy["fields_dropped"] = field_counts
    return sanitized, policy


def build_serving_payload(
    masked_payload: Any,
    *,
    canonical_only: bool = False,
) -> tuple[Any | None, dict[str, Any]]:
    """Build a serving view from masked content.

    Canonical block documents use per-block serving_eligible flags. Generic
    JSON/Markdown/TXT payloads return the masked payload unless canonical_only
    is requested.
    """
    policy = {
        "canonical_only": canonical_only,
        "serving_generated": False,
        "blocks_dropped": 0,
        "derived_vlm_text_blocks": 0,
        "reason": None,
    }
    if canonical_only:
        policy["reason"] = "canonical_only requested"
        return None, policy

    if not _is_canonical_document(masked_payload):
        policy["serving_generated"] = True
        return masked_payload, policy

    serving_payload = deepcopy(masked_payload)
    serving_blocks = []
    dropped = 0
    derived_vlm_text_blocks = 0
    for block in masked_payload.get("blocks", []):
        block_type = block.get("block_type")
        if block_type in SERVING_SAFE_IMAGE_SOURCE_TYPES:
            dropped += 1
            derived_block = _build_serving_safe_vlm_text_block(block)
            if derived_block is not None:
                serving_blocks.append(derived_block)
                derived_vlm_text_blocks += 1
            continue

        if block_type in SERVING_DROPPED_RAW_ASSET_BLOCK_TYPES:
            dropped += 1
            continue

        if block.get("serving_eligible") is not True:
            dropped += 1
            continue
        serving_block = deepcopy(block)
        if serving_block.get("block_type") in SERVING_DROPPED_RAW_ASSET_BLOCK_TYPES:
            serving_block.pop("asset_ref", None)
            serving_block["asset_removed_from_serving"] = True
        serving_blocks.append(serving_block)

    if not serving_blocks:
        policy["blocks_dropped"] = dropped
        policy["derived_vlm_text_blocks"] = derived_vlm_text_blocks
        policy["reason"] = "no serving-eligible blocks after policy filtering"
        return None, policy

    serving_payload["view"] = "serving"
    serving_payload["blocks"] = serving_blocks
    serving_payload["block_count"] = len(serving_blocks)
    serving_payload["serving_policy"] = {
        "generated_from_masked_canonical": True,
        "dropped_ineligible_blocks": dropped,
        "derived_vlm_text_blocks": derived_vlm_text_blocks,
        "raw_assets_included": False,
    }
    serving_sanitization = _sanitize_serving_payload(serving_payload)
    serving_payload["serving_policy"]["sanitization"] = serving_sanitization
    policy["serving_generated"] = True
    policy["blocks_dropped"] = dropped
    policy["derived_vlm_text_blocks"] = derived_vlm_text_blocks
    policy["sanitization"] = serving_sanitization
    return serving_payload, policy


def summarize_match_records(records: list[dict]) -> dict[str, Any]:
    """Collapse raw match records into pattern-level counts."""
    summary: dict[str, Any] = {"total_matches": 0, "patterns": {}}
    for record in records:
        pattern_name = record.get("pattern", "unknown")
        matches = int(record.get("matches", 0))
        action = record.get("action")
        summary["total_matches"] += matches
        pattern_summary = summary["patterns"].setdefault(
            pattern_name,
            {"matches": 0, "action": action},
        )
        pattern_summary["matches"] += matches
    return summary


def write_masked_payload(payload: Any, path: Path, source_format: str) -> None:
    """Write a masked payload preserving the selected output format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if source_format == "json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")


def _is_canonical_document(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("blocks"), list)
        and (
            value.get("schema_version") == CANONICAL_SCHEMA_VERSION
            or value.get("source", {}).get("route") is not None
        )
    )


def _build_serving_safe_vlm_text_block(block: dict[str, Any]) -> dict[str, Any] | None:
    """Derive a serving-safe text block from a masked image/figure block."""
    text = _compose_serving_safe_visual_text(block)
    if not text:
        return None

    derived_block = {
        "block_id": f"{block.get('block_id')}:vlm_text",
        "block_index": block.get("block_index"),
        "block_type": "vlm_text",
        "text": text,
        "serving_eligible": True,
        "retrieval_eligible": True,
        "graph_eligible": True,
        "needs_review": bool(block.get("needs_review", False)),
        "derived_from_block_id": block.get("block_id"),
        "derived_from_block_type": block.get("block_type"),
        "asset_removed_from_serving": True,
    }
    for key in ("source_anchor", "parser", "sensitivity_hint", "source_bbox"):
        if key in block:
            derived_block[key] = deepcopy(block[key])

    local_vlm = block.get("enrichment", {}).get("local_vlm")
    if isinstance(local_vlm, dict):
        derived_block["enrichment"] = {
            "local_vlm": deepcopy(local_vlm),
        }

    return derived_block


def _compose_serving_safe_visual_text(block: dict[str, Any]) -> str | None:
    pieces: list[str] = []

    block_text = _clean_text_value(block.get("text"))
    if block_text and not _looks_like_placeholder_image_text(block_text):
        pieces.append(f"Observed text: {block_text}")

    response_text = block.get("enrichment", {}).get("local_vlm", {}).get("response_text")
    response_summary = _format_vlm_response_text(response_text)
    if response_summary:
        pieces.append(response_summary)

    deduped = _dedupe_preserve_order(pieces)
    if not deduped:
        return None
    return "\n".join(deduped)


def _format_vlm_response_text(response_text: Any) -> str | None:
    text = _clean_text_value(response_text)
    if not text:
        return None

    normalized = _strip_markdown_code_fence(text)
    parsed = _try_parse_json_text(normalized)
    if isinstance(parsed, dict):
        sections: list[str] = []
        _append_section(sections, "Visual summary", parsed.get("image_summary"))
        _append_section(sections, "Visual summary", parsed.get("visual_observation"))
        _append_section(sections, "Visual summary", parsed.get("content_summary"))
        _append_section(sections, "Visual summary", parsed.get("description"))
        _append_section(sections, "Extracted text", parsed.get("extracted_text"))
        _append_section(sections, "Extracted text", parsed.get("ocr_text"))
        _append_section(sections, "Candidate entities", parsed.get("candidate_entities"))
        _append_section(sections, "Review notes", parsed.get("review_notes"))
        deduped = _dedupe_preserve_order(sections)
        if deduped:
            return "\n".join(deduped)
        flattened = _flatten_json_text_values(parsed)
        return flattened or None

    if isinstance(parsed, list):
        flattened = _flatten_json_text_values(parsed)
        return flattened or None

    return normalized


def _try_parse_json_text(value: str) -> Any | None:
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _append_section(sections: list[str], label: str, value: Any) -> None:
    text = _flatten_json_text_values(value)
    if text:
        sections.append(f"{label}: {text}")


def _flatten_json_text_values(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        items = [
            item
            for item in (_flatten_json_text_values(entry) for entry in value)
            if item
        ]
        return "; ".join(_dedupe_preserve_order(items))
    if isinstance(value, dict):
        items = [
            item
            for item in (_flatten_json_text_values(entry) for entry in value.values())
            if item
        ]
        return "; ".join(_dedupe_preserve_order(items))
    return ""


def _clean_text_value(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _strip_markdown_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _looks_like_placeholder_image_text(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return normalized in {
        "image",
        "figure",
        "chart",
        "image block",
        "figure chart",
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _sanitize_serving_payload(value: Any) -> dict[str, Any]:
    """Apply serving-only field policy in-place and return drop counts."""
    local_vlm_counts = _sanitize_local_vlm_sections(value)
    field_counts = _drop_fields_recursive(value, SERVING_DROP_FIELD_NAMES)
    return {
        "fields_dropped": field_counts,
        "local_vlm_sections_sanitized": local_vlm_counts["sections"],
        "local_vlm_response_removed": local_vlm_counts["responses_removed"],
    }


def _sanitize_local_vlm_sections(value: Any) -> dict[str, int]:
    """Trim local VLM metadata to serving-safe status fields."""
    counts = {"sections": 0, "responses_removed": 0}

    if isinstance(value, dict):
        local_vlm = value.get("local_vlm")
        if isinstance(local_vlm, dict):
            counts["sections"] += 1
            response_removed = any(
                key in local_vlm
                for key in ("response_text", "response_metrics", "raw_response")
            )
            allowed = {
                key: deepcopy(local_vlm[key])
                for key in SERVING_LOCAL_VLM_ALLOWED_KEYS
                if key in local_vlm
            }
            if response_removed:
                allowed["response_removed_from_serving"] = True
                counts["responses_removed"] += 1
            value["local_vlm"] = allowed

        for nested in value.values():
            nested_counts = _sanitize_local_vlm_sections(nested)
            counts["sections"] += nested_counts["sections"]
            counts["responses_removed"] += nested_counts["responses_removed"]
    elif isinstance(value, list):
        for item in value:
            nested_counts = _sanitize_local_vlm_sections(item)
            counts["sections"] += nested_counts["sections"]
            counts["responses_removed"] += nested_counts["responses_removed"]

    return counts


def _drop_fields_recursive(value: Any, field_names: set[str]) -> dict[str, int]:
    """Drop matching dict keys anywhere in a JSON-like structure."""
    counts: dict[str, int] = {}

    if isinstance(value, dict):
        for key in list(value.keys()):
            if key in field_names:
                value.pop(key, None)
                counts[key] = counts.get(key, 0) + 1
                continue
            nested_counts = _drop_fields_recursive(value[key], field_names)
            _merge_counts(counts, nested_counts)
    elif isinstance(value, list):
        for item in value:
            nested_counts = _drop_fields_recursive(item, field_names)
            _merge_counts(counts, nested_counts)

    return counts


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, count in source.items():
        target[key] = target.get(key, 0) + count
