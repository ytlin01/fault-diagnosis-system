from __future__ import annotations

import argparse
import tempfile
import unittest
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from services.ingestion.canonical_document import (
    build_canonical_document,
    build_synthetic_canonical_document,
)
from services.ingestion.local_vlm import collect_local_vlm_targets
from services.ingestion.unstructured import (
    MaskingPattern,
    build_serving_payload,
    mask_json_value,
    sanitize_masked_canonical_payload,
)
from scripts.ingest.run_mask_unstructured import (
    _output_path,
    _resolve_output_dirs,
)


@dataclass(frozen=True)
class FakeRule:
    raw_name: str
    mapped_name: str
    index: int | None = 1
    row_number: int = 2


class FakeNameMappingRegistry:
    path = Path("local/name_mapping.xlsx")

    def __init__(self) -> None:
        self.rules_by_scope = {
            "content": [
                FakeRule("legacy_station", "C1STN", index=1, row_number=2),
                FakeRule("CGSF1", "C1STN", index=2, row_number=3),
                FakeRule("CGSF", "C1STN", index=3, row_number=4),
            ]
        }

    def apply_text(self, value, *, scope: str):
        return value, {
            "applied": False,
            "replacements": 0,
            "rules": [],
            "qpl_values": [],
            "rule_profiles": [],
        }


class UnstructuredIngestionTests(unittest.TestCase):
    def _temp_dir(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_synthetic_document_covers_required_block_types(self) -> None:
        document = build_synthetic_canonical_document()
        block_types = {block["block_type"] for block in document["blocks"]}
        asset_kinds = {block.get("asset_kind") for block in document["blocks"]}

        self.assertIn("text", block_types)
        self.assertIn("table", block_types)
        self.assertIn("image", block_types)
        self.assertIn("figure-chart", block_types)
        self.assertIn("3d_model_or_3d_view", asset_kinds)
        self.assertTrue(any(
            block.get("enrichment", {}).get("local_vlm", {}).get("candidate")
            for block in document["blocks"]
        ))

    def test_text_ingestion_applies_name_mapping_as_contains_after_reading(self) -> None:
        temp_dir = self._temp_dir()
        text_path = temp_dir / "demo.txt"
        text_path.write_text("Alarm at legacy_station and CGSF1\n", encoding="utf-8")

        document = build_canonical_document(
            text_path,
            source_root=temp_dir,
            name_mapping_registry=FakeNameMappingRegistry(),
        )

        self.assertEqual(document["source"]["route"], "native_text")
        self.assertIn("C1STN", document["blocks"][0]["text"])
        self.assertNotIn("C1STN1", document["blocks"][0]["text"])
        self.assertEqual(document["normalization"]["name_mapping"]["replacements"], 2)
        self.assertEqual(document["normalization"]["name_mapping"]["text_match_mode"], "contains")

    def test_toc_entry_is_kept_but_excluded_from_retrieval_graph_and_serving(self) -> None:
        document = build_synthetic_canonical_document()
        toc_block = next(block for block in document["blocks"] if block.get("structure_role") == "toc_entry")

        self.assertEqual(toc_block["toc_entry"]["section"], "1.3.1")
        self.assertEqual(toc_block["toc_entry"]["target_page"], 8)
        self.assertFalse(toc_block["serving_eligible"])
        self.assertFalse(toc_block["retrieval_eligible"])
        self.assertFalse(toc_block["graph_eligible"])
        self.assertEqual(document["normalization"]["structure_detection"]["toc_entries"], 1)

    def test_3d_asset_is_registered_as_placeholder(self) -> None:
        temp_dir = self._temp_dir()
        asset_path = temp_dir / "fixture.step"
        asset_path.write_text("ISO-10303-21;", encoding="utf-8")

        document = build_canonical_document(asset_path, source_root=temp_dir)
        block = document["blocks"][0]

        self.assertEqual(document["source"]["route"], "three_d_asset_placeholder")
        self.assertEqual(block["block_type"], "asset-placeholder")
        self.assertEqual(block["asset_kind"], "3d_model_or_3d_view")
        self.assertFalse(block["serving_eligible"])
        self.assertTrue(block["needs_review"])

    def test_docx_embedded_image_is_extracted_to_resolvable_asset(self) -> None:
        temp_dir = self._temp_dir()
        docx_path = temp_dir / "demo.docx"
        asset_root = temp_dir / "assets"
        with zipfile.ZipFile(docx_path, "w") as archive:
            archive.writestr(
                "word/document.xml",
                (
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    "<w:body><w:p><w:r><w:t>Demo</w:t></w:r></w:p></w:body></w:document>"
                ),
            )
            archive.writestr("word/media/image1.png", b"fake-png")

        document = build_canonical_document(
            docx_path,
            source_root=temp_dir,
            asset_output_root=asset_root,
        )
        image_block = next(block for block in document["blocks"] if block["block_type"] == "image")
        targets = collect_local_vlm_targets(document, asset_roots=[asset_root], limit=1)

        self.assertEqual(document["normalization"]["office_assets"]["extracted"], 1)
        self.assertTrue(image_block["asset_ref"].startswith("asset://local/demo_"))
        self.assertTrue(image_block["asset_ref"].endswith("/word/media/image1.png"))
        self.assertTrue(Path(image_block["asset_local_path"]).is_file())
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].resolved_image_path, str(Path(image_block["asset_local_path"]).resolve()))

    def test_mineru_content_list_v2_keeps_table_image_ref_in_single_document(self) -> None:
        temp_dir = self._temp_dir()
        content_path = temp_dir / "HIVE Error Code_content_list_v2.json"
        content_path.write_text(
            json.dumps(
                [
                    [
                        {"type": "page_header", "content": "HIVE Error Code"},
                        {
                            "type": "table",
                            "content": {
                                "html": "<table><tr><td>Error</td><td>Action</td></tr></table>",
                                "image_source": {"path": "images/table_1.jpg"},
                            },
                            "bbox": [1, 2, 3, 4],
                        },
                    ]
                ]
            ),
            encoding="utf-8",
        )

        document = build_canonical_document(content_path, source_root=temp_dir)
        table_block = next(block for block in document["blocks"] if block["block_type"] == "table")

        self.assertTrue(document["doc_id"].startswith("HIVE_Error_Code_"))
        self.assertNotIn("content_list_v2", document["doc_id"])
        self.assertEqual(document["normalization"]["mineru"]["source_format"], "content_list")
        self.assertIn("Error | Action", table_block["text"])
        self.assertEqual(table_block["table"]["image_path"], "images/table_1.jpg")
        self.assertEqual(table_block["table_image_ref"], "asset://local/images/table_1.jpg")
        self.assertTrue(table_block["enrichment"]["local_vlm"]["candidate"])

    def test_serving_payload_filters_ineligible_blocks_after_masking(self) -> None:
        document = build_synthetic_canonical_document()
        document["blocks"][0]["text"] = "Contact owner test@example.com for reset."
        patterns = [
            MaskingPattern(
                name="email",
                regex=r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
                action="redact",
                replacement="[EMAIL_REDACTED]",
            )
        ]

        masked, records = mask_json_value(document, patterns)
        serving, policy = build_serving_payload(masked)

        self.assertEqual(records[0]["matches"], 1)
        self.assertIsNotNone(serving)
        self.assertTrue(policy["serving_generated"])
        self.assertGreater(policy["blocks_dropped"], 0)
        self.assertEqual(len(serving["blocks"]), 2)
        self.assertIn("[EMAIL_REDACTED]", serving["blocks"][0]["text"])

    def test_canonical_sanitization_drops_raw_vlm_debug_fields(self) -> None:
        document = _document_with_vlm_enrichment()

        sanitized, policy = sanitize_masked_canonical_payload(document)
        local_vlm = sanitized["blocks"][0]["enrichment"]["local_vlm"]

        self.assertTrue(policy["applied"])
        self.assertEqual(policy["fields_dropped"]["raw_response"], 1)
        self.assertEqual(policy["fields_dropped"]["resolved_image_path"], 1)
        self.assertIn("response_text", local_vlm)
        self.assertIn("response_metrics", local_vlm)
        self.assertNotIn("raw_response", local_vlm)
        self.assertNotIn("resolved_image_path", local_vlm)

    def test_serving_payload_removes_vlm_response_and_asset_paths(self) -> None:
        document, _ = sanitize_masked_canonical_payload(_document_with_vlm_enrichment())

        serving, policy = build_serving_payload(document)
        serving_block = serving["blocks"][0]
        local_vlm = serving_block["enrichment"]["local_vlm"]

        self.assertTrue(policy["serving_generated"])
        self.assertNotIn("table_image_ref", serving_block)
        self.assertNotIn("asset_ref", serving_block)
        self.assertNotIn("image_path", serving_block["table"])
        self.assertNotIn("response_text", local_vlm)
        self.assertNotIn("response_metrics", local_vlm)
        self.assertNotIn("provider", local_vlm)
        self.assertNotIn("endpoint", local_vlm)
        self.assertTrue(local_vlm["response_removed_from_serving"])
        self.assertEqual(local_vlm["status"], "ok")
        self.assertEqual(
            serving["serving_policy"]["sanitization"]["local_vlm_response_removed"],
            1,
        )
        self.assertEqual(policy["sanitization"]["local_vlm_response_removed"], 1)

    def test_serving_payload_keeps_serving_safe_vlm_text_for_image_blocks(self) -> None:
        document, _ = sanitize_masked_canonical_payload(_image_document_with_vlm_enrichment())

        serving, policy = build_serving_payload(document)
        self.assertIsNotNone(serving)
        self.assertTrue(policy["serving_generated"])
        self.assertEqual(policy["derived_vlm_text_blocks"], 1)

        serving_block = serving["blocks"][0]
        self.assertEqual(serving_block["block_type"], "vlm_text")
        self.assertEqual(serving_block["derived_from_block_type"], "image")
        self.assertEqual(serving_block["derived_from_block_id"], "demo:b0002")
        self.assertTrue(serving_block["block_id"].endswith(":vlm_text"))
        self.assertTrue(serving_block["retrieval_eligible"])
        self.assertTrue(serving_block["graph_eligible"])
        self.assertIn("Visual summary: Warning label beside the pneumatic fixture.", serving_block["text"])
        self.assertIn("Extracted text: 注意", serving_block["text"])
        self.assertIn("Candidate entities: yellow warning label; pneumatic fixture", serving_block["text"])
        self.assertNotIn("asset_ref", serving_block)
        self.assertNotIn("image_path", serving_block)
        self.assertTrue(serving_block["asset_removed_from_serving"])

        local_vlm = serving_block["enrichment"]["local_vlm"]
        self.assertNotIn("response_text", local_vlm)
        self.assertNotIn("response_metrics", local_vlm)
        self.assertNotIn("endpoint", local_vlm)
        self.assertNotIn("provider", local_vlm)
        self.assertTrue(local_vlm["response_removed_from_serving"])
        self.assertEqual(local_vlm["status"], "ok")
        self.assertEqual(serving["serving_policy"]["derived_vlm_text_blocks"], 1)
        self.assertEqual(
            serving["serving_policy"]["sanitization"]["local_vlm_response_removed"],
            1,
        )

    def test_vlm_masking_defaults_use_dedicated_output_dirs_and_names(self) -> None:
        input_file = Path("data/processed/unstructured_vlm/demo_canonical_vlm.json")
        args = argparse.Namespace(
            canonical_output_dir=None,
            serving_output_dir=None,
        )

        canonical_dir, serving_dir = _resolve_output_dirs(args, [input_file])
        canonical_path = _output_path(
            canonical_dir,
            input_file,
            suffix="canonical",
            source_format="json",
        )
        serving_path = _output_path(
            serving_dir,
            input_file,
            suffix="serving",
            source_format="json",
        )

        self.assertTrue(str(canonical_dir).endswith("data\\processed\\masked\\unstructured\\vlm") or str(canonical_dir).endswith("data/processed/masked/unstructured/vlm"))
        self.assertTrue(str(serving_dir).endswith("data\\processed\\serving\\unstructured") or str(serving_dir).endswith("data/processed/serving/unstructured"))
        self.assertEqual(canonical_path.name, "demo_vlm_masked_canonical.json")
        self.assertEqual(serving_path.name, "demo_vlm_masked_serving.json")

    def test_base_canonical_masking_defaults_use_masked_output_dir(self) -> None:
        input_file = Path("data/processed/unstructured/demo_canonical.json")
        args = argparse.Namespace(
            canonical_output_dir=None,
            serving_output_dir=None,
        )

        canonical_dir, serving_dir = _resolve_output_dirs(args, [input_file])
        canonical_path = _output_path(
            canonical_dir,
            input_file,
            suffix="canonical",
            source_format="json",
        )

        self.assertTrue(str(canonical_dir).endswith("data\\processed\\masked\\unstructured") or str(canonical_dir).endswith("data/processed/masked/unstructured"))
        self.assertTrue(str(serving_dir).endswith("data\\processed\\serving\\unstructured") or str(serving_dir).endswith("data/processed/serving/unstructured"))
        self.assertEqual(canonical_path.name, "demo_masked_canonical.json")


def _document_with_vlm_enrichment() -> dict:
    return {
        "schema_version": "unstructured_canonical_v1",
        "doc_id": "demo",
        "source": {"file": "demo.pdf", "route": "mineru_json_or_canonical"},
        "blocks": [
            {
                "block_id": "demo:b0001",
                "block_index": 1,
                "block_type": "table",
                "serving_eligible": True,
                "text": "Owner Debo, repair action adjusted.",
                "asset_ref": "asset://local/images/table.jpg",
                "table_image_ref": "asset://local/images/table.jpg",
                "table": {
                    "html": "<table><tr><td>Owner Debo</td></tr></table>",
                    "image_path": "images/table.jpg",
                },
                "enrichment": {
                    "local_vlm": {
                        "candidate": True,
                        "executed": True,
                        "status": "ok",
                        "metadata_only": True,
                        "provider": "ollama",
                        "model": "qwen2.5vl:7b",
                        "endpoint": "http://localhost:11434",
                        "prompt_contract": "metadata augmentation only; not final MappingRecord",
                        "image_ref": "asset://local/images/table.jpg",
                        "resolved_image_path": "D:\\private\\images\\table.jpg",
                        "response_text": '{"DRI":"Debo"}',
                        "response_metrics": {"done": True},
                        "raw_response": {"context": [1, 2, 3]},
                    }
                },
            }
        ],
    }


def _image_document_with_vlm_enrichment() -> dict:
    return {
        "schema_version": "unstructured_canonical_v1",
        "doc_id": "demo",
        "source": {"file": "demo.pdf", "route": "mineru_json_or_canonical"},
        "blocks": [
            {
                "block_id": "demo:b0002",
                "block_index": 2,
                "block_type": "image",
                "serving_eligible": False,
                "retrieval_eligible": False,
                "graph_eligible": False,
                "needs_review": True,
                "parser": "native_docx",
                "sensitivity_hint": "unknown",
                "source_anchor": {
                    "source_file": "demo.pdf",
                    "page": 2,
                    "slide": None,
                    "section": "safety",
                    "block_index": 2,
                },
                "text": "",
                "asset_ref": "asset://local/images/warning.png",
                "asset_local_path": "D:\\private\\images\\warning.png",
                "enrichment": {
                    "local_vlm": {
                        "candidate": True,
                        "executed": True,
                        "status": "ok",
                        "metadata_only": True,
                        "provider": "ollama",
                        "model": "qwen2.5vl:7b",
                        "endpoint": "http://localhost:11434",
                        "prompt_contract": "metadata augmentation only; not final MappingRecord",
                        "image_ref": "asset://local/images/warning.png",
                        "resolved_image_path": "D:\\private\\images\\warning.png",
                        "response_text": "```json\n"
                        + json.dumps(
                            {
                                "image_summary": "Warning label beside the pneumatic fixture.",
                                "extracted_text": "注意",
                                "candidate_entities": [
                                    "yellow warning label",
                                    "pneumatic fixture",
                                ],
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n```",
                        "response_metrics": {"done": True},
                        "raw_response": {"context": [7, 8, 9]},
                    }
                },
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
