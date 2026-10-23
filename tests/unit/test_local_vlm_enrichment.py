from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ingest.run_enrich_unstructured_vlm import _apply_config_defaults
from services.ingestion.local_vlm import (
    build_local_vlm_prompt,
    collect_local_vlm_targets,
    enrich_document_with_local_vlm,
)


class FakeLocalVlmClient:
    model = "fake-vlm"
    endpoint = "local-test"

    def generate(self, *, image_path: Path, prompt: str):
        return {
            "provider": "fake",
            "model": self.model,
            "endpoint": self.endpoint,
            "duration_ms": 1,
            "response": '{"image_summary":"ok"}',
            "raw": {"response": '{"image_summary":"ok"}'},
        }


class LocalVlmEnrichmentTests(unittest.TestCase):
    def _temp_dir(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_collect_targets_resolves_mineru_table_image_under_source_parent(self) -> None:
        temp_dir = self._temp_dir()
        image_path = temp_dir / "HIVE Error Code" / "auto" / "images" / "table.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"fake-image")
        document = _document_with_table_image()

        targets = collect_local_vlm_targets(
            document,
            asset_roots=[temp_dir],
            limit=1,
        )

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].block_id, "demo:b0001")
        self.assertEqual(targets[0].resolved_image_path, str(image_path.resolve()))

    def test_enrich_document_attaches_metadata_without_rewriting_block_text(self) -> None:
        temp_dir = self._temp_dir()
        image_path = temp_dir / "HIVE Error Code" / "auto" / "images" / "table.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"fake-image")
        document = _document_with_table_image()

        enriched = enrich_document_with_local_vlm(
            document,
            client=FakeLocalVlmClient(),
            asset_roots=[temp_dir],
            limit=1,
        )
        local_vlm = enriched["blocks"][0]["enrichment"]["local_vlm"]

        self.assertEqual(enriched["blocks"][0]["text"], "Existing table OCR")
        self.assertTrue(local_vlm["executed"])
        self.assertEqual(local_vlm["status"], "ok")
        self.assertEqual(local_vlm["response_text"], '{"image_summary":"ok"}')
        self.assertNotIn("raw_response", local_vlm)
        self.assertEqual(local_vlm["response_metrics"]["done"], None)
        self.assertTrue(enriched["normalization"]["local_vlm"]["metadata_only"])

    def test_enrich_document_can_keep_raw_response_for_debug_when_requested(self) -> None:
        temp_dir = self._temp_dir()
        image_path = temp_dir / "HIVE Error Code" / "auto" / "images" / "table.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"fake-image")
        document = _document_with_table_image()

        enriched = enrich_document_with_local_vlm(
            document,
            client=FakeLocalVlmClient(),
            asset_roots=[temp_dir],
            limit=1,
            include_raw_response=True,
        )
        local_vlm = enriched["blocks"][0]["enrichment"]["local_vlm"]

        self.assertIn("raw_response", local_vlm)

    def test_prompt_contains_existing_text_and_metadata_contract(self) -> None:
        prompt = build_local_vlm_prompt(_document_with_table_image()["blocks"][0])

        self.assertIn("metadata", prompt.lower())
        self.assertIn("Existing table OCR", prompt)
        self.assertIn("demo:b0001", prompt)

    def test_config_profile_supplies_e3_runtime_defaults(self) -> None:
        temp_dir = self._temp_dir()
        config_path = temp_dir / "local_vlm.yaml"
        config_path.write_text(
            "\n".join([
                "version: 1",
                "default_profile: e2a",
                "profiles:",
                "  e2a:",
                "    model: qwen2.5vl:7b",
                "    endpoint: http://localhost:11434",
                "    asset_roots:",
                "      - data/processed/unstructured_assets",
                "    limit: 3",
                "    timeout_seconds: 180",
                "  e3:",
                "    model: qwen2.5vl:32b",
                "    endpoint: http://localhost:11434",
                "    ollama_models_dir: /models/e3",
                "    startup_command: ollama serve",
                "    asset_roots:",
                "      - data/processed/unstructured_assets",
                "    limit: 0",
                "    timeout_seconds: 300",
                "    existing_text_limit: 1200",
            ]),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            config=str(config_path),
            profile="e3",
            model=None,
            endpoint=None,
            output_dir=None,
            asset_root=None,
            prompt_file=None,
            limit=None,
            timeout_seconds=None,
            existing_text_limit=None,
            allow_non_local_endpoint=None,
        )

        with patch.dict(os.environ, {}, clear=True):
            resolved = _apply_config_defaults(args)

        self.assertEqual(resolved.profile, "e3")
        self.assertEqual(resolved.model, "qwen2.5vl:32b")
        self.assertEqual(resolved.limit, 0)
        self.assertEqual(resolved.timeout_seconds, 300)
        self.assertEqual(resolved.ollama_models_dir, "/models/e3")
        self.assertEqual(resolved.startup_command, "ollama serve")
        self.assertTrue(resolved.asset_roots[0].endswith("data\\processed\\unstructured_assets") or resolved.asset_roots[0].endswith("data/processed/unstructured_assets"))


def _document_with_table_image() -> dict:
    return {
        "schema_version": "unstructured_canonical_v1",
        "doc_id": "demo",
        "source": {
            "file": "HIVE Error Code\\auto\\HIVE Error Code_content_list_v2.json",
        },
        "blocks": [
            {
                "block_id": "demo:b0001",
                "block_index": 1,
                "block_type": "table",
                "source_anchor": {
                    "source_file": "HIVE Error Code\\auto\\HIVE Error Code_content_list_v2.json",
                    "page": 3,
                },
                "text": "Existing table OCR",
                "table": {
                    "image_path": "images/table.jpg",
                },
                "table_image_ref": "asset://local/images/table.jpg",
                "enrichment": {
                    "local_vlm": {
                        "candidate": True,
                        "executed": False,
                    }
                },
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
