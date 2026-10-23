from pathlib import Path
import unittest

from services.ingestion.cad_2d_pipeline_v2.review_queue import (
    build_manual_classification_records,
    normalized_pdf_identifier,
)


class ManualClassificationReviewTests(unittest.TestCase):
    def test_builds_only_unclassified_records_in_stable_order(self) -> None:
        records = build_manual_classification_records(
            [{"part_number": "P-002", "decision": "prt"}],
            {
                "P-003": {"drawing_title": "Third", "project_name": None},
                "P-001": {"drawing_title": None, "project_name": "Pilot"},
                "P-002": {"drawing_title": "Second", "project_name": "Pilot"},
            },
            [
                Path("masked_2d/P-003_masked_redacted.pdf"),
                Path("masked_2d/P-001_masked_redacted.pdf"),
                Path("masked_2d/P-002_masked_redacted.pdf"),
            ],
        )

        self.assertEqual([record["part_number"] for record in records], ["P-001", "P-003"])
        self.assertTrue(all(record["decision"] is None for record in records))
        self.assertEqual(records[0]["source_partition"], "masked_2d")

    def test_rejects_missing_or_ambiguous_pdf(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one governed PDF"):
            build_manual_classification_records([], {"P-001": {}}, [])
        with self.assertRaisesRegex(ValueError, "exactly one governed PDF"):
            build_manual_classification_records(
                [],
                {"P-001": {}},
                [Path("a/P-001_masked.pdf"), Path("b/P-001_redacted.pdf")],
            )

    def test_normalizes_masking_and_redaction_suffixes(self) -> None:
        self.assertEqual(
            normalized_pdf_identifier(Path("P-001_masked_redacted.pdf")),
            "p-001",
        )


if __name__ == "__main__":
    unittest.main()
