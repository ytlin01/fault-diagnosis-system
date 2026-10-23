"""Canonical block document utilities for unstructured ingestion.

The output is a block-level canonical document consumed by masking,
retrieval preparation, and later mapping review. It is not an external
serving artifact.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree

if TYPE_CHECKING:
    from services.ingestion.name_mapping import NameMappingRegistry


INGESTION_VERSION = "unstructured_canonical_v1"

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
DOCX_EXTENSIONS = {".docx"}
PPTX_EXTENSIONS = {".pptx"}
PDF_EXTENSIONS = {".pdf"}
MINERU_EXTENSIONS = {".json"}
THREE_D_EXTENSIONS = {".3mf", ".fbx", ".glb", ".gltf", ".iges", ".igs", ".obj", ".step", ".stl", ".stp"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | DOCX_EXTENSIONS | PPTX_EXTENSIONS | PDF_EXTENSIONS | MINERU_EXTENSIONS | THREE_D_EXTENSIONS

TOC_ENTRY_RE = re.compile(r"^(?P<section>\d+(?:\.\d+)*)(?:\s+|[.)])(?P<title>.+?)\s+(?P<target_page>\d{1,4})$")
TOC_SCAN_INITIAL_BLOCKS = 120
UNSTRUCTURED_NAME_MAPPING_MIN_CONTAINS_LEN = 2


def detect_source_kind(path: Path) -> str:
    """Return the ingestion route for one source path."""
    suffix = path.suffix.lower()
    if suffix in DOCX_EXTENSIONS:
        return "native_docx"
    if suffix in PPTX_EXTENSIONS:
        return "native_pptx"
    if suffix in PDF_EXTENSIONS:
        return "mineru_pdf_required"
    if suffix in TEXT_EXTENSIONS:
        return "native_text"
    if suffix in MINERU_EXTENSIONS:
        return "mineru_json_or_canonical"
    if suffix in THREE_D_EXTENSIONS:
        return "three_d_asset_placeholder"
    return "unsupported"


def build_canonical_document(
    source_path: Path,
    *,
    source_root: Path | None = None,
    asset_output_root: Path | None = None,
    name_mapping_registry: "NameMappingRegistry" | None = None,
    mark_vlm_candidates: bool = True,
    name_mapping_text_mode: str = "contains",
) -> dict[str, Any]:
    """Read or register one source as a canonical block document."""
    source_path = source_path.resolve()
    source_root = source_root.resolve() if source_root else source_path.parent
    asset_output_root = asset_output_root.resolve() if asset_output_root else None
    source_label = _safe_relative(source_path, source_root)
    source_kind = detect_source_kind(source_path)
    doc_id = _make_doc_id(source_path)

    document: dict[str, Any] = {
        "schema_version": INGESTION_VERSION,
        "doc_id": doc_id,
        "source": {
            "file": source_label,
            "format": source_path.suffix.lower().lstrip(".") or "unknown",
            "sha256": _file_sha256(source_path) if source_path.exists() else None,
            "route": source_kind,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parser": {"name": source_kind, "external_api_used": False},
        "serving_policy": {
            "default_serving_eligible": False,
            "reason": "Raw canonical documents require masking and review before serving.",
        },
        "blocks": [],
        "normalization": {},
        "open_questions": [],
    }

    if source_kind == "native_text":
        document["blocks"] = _blocks_from_text_file(source_path, doc_id, source_label)
    elif source_kind == "native_docx":
        document["blocks"] = _blocks_from_docx(
            source_path,
            doc_id,
            source_label,
            asset_output_root=asset_output_root,
        )
        _record_office_asset_summary(document, asset_output_root=asset_output_root)
    elif source_kind == "native_pptx":
        document["blocks"] = _blocks_from_pptx(
            source_path,
            doc_id,
            source_label,
            asset_output_root=asset_output_root,
        )
        _record_office_asset_summary(document, asset_output_root=asset_output_root)
    elif source_kind == "mineru_pdf_required":
        document["blocks"] = [_asset_placeholder_block(
            doc_id=doc_id,
            source_file=source_label,
            block_index=0,
            asset_kind="pdf_requires_mineru",
            caption="PDF registered. Run MinerU before downstream masking/serving.",
            parser=source_kind,
            sensitivity_hint="unknown",
        )]
        document["open_questions"].append("PDF parsing depends on MinerU output quality and layout/OCR status.")
    elif source_kind == "mineru_json_or_canonical":
        document = _document_from_json(source_path, document, source_label)
    elif source_kind == "three_d_asset_placeholder":
        document["blocks"] = [_asset_placeholder_block(
            doc_id=doc_id,
            source_file=source_label,
            block_index=0,
            asset_kind="3d_model_or_3d_view",
            caption="3D asset registered for future three_d_asset_adapter.",
            parser=source_kind,
            sensitivity_hint="unknown",
        )]
        document["open_questions"].append("3D semantic parsing is out of scope for the first ingestion pass.")
    else:
        document["blocks"] = [_asset_placeholder_block(
            doc_id=doc_id,
            source_file=source_label,
            block_index=0,
            asset_kind="unsupported_source",
            caption="Unsupported file type registered as metadata only.",
            parser=source_kind,
            sensitivity_hint="unknown",
        )]
        document["open_questions"].append(f"Unsupported extension: {source_path.suffix.lower()}")

    if name_mapping_registry:
        apply_name_mapping_to_document(
            document,
            name_mapping_registry,
            text_match_mode=name_mapping_text_mode,
        )

    annotate_structure_blocks(document)

    if mark_vlm_candidates:
        mark_local_vlm_candidates(document)

    document["block_count"] = len(document.get("blocks", []))
    return document


def build_synthetic_canonical_document() -> dict[str, Any]:
    """Build a synthetic document that exercises all first-pass block types."""
    doc_id = "synthetic_unstructured_demo"
    blocks = [
        _text_block(
            doc_id=doc_id,
            source_file="synthetic/demo.pdf",
            block_index=0,
            text="Alarm phenomenon: station C1STN stop button fault on Line L1.",
            parser="synthetic",
            page=1,
            serving_eligible=True,
            sensitivity_hint="low",
        ),
        _text_block(
            doc_id=doc_id,
            source_file="synthetic/demo.pdf",
            block_index=1,
            text="1.3.1 Auto loading structure 8",
            parser="synthetic",
            page=1,
            serving_eligible=True,
            sensitivity_hint="low",
        ),
        _table_block(
            doc_id=doc_id,
            source_file="synthetic/demo.pdf",
            block_index=2,
            rows=[["field", "value"], ["station", "C1STN"], ["action", "Check safety relay and reset E-stop circuit."]],
            parser="synthetic",
            page=1,
            serving_eligible=True,
            sensitivity_hint="low",
        ),
        _asset_placeholder_block(
            doc_id=doc_id,
            source_file="synthetic/demo.pdf",
            block_index=3,
            asset_kind="image",
            caption="Equipment photo placeholder; not serving eligible by default.",
            parser="synthetic",
            page=2,
            sensitivity_hint="high",
        ),
        _asset_placeholder_block(
            doc_id=doc_id,
            source_file="synthetic/demo.pdf",
            block_index=4,
            asset_kind="figure-chart",
            caption="Trend chart candidate for local VLM enrichment.",
            parser="synthetic",
            page=3,
            sensitivity_hint="medium",
        ),
        _asset_placeholder_block(
            doc_id=doc_id,
            source_file="synthetic/model.step",
            block_index=5,
            asset_kind="3d_model_or_3d_view",
            caption="3D asset placeholder for future three_d_asset_adapter.",
            parser="synthetic",
            sensitivity_hint="unknown",
        ),
    ]
    document = {
        "schema_version": INGESTION_VERSION,
        "doc_id": doc_id,
        "source": {"file": "synthetic/demo.pdf", "format": "synthetic", "sha256": None, "route": "synthetic"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parser": {"name": "synthetic", "external_api_used": False},
        "serving_policy": {"default_serving_eligible": False, "reason": "Synthetic preview only; serving requires masking."},
        "blocks": blocks,
        "normalization": {},
        "open_questions": ["Serving eligibility for images, charts, and 3D assets requires review."],
    }
    annotate_structure_blocks(document)
    mark_local_vlm_candidates(document)
    document["block_count"] = len(blocks)
    return document


def apply_name_mapping_to_document(
    document: dict[str, Any],
    registry: "NameMappingRegistry",
    *,
    text_match_mode: str = "contains",
) -> dict[str, Any]:
    """Apply content-scope name mapping to text-like block fields."""
    report = {
        "enabled": True,
        "mapping_file": str(registry.path),
        "blocks_touched": 0,
        "fields_touched": 0,
        "replacements": 0,
        "rules": {},
        "text_match_mode": text_match_mode,
    }
    for block in document.get("blocks", []):
        block_touched = False
        for field in ("text", "caption"):
            mapped_value, summary = _apply_unstructured_name_mapping(
                block.get(field),
                registry,
                text_match_mode=text_match_mode,
            )
            if not summary["applied"]:
                continue
            block[field] = mapped_value
            block_touched = True
            report["fields_touched"] += 1
            report["replacements"] += summary["replacements"]
            for rule_name in summary["rules"]:
                report["rules"][rule_name] = report["rules"].get(rule_name, 0) + 1
        if block_touched:
            block["name_mapping_applied"] = True
            report["blocks_touched"] += 1

    document.setdefault("normalization", {})["name_mapping"] = report
    return document


def annotate_structure_blocks(document: dict[str, Any]) -> dict[str, Any]:
    """Mark structural-only blocks such as table-of-contents entries."""
    report = {"toc_entries": 0}
    for block in document.get("blocks", []):
        if block.get("block_type") != "text":
            continue
        if block.get("block_index", 0) > TOC_SCAN_INITIAL_BLOCKS:
            continue
        toc_entry = _parse_toc_entry(block.get("text"))
        if not toc_entry:
            continue
        block["structure_role"] = "toc_entry"
        block["toc_entry"] = toc_entry
        block["serving_eligible"] = False
        block["retrieval_eligible"] = False
        block["graph_eligible"] = False
        block["needs_review"] = False
        report["toc_entries"] += 1

    document.setdefault("normalization", {})["structure_detection"] = report
    return document


def mark_local_vlm_candidates(document: dict[str, Any]) -> dict[str, Any]:
    """Mark blocks where local VLM enrichment can be evaluated later."""
    candidate_kinds = {"image", "figure-chart", "3d_model_or_3d_view"}
    for block in document.get("blocks", []):
        block_type = block.get("block_type")
        asset_kind = block.get("asset_kind")
        candidate = block_type in {"image", "figure-chart"} or asset_kind in candidate_kinds
        if not candidate:
            continue
        block["enrichment"] = {
            "local_vlm": {
                "candidate": True,
                "executed": False,
                "recommended_dev_model": "qwen2.5vl:7b",
                "dev_machine": "E2a small-sample validation",
                "batch_machine": "E3 or approved company provider",
                "output_contract": "metadata augmentation only; not final MappingRecord",
            }
        }
    return document


def write_canonical_document(document: dict[str, Any], output_dir: Path) -> Path:
    """Write one canonical document JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_safe_filename(document.get('doc_id', 'unstructured_document'))}_canonical.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _blocks_from_text_file(source_path: Path, doc_id: str, source_label: str) -> list[dict[str, Any]]:
    text = source_path.read_text(encoding="utf-8")
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    if not chunks and text.strip():
        chunks = [text.strip()]
    return [
        _text_block(
            doc_id=doc_id,
            source_file=source_label,
            block_index=index,
            text=chunk,
            parser="native_text",
            section=f"paragraph_{index + 1}",
            serving_eligible=True,
            sensitivity_hint="unknown",
        )
        for index, chunk in enumerate(chunks)
    ]


def _blocks_from_docx(
    source_path: Path,
    doc_id: str,
    source_label: str,
    *,
    asset_output_root: Path | None,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    with zipfile.ZipFile(source_path) as archive:
        if "word/document.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("word/document.xml"))
            body = root.find(_w_tag("body"))
            if body is not None:
                for child in list(body):
                    tag = _strip_namespace(child.tag)
                    if tag == "p":
                        text = _collect_text(child)
                        if text:
                            blocks.append(_text_block(doc_id=doc_id, source_file=source_label, block_index=len(blocks), text=text, parser="native_docx", section="document", serving_eligible=True, sensitivity_hint="unknown"))
                    elif tag == "tbl":
                        rows = _collect_docx_table(child)
                        if rows:
                            blocks.append(_table_block(doc_id=doc_id, source_file=source_label, block_index=len(blocks), rows=rows, parser="native_docx", section="document", serving_eligible=True, sensitivity_hint="unknown"))
        for name in sorted(archive.namelist()):
            if name.startswith("word/media/"):
                asset = _extract_office_media_asset(
                    archive,
                    name,
                    asset_output_root=asset_output_root,
                    doc_id=doc_id,
                )
                blocks.append(_asset_placeholder_block(
                    doc_id=doc_id,
                    source_file=source_label,
                    block_index=len(blocks),
                    asset_kind="image",
                    caption=f"Embedded DOCX media: {Path(name).name}",
                    parser="native_docx",
                    sensitivity_hint="unknown",
                    asset=asset,
                ))
    return blocks


def _blocks_from_pptx(
    source_path: Path,
    doc_id: str,
    source_label: str,
    *,
    asset_output_root: Path | None,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    with zipfile.ZipFile(source_path) as archive:
        # 改动1: 用 presentation.xml <p:sldIdLst> 确定真实 slide 显示顺序
        _R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        try:
            prs_root = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
            sld_id_lst = next(
                (el for el in prs_root.iter() if _strip_namespace(el.tag) == "sldIdLst"),
                None,
            )
            rels_root = ElementTree.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
            rid_to_target: dict[str, str] = {
                rel.get("Id"): rel.get("Target")
                for rel in rels_root.iter()
                if _strip_namespace(rel.tag) == "Relationship" and rel.get("Id") and rel.get("Target")
            }
            slide_names = []
            if sld_id_lst is not None:
                for sld_id_el in sld_id_lst:
                    if _strip_namespace(sld_id_el.tag) == "sldId":
                        rid = sld_id_el.get(f"{{{_R_NS}}}id")
                        target = rid_to_target.get(rid, "") if rid else ""
                        if target.startswith("../"):
                            normalized = "ppt/" + target[3:]
                        elif not target.startswith("ppt/"):
                            normalized = "ppt/" + target
                        else:
                            normalized = target
                        if normalized in archive.namelist():
                            slide_names.append(normalized)
            if not slide_names:
                raise KeyError("no slides resolved from presentation.xml")
        except KeyError:
            slide_names = sorted(
                (name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)),
                key=_slide_sort_key,
            )
        for slide_index, slide_name in enumerate(slide_names, start=1):
            root = ElementTree.fromstring(archive.read(slide_name))
            # 改动2: 先产出 table block（遍历所有 <a:tbl>）
            for el in root.iter():
                if _strip_namespace(el.tag) == "tbl":
                    tbl_rows = _collect_pptx_table(el)
                    if tbl_rows:
                        blocks.append(_table_block(doc_id=doc_id, source_file=source_label, block_index=len(blocks), rows=tbl_rows, parser="native_pptx", slide=slide_index, serving_eligible=True, sensitivity_hint="unknown"))
            # 改动3: 收集文本时排除 <a:tbl> 子树，防止表格内容重复进入 text block
            tbl_ids: set[int] = set()
            for tbl in root.iter():
                if _strip_namespace(tbl.tag) == "tbl":
                    for desc in tbl.iter():
                        tbl_ids.add(id(desc))
            if tbl_ids:
                values = [
                    node.text.strip()
                    for node in root.iter()
                    if _strip_namespace(node.tag) == "t" and node.text and id(node) not in tbl_ids
                ]
                text = " ".join(v for v in values if v).strip()
            else:
                text = _collect_text(root)
            if text:
                blocks.append(_text_block(doc_id=doc_id, source_file=source_label, block_index=len(blocks), text=text, parser="native_pptx", slide=slide_index, serving_eligible=True, sensitivity_hint="unknown"))
        for name in sorted(archive.namelist()):
            if name.startswith("ppt/media/"):
                asset = _extract_office_media_asset(
                    archive,
                    name,
                    asset_output_root=asset_output_root,
                    doc_id=doc_id,
                )
                blocks.append(_asset_placeholder_block(
                    doc_id=doc_id,
                    source_file=source_label,
                    block_index=len(blocks),
                    asset_kind="image",
                    caption=f"Embedded PPTX media: {Path(name).name}",
                    parser="native_pptx",
                    sensitivity_hint="unknown",
                    asset=asset,
                ))
    return blocks


def _document_from_json(source_path: Path, base_document: dict[str, Any], source_label: str) -> dict[str, Any]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("schema_version") == INGESTION_VERSION:
        document = deepcopy(payload)
        document.setdefault("source", {})["file"] = source_label
        return document

    doc_id = base_document["doc_id"]
    blocks: list[dict[str, Any]] = []
    mineru_items = _flatten_mineru_content_list(payload)
    if mineru_items:
        for item, page_idx in mineru_items:
            _append_mineru_block(
                blocks,
                item,
                page_idx=page_idx,
                doc_id=doc_id,
                source_file=source_label,
            )
        base_document.setdefault("normalization", {})["mineru"] = {
            "source_format": "content_list",
            "items_read": len(mineru_items),
            "blocks_created": len(blocks),
        }
    elif isinstance(payload, dict) and isinstance(payload.get("blocks"), list):
        for raw_block in payload["blocks"]:
            text = _coerce_text(raw_block)
            if text:
                blocks.append(_text_block(doc_id=doc_id, source_file=source_label, block_index=len(blocks), text=text, parser="mineru_json", page=_coerce_int(raw_block.get("page") or raw_block.get("page_idx")), serving_eligible=True, sensitivity_hint="unknown"))
    if not blocks:
        for index, text in enumerate(_collect_json_strings(payload)):
            blocks.append(_text_block(doc_id=doc_id, source_file=source_label, block_index=index, text=text, parser="json_string_extract", serving_eligible=True, sensitivity_hint="unknown"))
    base_document["blocks"] = blocks
    return base_document


def _flatten_mineru_content_list(payload: Any) -> list[tuple[dict[str, Any], int | None]]:
    if not isinstance(payload, list):
        return []
    flattened: list[tuple[dict[str, Any], int | None]] = []
    looks_like_mineru = False
    for page_idx, entry in enumerate(payload):
        if isinstance(entry, list):
            for item in entry:
                if isinstance(item, dict) and "type" in item:
                    looks_like_mineru = True
                    flattened.append((item, page_idx))
        elif isinstance(entry, dict) and "type" in entry:
            looks_like_mineru = True
            flattened.append((entry, _coerce_int(entry.get("page_idx"))))
    return flattened if looks_like_mineru else []


def _append_mineru_block(
    blocks: list[dict[str, Any]],
    item: dict[str, Any],
    *,
    page_idx: int | None,
    doc_id: str,
    source_file: str,
) -> None:
    item_type = str(item.get("type", "")).lower()
    if item_type in {"footer", "page_footer", "page_number"}:
        return

    page = _coerce_int(item.get("page_idx"))
    if page is None:
        page = page_idx
    bbox = item.get("bbox")

    if item_type == "table":
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        html_body = content.get("html") or content.get("table_body") or ""
        caption = _extract_mineru_text(content.get("table_caption"))
        footnote = _extract_mineru_text(content.get("table_footnote"))
        image_path = _extract_mineru_image_path(content) or _extract_mineru_image_path(item)
        text = _html_to_text(html_body)
        combined_text = "\n".join(part for part in (caption, text, footnote) if part)
        block = _base_block(
            doc_id=doc_id,
            source_file=source_file,
            block_index=len(blocks),
            block_type="table",
            parser="mineru_content_list",
            page=page,
            slide=None,
            section=None,
            serving_eligible=bool(combined_text),
            sensitivity_hint="unknown",
            extra={
                "text": combined_text or caption or footnote,
                "table": {
                    "html": html_body,
                    "caption": caption,
                    "footnote": footnote,
                    "image_path": image_path,
                },
                "source_bbox": bbox,
            },
        )
        if image_path:
            block["table_image_ref"] = f"asset://local/{image_path}"
            block["enrichment"] = {
                "local_vlm": {
                    "candidate": True,
                    "executed": False,
                    "reason": "MinerU table has source image; use only for metadata augmentation.",
                }
            }
        blocks.append(block)
        return

    if item_type in {"image", "figure"}:
        image_path = _extract_mineru_image_path(item)
        caption = _extract_mineru_text(item.get("content")) or image_path or "MinerU image block"
        block = _asset_placeholder_block(
            doc_id=doc_id,
            source_file=source_file,
            block_index=len(blocks),
            asset_kind="image",
            caption=caption,
            parser="mineru_content_list",
            page=page,
            sensitivity_hint="unknown",
        )
        if image_path:
            block["asset_ref"] = f"asset://local/{image_path}"
            block["image_path"] = image_path
        block["source_bbox"] = bbox
        blocks.append(block)
        return

    text = _extract_mineru_text(item.get("content")) or item.get("text") or ""
    if not text:
        return
    structure_role = item_type if item_type in {"title", "header", "page_header"} else None
    block = _text_block(
        doc_id=doc_id,
        source_file=source_file,
        block_index=len(blocks),
        text=text,
        parser="mineru_content_list",
        page=page,
        serving_eligible=True,
        sensitivity_hint="unknown",
    )
    block["source_bbox"] = bbox
    if structure_role:
        block["structure_role"] = structure_role
    blocks.append(block)


def _extract_mineru_image_path(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("image_source"), dict):
        return str(value["image_source"].get("path") or "")
    return str(value.get("img_path") or value.get("image_path") or "")


def _extract_mineru_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_extract_mineru_text(item) for item in value) if part)
    if isinstance(value, dict):
        if isinstance(value.get("content"), str):
            return value["content"].strip()
        parts: list[str] = []
        for nested in value.values():
            text = _extract_mineru_text(nested)
            if text:
                parts.append(text)
        return "\n".join(parts)
    return ""


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"</(?:td|th)>", " | ", value, flags=re.IGNORECASE)
    text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [" ".join(line.split()).strip(" |") for line in text.splitlines()]
    return "\n".join(line for line in lines if line)

def _text_block(*, doc_id: str, source_file: str, block_index: int, text: str, parser: str, page: int | None = None, slide: int | None = None, section: str | None = None, serving_eligible: bool, sensitivity_hint: str) -> dict[str, Any]:
    return _base_block(doc_id=doc_id, source_file=source_file, block_index=block_index, block_type="text", parser=parser, page=page, slide=slide, section=section, serving_eligible=serving_eligible, sensitivity_hint=sensitivity_hint, extra={"text": text})


def _table_block(*, doc_id: str, source_file: str, block_index: int, rows: list[list[str]], parser: str, page: int | None = None, slide: int | None = None, section: str | None = None, serving_eligible: bool, sensitivity_hint: str) -> dict[str, Any]:
    text = "\n".join(" | ".join(cell for cell in row) for row in rows)
    return _base_block(doc_id=doc_id, source_file=source_file, block_index=block_index, block_type="table", parser=parser, page=page, slide=slide, section=section, serving_eligible=serving_eligible, sensitivity_hint=sensitivity_hint, extra={"table": {"rows": rows}, "text": text})


def _extract_office_media_asset(
    archive: zipfile.ZipFile,
    archive_name: str,
    *,
    asset_output_root: Path | None,
    doc_id: str,
) -> dict[str, Any] | None:
    if asset_output_root is None:
        return None

    safe_doc_id = _safe_filename(doc_id)
    safe_parts = [
        _safe_filename(part)
        for part in PurePosixPath(archive_name).parts
        if part not in {"", ".", ".."}
    ]
    if not safe_parts:
        return None

    asset_bytes = archive.read(archive_name)
    asset_rel_path = PurePosixPath(safe_doc_id, *safe_parts)
    asset_path = asset_output_root.joinpath(*asset_rel_path.parts)
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(asset_bytes)

    return {
        "asset_ref": f"asset://local/{asset_rel_path.as_posix()}",
        "image_path": asset_rel_path.as_posix(),
        "asset_source_path": archive_name,
        "asset_local_path": str(asset_path),
        "asset_sha256": hashlib.sha256(asset_bytes).hexdigest(),
    }


def _record_office_asset_summary(
    document: dict[str, Any],
    *,
    asset_output_root: Path | None,
) -> None:
    image_blocks = [
        block
        for block in document.get("blocks", [])
        if block.get("block_type") == "image"
    ]
    extracted_blocks = [
        block
        for block in image_blocks
        if block.get("asset_local_path")
    ]
    document.setdefault("normalization", {})["office_assets"] = {
        "asset_output_root": str(asset_output_root) if asset_output_root else None,
        "image_blocks": len(image_blocks),
        "extracted": len(extracted_blocks),
        "extractable_by_vlm": len([
            block for block in extracted_blocks
            if Path(str(block.get("image_path", ""))).suffix.lower() in {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
        ]),
    }


def _asset_placeholder_block(
    *,
    doc_id: str,
    source_file: str,
    block_index: int,
    asset_kind: str,
    caption: str,
    parser: str,
    page: int | None = None,
    slide: int | None = None,
    sensitivity_hint: str,
    asset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    block_type = "asset-placeholder"
    if asset_kind == "image":
        block_type = "image"
    elif asset_kind == "figure-chart":
        block_type = "figure-chart"
    extra: dict[str, Any] = {
        "asset_kind": asset_kind,
        "asset_ref": f"asset://local/{doc_id}/block_{block_index:04d}",
        "caption": caption,
        "needs_review": True,
    }
    if asset:
        extra.update({
            "asset_ref": asset["asset_ref"],
            "image_path": asset["image_path"],
            "asset_source_path": asset["asset_source_path"],
            "asset_local_path": asset["asset_local_path"],
            "asset_sha256": asset["asset_sha256"],
        })
    return _base_block(doc_id=doc_id, source_file=source_file, block_index=block_index, block_type=block_type, parser=parser, page=page, slide=slide, section=None, serving_eligible=False, sensitivity_hint=sensitivity_hint, extra=extra)


def _base_block(*, doc_id: str, source_file: str, block_index: int, block_type: str, parser: str, page: int | None, slide: int | None, section: str | None, serving_eligible: bool, sensitivity_hint: str, extra: dict[str, Any]) -> dict[str, Any]:
    block = {
        "block_id": f"{doc_id}:b{block_index:04d}",
        "block_index": block_index,
        "block_type": block_type,
        "source_anchor": {"source_file": source_file, "page": page, "slide": slide, "section": section, "block_index": block_index},
        "parser": parser,
        "sensitivity_hint": sensitivity_hint,
        "serving_eligible": serving_eligible,
        "retrieval_eligible": serving_eligible,
        "graph_eligible": serving_eligible,
        "needs_review": not serving_eligible or sensitivity_hint in {"high", "unknown"},
    }
    block.update(extra)
    return block


def _apply_unstructured_name_mapping(
    value: Any,
    registry: "NameMappingRegistry",
    *,
    text_match_mode: str,
) -> tuple[Any, dict[str, Any]]:
    if text_match_mode == "configured":
        return registry.apply_text(value, scope="content")
    if text_match_mode != "contains":
        raise ValueError("text_match_mode must be 'contains' or 'configured'")

    summary = {
        "applied": False,
        "replacements": 0,
        "rules": [],
        "qpl_values": [],
        "rule_profiles": [],
    }
    if value is None or not isinstance(value, str) or not value:
        return value, summary

    current = value
    rules = sorted(
        registry.rules_by_scope.get("content", []),
        key=lambda rule: (-len(rule.raw_name), rule.index is None, rule.index or rule.row_number),
    )
    for rule in rules:
        if len(rule.raw_name) < UNSTRUCTURED_NAME_MAPPING_MIN_CONTAINS_LEN:
            continue
        pattern = _compile_contains_pattern(rule.raw_name)
        current, count = pattern.subn(rule.mapped_name, current)
        if not count:
            continue
        summary["applied"] = True
        summary["replacements"] += count
        summary["rules"].append(rule.raw_name)

    return current, summary


def _compile_contains_pattern(raw_name: str) -> re.Pattern[str]:
    escaped = re.escape(raw_name)
    prefix = r"(?<![A-Za-z0-9])" if raw_name[:1].isascii() and raw_name[:1].isalnum() else ""
    suffix = r"(?![A-Za-z0-9])" if raw_name[-1:].isascii() and raw_name[-1:].isalnum() else ""
    return re.compile(f"{prefix}{escaped}{suffix}", flags=re.IGNORECASE)


def _parse_toc_entry(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    if not text or len(text) > 120:
        return None
    match = TOC_ENTRY_RE.match(text)
    if not match:
        return None
    title = match.group("title").strip(" .\t")
    if not title:
        return None
    return {
        "section": match.group("section"),
        "title": title,
        "target_page": int(match.group("target_page")),
    }


def _collect_text(element: ElementTree.Element) -> str:
    values = [node.text or "" for node in element.iter() if _strip_namespace(node.tag) == "t" and node.text]
    return " ".join(value.strip() for value in values if value.strip()).strip()


def _collect_docx_table(table: ElementTree.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.findall(_w_tag("tr")):
        cells = [_collect_text(cell) for cell in row.findall(_w_tag("tc"))]
        if any(cells):
            rows.append(cells)
    return rows


def _collect_pptx_table(table: ElementTree.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.iter():
        if _strip_namespace(row.tag) == "tr":
            cells = [
                _collect_text(cell)
                for cell in row
                if _strip_namespace(cell.tag) == "tc"
            ]
            if any(cells):
                rows.append(cells)
    return rows


def _collect_json_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str) and value.strip():
        strings.append(value.strip())
    elif isinstance(value, dict):
        for nested in value.values():
            strings.extend(_collect_json_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.extend(_collect_json_strings(nested))
    return strings


def _coerce_text(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value).strip() if value is not None else ""
    for key in ("text", "content", "markdown", "html"):
        if value.get(key):
            return str(value[key]).strip()
    return ""


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _make_doc_id(source_path: Path) -> str:
    digest = _file_sha256(source_path)[:12] if source_path.exists() else "missing"
    return f"{_safe_filename(_strip_mineru_output_suffix(source_path.stem))}_{digest}"


def _strip_mineru_output_suffix(stem: str) -> str:
    for suffix in ("_content_list_v2", "_content_list", "_middle", "_model", "_origin", "_span", "_layout"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "document"


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _w_tag(name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{name}"


def _slide_sort_key(name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0
