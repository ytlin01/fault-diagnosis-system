from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from services.ingestion.cad_2d_pipeline_v2 import load_config
from services.ingestion.cad_2d_pipeline_v2.artifacts import sha256_value


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNNER = PROJECT_ROOT / "scripts" / "pipelines" / "cad_2d_v2" / "run_stage.py"
CONFIG = PROJECT_ROOT / "configs" / "pipelines" / "cad_2d_pipeline_v2.yaml"


class Cad2dCliTests(unittest.TestCase):
    def test_combined_b01_rejects_self_consistent_forged_b00(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cfg = load_config(CONFIG)
            index = [{"part_number": "ASM-1", "drawing_type": "ASM"}]
            bundle = {
                "schema_version": "cad_2d_reviewed_asm_words_v1",
                "records": [{
                    "part_number": "ASM-1",
                    "source_pdf_sha256": "a" * 64,
                    "page_index": 0,
                    "page_count": 1,
                    "extraction_state": "local_reviewed_asm_word_geometry",
                    "words": [],
                }],
                "audit": {
                    "stage": "B00",
                    "raw_zone_content_accessed": False,
                    "processed_pdf_content_accessed": True,
                    "output_document_count": 1,
                },
                "exclusions": [],
            }
            lineage = cfg["bom"]["reviewed_word_bundle_lineage"]
            manifest = {
                "manifest_version": "cad-2d-run-v1",
                "stage": "B00",
                "graph_activation": False,
                "promotion_state": "candidate",
                "config_schema_version": cfg["schema_version"],
                "config_sha256": sha256_value(cfg),
                "result_sha256": sha256_value(bundle),
                "input_sha256": {
                    "source_review_sha256": sha256_value(
                        lineage["source_review_file_sha256"]
                    ),
                    "projection_sha256": sha256_value(
                        lineage["projection_file_sha256"]
                    ),
                    "page_index": sha256_value(cfg["bom"]["page_index"]),
                },
            }
            paths = {
                "index.json": index,
                "historical.json": {},
                "words.json": bundle,
                "manifest.json": manifest,
            }
            for name, value in paths.items():
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, str(RUNNER), "B01", "--config", str(CONFIG),
                    "--primary", str(root / "index.json"),
                    "--secondary", str(root / "historical.json"),
                    "--tertiary", str(root / "words.json"),
                    "--tertiary-manifest", str(root / "manifest.json"),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("lineage is not governed", completed.stderr)

    def test_combined_b01_rejects_unattributed_word_bundle_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            index = root / "index.json"
            historical = root / "historical.json"
            words = root / "words.json"
            index.write_text(
                json.dumps([{"part_number": "ASM-1", "drawing_type": "ASM"}]),
                encoding="utf-8",
            )
            historical.write_text("{}", encoding="utf-8")
            words.write_text(
                json.dumps({
                    "records": [],
                    "audit": {},
                    "exclusions": [{"reason_code": "BOM_PAGE_UNAVAILABLE"}],
                }),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "B01",
                    "--config",
                    str(CONFIG),
                    "--primary",
                    str(index),
                    "--secondary",
                    str(historical),
                    "--tertiary",
                    str(words),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("requires a governed B00 word bundle", completed.stderr)

    def test_preview_then_exclusive_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reviewed = root / "reviewed.json"
            full = root / "full.json"
            output = root / "candidate.json"
            manifest = root / "manifest.json"
            reviewed.write_text("[]", encoding="utf-8")
            full.write_text(
                json.dumps([{"part_number": "SYNTH-ASM-1", "decision": "ASM"}]),
                encoding="utf-8",
            )
            base = [
                sys.executable,
                str(RUNNER),
                "A01",
                "--config",
                str(CONFIG),
                "--primary",
                str(reviewed),
                "--secondary",
                str(full),
                "--out",
                str(output),
                "--manifest-out",
                str(manifest),
            ]
            preview = subprocess.run(
                base,
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertFalse(output.exists())
            self.assertIn('"mode": "preview"', preview.stdout)

            written = subprocess.run(
                base + ["--write"],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertTrue(output.exists())
            self.assertTrue(manifest.exists())
            self.assertFalse(json.loads(manifest.read_text(encoding="utf-8"))["graph_activation"])

            repeated = subprocess.run(
                base + ["--write"],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("FileExistsError", repeated.stderr)

    def test_manifest_collision_does_not_leave_orphan_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reviewed = root / "reviewed.json"
            full = root / "full.json"
            output = root / "candidate.json"
            manifest = root / "manifest.json"
            reviewed.write_text("[]", encoding="utf-8")
            full.write_text(
                json.dumps([{"part_number": "SYNTH-ASM-1", "decision": "ASM"}]),
                encoding="utf-8",
            )
            manifest.write_text("{}", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "A01",
                    "--config",
                    str(CONFIG),
                    "--primary",
                    str(reviewed),
                    "--secondary",
                    str(full),
                    "--out",
                    str(output),
                    "--manifest-out",
                    str(manifest),
                    "--write",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertFalse(output.exists())

    def test_b02_c01_c02_preview_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            values = {
                "index.json": [
                    {"part_number": "ASM-1", "drawing_type": "ASM"},
                    {"part_number": "PRT-1", "drawing_type": "PRT"},
                ],
                "bom.json": [{
                    "parent_part_number": "ASM-1",
                    "rows": [{"item_no": "1", "part_number": "PRT-1", "quantity": 1}],
                }],
                "findings.json": [],
                "relations.json": [{
                    "parent_asm_part_number": "ASM-1",
                    "child_part_number": "PRT-1",
                    "item_no": "1",
                    "quantity": 1,
                    "description": "",
                    "child_semantics": "confirmed_prt_child",
                }],
            }
            for name, value in values.items():
                (root / name).write_text(json.dumps(value), encoding="utf-8")

            commands = [
                ["B02", "--primary", str(root / "index.json"), "--secondary", str(root / "bom.json")],
                [
                    "C01",
                    "--primary", str(root / "index.json"),
                    "--secondary", str(root / "bom.json"),
                    "--tertiary", str(root / "findings.json"),
                ],
                ["C02", "--primary", str(root / "index.json"), "--secondary", str(root / "relations.json")],
            ]
            for arguments in commands:
                completed = subprocess.run(
                    [sys.executable, str(RUNNER), *arguments, "--config", str(CONFIG)],
                    cwd=PROJECT_ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn('"mode": "preview"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
