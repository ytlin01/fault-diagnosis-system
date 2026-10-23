"""Deterministic offline adapter for legacy Route B serving documents."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
import re
from typing import Any

_IDENTITY_VERSION = "dekg_evidence_identity_v1"
_CONTENT_KINDS = {"text", "table", "vlm_text"}
_BLOCKED_FIELDS = {
    "raw_text",
    "raw_image",
    "response_text",
    "raw_response",
    "endpoint",
    "secret",
    "credential",
    "masking_salt",
    "local_asset_path",
    "absolute_path",
    "debug_payload",
    "confirmed_diagnosis",
}


class DEKGLegacyAdapterError(ValueError):
    """Raised when a legacy document cannot be safely adapted."""


def adapt_dekg_legacy_document(
    document: Mapping[str, Any],
    *,
    release_id: str,
    source_id: str,
    source_version: str,
    manifest_digest: str,
    lineage_ref: str,
    masking_status: str,
    ingestion_mode: str = "full_document",
    partition_decision: Mapping[str, Any] | None = None,
    producer_commit: str | None = None,
) -> dict[str, Any]:
    """Map one governed serving document to DEKG evidence records.

    In residual mode, ``partition_decision.excluded_anchor_refs`` must identify
    existing table blocks. Those blocks are omitted before records are emitted.
    """

    if not isinstance(document, Mapping):
        raise DEKGLegacyAdapterError("document must be a mapping")
    for name, value in {
        "release_id": release_id,
        "source_id": source_id,
        "source_version": source_version,
        "manifest_digest": manifest_digest,
        "lineage_ref": lineage_ref,
    }.items():
        _require_nonempty(name, value)
    _reject_blocked_fields(document, path="document")

    doc_id = _text(document.get("doc_id"), "document.doc_id")
    blocks = document.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise DEKGLegacyAdapterError("document.blocks must be a non-empty list")
    normalized_blocks = [
        _normalize_block(block, index=index) for index, block in enumerate(blocks)
    ]
    eligible = [
        block
        for block in normalized_blocks
        if block["serving_eligible"] and block["retrieval_eligible"]
    ]
    if not eligible:
        raise DEKGLegacyAdapterError("document has no eligible serving-safe blocks")

    partition, co_source, excluded = _partition_metadata(
        ingestion_mode, partition_decision, eligible
    )
    emitted_blocks = [block for block in eligible if block["anchor"] not in excluded]
    if not emitted_blocks:
        raise DEKGLegacyAdapterError(
            "partition leaves no residual DEKG evidence records"
        )

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for block in emitted_blocks:
        text = _block_text(block)
        if not text:
            continue
        chunk_ordinal = 0
        chunk_id = f"{doc_id}:{block['block_id']}:c{chunk_ordinal:04d}"
        evidence_id = _evidence_id(
            ingestion_mode=ingestion_mode,
            source_id=source_id,
            source_version=source_version,
            doc_id=doc_id,
            block_id=block["block_id"],
            anchor=block["anchor"],
            content_kind=block["block_type"],
            chunk_ordinal=chunk_ordinal,
        )
        if evidence_id in seen_ids:
            raise DEKGLegacyAdapterError(f"duplicate evidence identity {evidence_id}")
        seen_ids.add(evidence_id)
        records.append(
            {
                "evidence_id": evidence_id,
                "ingestion_mode": ingestion_mode,
                "source_id": source_id,
                "source_version": source_version,
                "doc_id": doc_id,
                "block_id": block["block_id"],
                "chunk_id": chunk_id,
                "anchor": block["anchor"],
                "content_kind": block["block_type"],
                "text": text,
                "language": block["language"],
                "section_title": block["section_title"],
                "page_or_slide": block["page_or_slide"],
                "evidence_status": "evidence_only",
                "route_b_status": "evidence_only",
                "serving_safe": True,
                "tpdx_partition": dict(partition),
                "co_source": dict(co_source),
            }
        )
    if not records:
        raise DEKGLegacyAdapterError("document has no non-empty evidence content")

    package = {
        "schema_version": "dekg_evidence_v2",
        "release_id": release_id.strip(),
        "source_id": source_id.strip(),
        "source_version": source_version.strip(),
        "manifest_digest": manifest_digest.strip(),
        "lineage_ref": lineage_ref.strip(),
        "masking_status": masking_status,
        "serving_safe": True,
        "producer_commit": producer_commit.strip() if producer_commit else None,
        "records": records,
    }
    _validate_cross_record_rules(package)
    _validate_package(package)
    return package


def _normalize_block(block: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(block, Mapping):
        raise DEKGLegacyAdapterError(f"document.blocks[{index}] must be a mapping")
    _reject_blocked_fields(block, path=f"document.blocks[{index}]")
    block_type = str(block.get("block_type") or "text")
    if block_type not in _CONTENT_KINDS:
        raise DEKGLegacyAdapterError(
            f"document.blocks[{index}].block_type is unsupported"
        )
    raw_block_id = block.get("block_id")
    if raw_block_id in (None, ""):
        raw_block_id = block.get("block_index")
    block_id = _text(raw_block_id, f"document.blocks[{index}].block_id")
    anchor = _text(
        block.get("anchor") or block_id,
        f"document.blocks[{index}].anchor",
    )
    if block.get("needs_review") is True:
        raise DEKGLegacyAdapterError(
            f"document.blocks[{index}] requires review and cannot be adapted"
        )
    return {
        "block_type": block_type,
        "block_id": block_id,
        "anchor": anchor,
        "text": block.get("text"),
        "table": block.get("table"),
        "serving_eligible": bool(block.get("serving_eligible", True)),
        "retrieval_eligible": bool(block.get("retrieval_eligible", True)),
        "language": _nullable_text(block.get("language")),
        "section_title": _nullable_text(block.get("section_title")),
        "page_or_slide": _page_or_slide(block.get("page_or_slide", block.get("page"))),
    }


def _partition_metadata(
    ingestion_mode: str,
    decision: Mapping[str, Any] | None,
    blocks: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    if ingestion_mode == "full_document":
        if decision is not None:
            raise DEKGLegacyAdapterError(
                "full_document mode must not include a partition decision"
            )
        return (
            {
                "mode": "none",
                "decision_id": None,
                "tpdx_extraction_refs": [],
                "tpdx_extraction_content_kinds": [],
                "tpdx_consumption_state": None,
                "excluded_anchor_refs": [],
                "overlap_with_tpdx_fact": False,
            },
            {
                "group_id": None,
                "tpdx_extraction_refs": [],
                "independent_corroboration": False,
            },
            set(),
        )
    if ingestion_mode != "evidence_residual":
        raise DEKGLegacyAdapterError(f"unsupported ingestion_mode {ingestion_mode!r}")
    if not isinstance(decision, Mapping):
        raise DEKGLegacyAdapterError(
            "evidence_residual mode requires a partition decision"
        )
    allowed = {
        "decision_id",
        "tpdx_extraction_refs",
        "tpdx_consumption_state",
        "excluded_anchor_refs",
        "co_source_group_id",
    }
    unknown = set(decision) - allowed
    if unknown:
        raise DEKGLegacyAdapterError(
            f"partition decision has unsupported fields: {sorted(unknown)}"
        )
    decision_id = _text(decision.get("decision_id"), "partition.decision_id")
    tpdx_refs = _nonempty_string_list(
        decision.get("tpdx_extraction_refs"), "partition.tpdx_extraction_refs"
    )
    excluded_refs = _nonempty_string_list(
        decision.get("excluded_anchor_refs"), "partition.excluded_anchor_refs"
    )
    state = decision.get("tpdx_consumption_state")
    if state not in {"candidate_selected", "reviewed", "published"}:
        raise DEKGLegacyAdapterError(
            "partition.tpdx_consumption_state is invalid"
        )
    group_id = _text(
        decision.get("co_source_group_id"), "partition.co_source_group_id"
    )
    by_anchor = {block["anchor"]: block for block in blocks}
    missing = set(excluded_refs) - set(by_anchor)
    if missing:
        raise DEKGLegacyAdapterError(
            f"partition excludes unknown anchors: {sorted(missing)}"
        )
    non_tables = [
        anchor
        for anchor in excluded_refs
        if by_anchor[anchor]["block_type"] != "table"
    ]
    if non_tables:
        raise DEKGLegacyAdapterError(
            f"partition may exclude only table anchors: {sorted(non_tables)}"
        )
    partition = {
        "mode": "partitioned_table_extraction",
        "decision_id": decision_id,
        "tpdx_extraction_refs": tpdx_refs,
        "tpdx_extraction_content_kinds": ["table"],
        "tpdx_consumption_state": state,
        "excluded_anchor_refs": excluded_refs,
        "overlap_with_tpdx_fact": False,
    }
    co_source = {
        "group_id": group_id,
        "tpdx_extraction_refs": list(tpdx_refs),
        "independent_corroboration": False,
    }
    return partition, co_source, set(excluded_refs)


def _block_text(block: Mapping[str, Any]) -> str:
    value = block.get("text")
    if value not in (None, ""):
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise DEKGLegacyAdapterError(
                f"block {block['block_id']} text must be scalar"
            )
        return str(value).strip()
    table = block.get("table")
    if isinstance(table, Mapping) and set(table) <= {"rows"}:
        rows = table.get("rows")
        if isinstance(rows, list):
            rendered: list[str] = []
            for row in rows:
                if not isinstance(row, list):
                    raise DEKGLegacyAdapterError(
                        f"block {block['block_id']} table rows must be lists"
                    )
                rendered.append(" | ".join(str(cell) for cell in row))
            return "\n".join(rendered).strip()
    if table not in (None, {}):
        raise DEKGLegacyAdapterError(
            f"block {block['block_id']} has unsupported table shape"
        )
    return ""


def _evidence_id(
    *,
    ingestion_mode: str,
    source_id: str,
    source_version: str,
    doc_id: str,
    block_id: str,
    anchor: str,
    content_kind: str,
    chunk_ordinal: int,
) -> str:
    material = [
        _IDENTITY_VERSION,
        ingestion_mode,
        source_id,
        source_version,
        doc_id,
        block_id,
        anchor,
        content_kind,
        chunk_ordinal,
    ]
    encoded = json.dumps(
        material, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return "DEK_" + hashlib.sha256(encoded).hexdigest()


def _validate_cross_record_rules(package: Mapping[str, Any]) -> None:
    records = package["records"]
    for record in records:
        partition = record["tpdx_partition"]
        co_source = record["co_source"]
        if record["anchor"] in partition["excluded_anchor_refs"]:
            raise DEKGLegacyAdapterError(
                f"record re-emits excluded anchor {record['anchor']}"
            )
        if co_source["tpdx_extraction_refs"] != partition["tpdx_extraction_refs"]:
            raise DEKGLegacyAdapterError("co-source references do not match partition")


def _nonempty_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DEKGLegacyAdapterError(f"{path} must be a non-empty list")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _text(item, path)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _page_or_slide(value: Any) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DEKGLegacyAdapterError("page_or_slide must be a string, integer, or null")
    if isinstance(value, str):
        return value.strip() or None
    return value


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise DEKGLegacyAdapterError("expected scalar text or null")
    return str(value).strip() or None


def _text(value: Any, path: str) -> str:
    text = _nullable_text(value)
    if text is None:
        raise DEKGLegacyAdapterError(f"{path} must be a non-empty scalar")
    return text


def _require_nonempty(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DEKGLegacyAdapterError(f"{name} must be a non-empty string")


def _reject_blocked_fields(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in _BLOCKED_FIELDS:
                raise DEKGLegacyAdapterError(f"{path}.{key} is blocked")
            _reject_blocked_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_blocked_fields(child, path=f"{path}[{index}]")


def _validate_package(package: Mapping[str, Any]) -> None:
    if package.get("schema_version") != "dekg_evidence_v2":
        raise DEKGLegacyAdapterError("canonical DEKG schema_version is invalid")
    if package.get("serving_safe") is not True:
        raise DEKGLegacyAdapterError("canonical DEKG package is not serving-safe")
    digest = package.get("manifest_digest")
    if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        raise DEKGLegacyAdapterError("manifest_digest must be sha256 plus 64 lowercase hex characters")
    if package.get("masking_status") not in {
        "masked",
        "not_required",
        "reviewed_masked",
    }:
        raise DEKGLegacyAdapterError("masking_status is invalid")
    records = package.get("records")
    if not isinstance(records, list) or not records:
        raise DEKGLegacyAdapterError("canonical DEKG package must contain records")
