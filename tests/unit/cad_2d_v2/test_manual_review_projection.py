import copy
import unittest

from services.ingestion.cad_2d_pipeline_v2.manual_review import (
    project_completed_review,
    projection_classification_records,
    validate_projection_semantics,
)


DIGEST = "a" * 64


def source_record(sequence: int, source_id: str, decision: str = "prt") -> dict:
    return {
        "sequence": sequence,
        "part_number": source_id,
        "pdf_sha256": f"{sequence:064x}",
        "decision": decision,
        "confidence": None if decision == "exclude" else "high",
        "reviewer": "synthetic-reviewer",
        "reviewed_at": "2026-08-08T00:00:00+08:00",
        "review_reason": "empty drawing" if decision == "exclude" else None,
        "project_name": None,
    }


def source(records: list[dict]) -> dict:
    return {
        "schema_version": "cad_2d_manual_classification_review_v1",
        "records": records,
    }


class ManualReviewProjectionTests(unittest.TestCase):
    def project(self, records: list[dict], overrides: list[dict] | None = None) -> dict:
        verified = {row["pdf_sha256"] for row in records}
        return project_completed_review(
            source(records),
            source_artifact_sha256=DIGEST,
            expected_source_artifact_sha256=DIGEST,
            verified_pdf_digests=verified,
            identity_overrides=overrides or [],
        )

    def test_exclude_remains_auditable_without_definition(self) -> None:
        result = self.project([source_record(1, "synthetic-empty", "exclude")])
        row = result["records"][0]
        self.assertEqual("empty_drawing", row["exclusion_reason_code"])
        self.assertIsNone(row["canonical_definition_id"])
        validate_projection_semantics(result)
        classification = projection_classification_records(result)[0]
        self.assertEqual("exclude", classification["decision"])
        self.assertEqual("empty_drawing", classification["exclusion_reason_code"])

    def test_explicit_views_share_definition_only_with_one_group(self) -> None:
        records = [
            source_record(1, "synthetic-view-a"),
            source_record(2, "synthetic-view-b"),
        ]
        overrides = [
            {
                "rule": "explicit_reviewed_views",
                "source_record_ids": ["synthetic-view-a", "synthetic-view-b"],
                "source_anchor": "synthetic-review-anchor",
            }
        ]
        result = self.project(records, overrides)
        self.assertEqual(
            1,
            len(
                {
                    row["canonical_definition_id"]
                    for row in result["records"]
                }
            ),
        )
        validate_projection_semantics(result)

    def test_same_display_context_does_not_merge_singletons(self) -> None:
        records = [source_record(1, "part-a"), source_record(2, "part-b")]
        records[0]["project_name"] = records[1]["project_name"] = "same-context"
        result = self.project(records)
        self.assertEqual(
            2,
            len(
                {
                    row["canonical_definition_id"]
                    for row in result["records"]
                }
            ),
        )

    def test_multi_page_override_requires_reviewed_page_count(self) -> None:
        records = [source_record(1, "assembly-a", "asm")]
        missing_count = [
            {
                "rule": "multi_page_document",
                "source_record_ids": ["assembly-a"],
                "source_anchor": "synthetic-review-anchor",
            }
        ]
        with self.assertRaisesRegex(ValueError, "page_count"):
            self.project(records, missing_count)

        missing_count[0]["page_count"] = 3
        missing_count[0]["aliases"] = [
            {
                "value": "synthetic-common-name",
                "alias_type": "common_name",
                "reviewer": "synthetic-reviewer",
            }
        ]
        result = self.project(records, missing_count)
        self.assertEqual(3, result["records"][0]["page_count"])
        self.assertEqual(1, len(result["records"][0]["aliases"]))

    def test_digest_mismatch_and_duplicate_override_fail_closed(self) -> None:
        records = [source_record(1, "part-a"), source_record(2, "part-b")]
        with self.assertRaisesRegex(ValueError, "digest"):
            project_completed_review(
                source(records),
                source_artifact_sha256=DIGEST,
                expected_source_artifact_sha256="b" * 64,
                verified_pdf_digests={row["pdf_sha256"] for row in records},
            )

        duplicate = [
            {
                "rule": "multi_page_document",
                "source_record_ids": ["part-a"],
                "source_anchor": "anchor-a",
                "page_count": 2,
            },
            {
                "rule": "multi_page_document",
                "source_record_ids": ["part-a"],
                "source_anchor": "anchor-b",
                "page_count": 2,
            },
        ]
        with self.assertRaisesRegex(ValueError, "multiple identity overrides"):
            self.project(records, duplicate)

    def test_semantics_reject_unreviewed_shared_definition(self) -> None:
        result = self.project(
            [source_record(1, "part-a"), source_record(2, "part-b")]
        )
        broken = copy.deepcopy(result)
        broken["records"][1]["canonical_definition_id"] = broken["records"][0][
            "canonical_definition_id"
        ]
        with self.assertRaisesRegex(ValueError, "explicit reviewed view group"):
            validate_projection_semantics(broken)


if __name__ == "__main__":
    unittest.main()
