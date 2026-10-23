from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

try:
    import pymupdf
except ModuleNotFoundError:  # pragma: no cover
    pymupdf = None

from services.ingestion.cad_2d_pipeline_v2.redaction import (
    MASK_RECTS,
    redact_pdf,
    verify_redacted_pdf,
)
from scripts.pipelines.cad_2d_v2 import redact_black_strip_pdfs


@unittest.skipIf(pymupdf is None, "PyMuPDF redaction dependency is unavailable")
class DestructiveRedactionTests(unittest.TestCase):
    def test_raw_cli_requires_explicit_bounded_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit --input-dir"):
            redact_black_strip_pdfs.main(["--input-zone", "raw"])

    def test_raw_cli_preview_accepts_only_raw_zone_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            source_root = repository_root / "data" / "raw" / "drawings"
            output_root = repository_root / "data" / "processed" / "direct"
            source_root.mkdir(parents=True)
            (repository_root / "data" / "processed").mkdir(parents=True)
            document = pymupdf.open()
            document.new_page(width=1190.55, height=841.89)
            document.save(source_root / "synthetic.pdf")
            document.close()

            stdout = io.StringIO()
            with patch.object(
                redact_black_strip_pdfs, "PROJECT_ROOT", repository_root
            ), redirect_stdout(stdout):
                result = redact_black_strip_pdfs.main(
                    [
                        "--input-zone",
                        "raw",
                        "--input-dir",
                        str(source_root),
                        "--output-dir",
                        str(output_root),
                        "--inventory-out",
                        str(output_root / "_lineage" / "inventory.json"),
                        "--manifest-out",
                        str(output_root / "_manifests" / "manifest.json"),
                    ]
                )

            preview = json.loads(stdout.getvalue())
            self.assertEqual(result, 0)
            self.assertEqual(preview["input_zone"], "raw")
            self.assertFalse(preview["raw_content_accessed"])
            self.assertFalse(output_root.exists())

            processed_input = repository_root / "data" / "processed" / "input"
            processed_input.mkdir()
            with patch.object(
                redact_black_strip_pdfs, "PROJECT_ROOT", repository_root
            ), self.assertRaisesRegex(ValueError, "raw redaction inputs"):
                redact_black_strip_pdfs.main(
                    [
                        "--input-zone",
                        "raw",
                        "--input-dir",
                        str(processed_input),
                    ]
                )

    def test_redacts_raw_pdf_without_visual_overlay_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw.pdf"
            output = root / "redacted.pdf"
            document = pymupdf.open()
            page = document.new_page(width=1190.55, height=841.89)
            page.insert_text((730, 755), "SYNTHETIC RAW SECRET")
            document.save(source)
            document.close()

            result = redact_pdf(source, output)

            self.assertGreater(result["words_intersecting_before"], 0)
            self.assertTrue(result["verification"]["passed"])
            self.assertEqual(
                result["verification"]["words_intersecting_redactions"], 0
            )
            self.assertGreaterEqual(
                result["verification"]["minimum_redaction_black_ratio"], 0.98
            )

    def test_redaction_removes_text_and_scrubs_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "overlay.pdf"
            output = root / "redacted.pdf"
            document = pymupdf.open()
            page = document.new_page(width=1190.55, height=841.89)
            page.insert_text((730, 755), "SYNTHETIC SECRET PROJECT")
            for coordinates in MASK_RECTS:
                page.draw_rect(
                    pymupdf.Rect(coordinates), color=(0, 0, 0), fill=(0, 0, 0)
                )
            document.set_metadata({"author": "synthetic-author"})
            document.embfile_add("synthetic.txt", b"synthetic attachment")
            document.save(source)
            document.close()

            result = redact_pdf(source, output)
            self.assertGreater(result["words_intersecting_before"], 0)
            self.assertEqual(
                result["verification"]["words_intersecting_redactions"], 0
            )
            self.assertEqual(result["verification"]["embedded_file_count"], 0)
            self.assertEqual(result["verification"]["metadata_value_count"], 0)
            self.assertGreaterEqual(
                result["verification"]["minimum_redaction_black_ratio"], 0.98
            )
            self.assertTrue(result["verification"]["passed"])
            self.assertEqual(verify_redacted_pdf(output), result["verification"])

    def test_never_overwrites_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            output = root / "output.pdf"
            document = pymupdf.open()
            document.new_page(width=1190.55, height=841.89)
            document.save(source)
            document.close()
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                redact_pdf(source, output)


if __name__ == "__main__":
    unittest.main()
