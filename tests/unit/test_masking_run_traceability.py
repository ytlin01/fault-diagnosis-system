from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.ingest.run_mask_structured import _resolve_governance_ids
from services.governance import masking_log
from services.governance.storage import read_jsonl_rows
from services.ingestion.lineage import LineageWriter
from services.ingestion.manifest import build_manifest, write_manifest


class MaskingRunTraceabilityTests(unittest.TestCase):
    def test_run_id_joins_manifest_lineage_and_governance_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "input.csv"
            input_path.write_text("field\nvalue\n", encoding="utf-8")
            run_id = "maskrun_20260723T120000Z_12345678"

            lineage_dir = root / "_lineage"
            with LineageWriter("demo", lineage_dir, run_id=run_id) as writer:
                writer.record(
                    row_index=0,
                    column_name="field",
                    level="C",
                    action="passthrough",
                    detail="passthrough",
                    view="canonical",
                )
            lineage_path = writer.path

            manifest = build_manifest(
                run_id=run_id,
                source_name="demo",
                rules_version=4,
                input_files=[input_path],
                input_file_labels=["input.csv"],
                input_row_count=1,
                input_col_count=1,
                output_canonical_path="data/processed/demo.json",
                output_serving_path="data/processed/serving/demo.json",
                output_row_count=1,
                output_col_count_canonical=1,
                output_col_count_serving=1,
            )
            manifest_path = write_manifest(manifest, root / "_manifests")

            governance_dir = root / "governance"
            masking_log.record(
                source_id="raw-demo",
                run_id=run_id,
                masking_source_name="demo",
                input_source_id="raw-demo",
                canonical_source_id="canonical-demo",
                serving_source_id="serving-demo",
                rules_version=4,
                masking_action="structured_masking",
                input_path="data/raw/input.csv",
                output_canonical_path="data/processed/demo.json",
                output_serving_path="data/processed/serving/demo.json",
                manifest_path="_manifests/" + manifest_path.name,
                lineage_path="_lineage/" + lineage_path.name,
                operator="tester",
                governance_dir=governance_dir,
            )

            manifest_record = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            lineage_record = json.loads(
                lineage_path.read_text(encoding="utf-8").splitlines()[0]
            )
            governance_record = read_jsonl_rows(
                governance_dir / "masking_log.jsonl"
            )[0]

            self.assertEqual(manifest_record["run_id"], run_id)
            self.assertEqual(lineage_record["run_id"], run_id)
            self.assertEqual(governance_record["run_id"], run_id)
            self.assertNotIn("hostname", manifest_record)
            self.assertEqual(
                governance_record["canonical_source_id"],
                "canonical-demo",
            )
            self.assertEqual(
                governance_record["serving_source_id"],
                "serving-demo",
            )
            with self.assertRaisesRegex(
                FileExistsError,
                "Refusing to overwrite masking run manifest",
            ):
                write_manifest(manifest, root / "_manifests")

            with self.assertRaisesRegex(
                FileExistsError,
                "Refusing to overwrite masking run lineage",
            ):
                LineageWriter("demo", lineage_dir, run_id=run_id).open()

    def test_governance_ids_are_complete_when_configured(self) -> None:
        identifiers = _resolve_governance_ids(
            "demo",
            {
                "governance_ids": {
                    "input_source_id": "raw-demo",
                    "canonical_source_id": "canonical-demo",
                    "serving_source_id": "serving-demo",
                }
            },
        )
        self.assertEqual(identifiers["input_source_id"], "raw-demo")

        with self.assertRaisesRegex(ValueError, "incomplete governance_ids"):
            _resolve_governance_ids(
                "demo",
                {
                    "governance_ids": {
                        "input_source_id": "raw-demo",
                    }
                },
            )


if __name__ == "__main__":
    unittest.main()
