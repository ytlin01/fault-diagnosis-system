from __future__ import annotations

import copy
import unittest

from services.ingestion.cad_2d_pipeline_v2 import (
    audit_asm_bom,
    build_drawing_index,
    build_project_owner_output,
    build_relationships,
    combine_bom_candidate_sources,
    extract_asm_bom,
    extract_fields,
    merge_classifications,
    reuse_historical_bom_candidates,
    validate_config,
)
from services.ingestion.cad_2d_pipeline_v2.artifacts import build_manifest


def config() -> dict:
    return validate_config(
        {
            "schema_version": "test-v1",
            "identifier": {"strip_suffixes": ["_masked"]},
            "classification": {
                "allowed_decisions": ["ASM", "PRT", "EXCLUDE", "UNKNOWN"],
                "decision_aliases": {
                    "asm": "ASM",
                    "prt": "PRT",
                    "exclude": "EXCLUDE",
                    "unresolved": "UNKNOWN",
                },
                "unreviewed_note": "unreviewed",
            },
            "field_extraction": {
                "default_profile": "p1",
                "profiles": {"p1": {"page_index": 0, "regions": {"drawing_title": [0, 0, 100, 20], "project_name": [0, 20, 100, 40]}}},
            },
            "bom": {
                "approved_parent_decision": "ASM",
                "page_index": 0,
                "item_number_pattern": "^[0-9]+$",
                "header_keywords": {"item": ["item"], "part_number": ["part number"], "description": ["description"], "quantity": ["qty"]},
                "thresholds": {"header_y_tolerance": 3, "row_y_tolerance": 3, "item_anchor_tolerance": 8, "quantity_anchor_tolerance": 20, "min_header_matches": 3, "min_quantity": 1, "max_quantity": 99},
            },
            "audit": {
                "blocking_severities": ["error"],
                "suspicious_identifier_pattern": "^[A-Za-z0-9][A-Za-z0-9._ /-]*$",
                "override_decision_states": ["accepted", "rejected"],
            },
            "relationships": {
                "asm_decision": "ASM",
                "prt_decision": "PRT",
                "unknown_decision": "UNKNOWN",
            },
        }
    )


class Cad2dPipelineTests(unittest.TestCase):
    def test_a01_preserves_authoritative_order_and_count(self) -> None:
        full = [{"part_number": "A", "decision": "ASM"}, {"part_number": "B", "decision": "PRT"}]
        reviewed = [{"part_number": "B", "decision": "ASM", "drawing_type": "PRT", "review_note": "checked"}]
        result = merge_classifications(reviewed, full, config())
        self.assertEqual([row["part_number"] for row in result.records], ["A", "B"])
        self.assertEqual(result.audit["changed_decision_count"], 1)
        self.assertEqual(len(result.records), len(full))

    def test_a01_rejects_duplicates_and_non_subset(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            merge_classifications([], [{"part_number": "A", "decision": "ASM"}, {"part_number": "A", "decision": "PRT"}], config())
        with self.assertRaisesRegex(ValueError, "not a subset"):
            merge_classifications([{"part_number": "X", "decision": "PRT"}], [{"part_number": "A", "decision": "ASM"}], config())

    def test_reviewed_exclude_is_retained_but_not_promotable(self) -> None:
        full = [{"part_number": "A", "decision": "PRT"}]
        reviewed = [
            {
                "part_number": "A",
                "decision": "exclude",
                "human_review_reason": "empty drawing",
            }
        ]
        merged = merge_classifications(reviewed, full, config())
        self.assertEqual("EXCLUDE", merged.records[0]["decision"])
        self.assertFalse(merged.records[0]["promotion_eligible"])
        self.assertEqual("REVIEWED_EXCLUSION", merged.exclusions[0]["reason_code"])

        index = build_drawing_index(merged.records, [], config())
        self.assertFalse(index.records[0]["promotion_eligible"])
        self.assertEqual("REVIEWED_EXCLUSION", index.exclusions[0]["reason_code"])
        self.assertEqual([], extract_asm_bom(index.records, [], config()).records)

    def test_review_projection_may_add_governed_classification_gap(self) -> None:
        reviewed = [{"part_number": "B", "decision": "prt"}]
        full = [{"part_number": "A", "decision": "ASM"}]
        result = merge_classifications(
            reviewed,
            full,
            config(),
            allow_reviewed_additions=True,
        )
        self.assertEqual(["A", "B"], [row["part_number"] for row in result.records])
        self.assertEqual("PRT", result.records[1]["decision"])
        self.assertEqual(1, result.audit["reviewed_addition_count"])

    def test_a02_controlled_profile_preserves_empty_fields(self) -> None:
        documents = [{"part_number": "A_masked", "words": [[10, 5, 20, 10, "Title"]]}]
        result = extract_fields(documents, config())
        self.assertEqual(result.records[0]["part_number"], "A")
        self.assertEqual(result.records[0]["drawing_title"], "Title")
        self.assertEqual(result.records[0]["project_name"], "")

    def test_a02_reports_unknown_profile_without_protected_value(self) -> None:
        result = extract_fields([{"part_number": "SECRET", "template_profile": "missing", "words": []}], config())
        self.assertEqual(result.records, [])
        self.assertEqual(result.exclusions, [{"reason_code": "UNKNOWN_TEMPLATE_PROFILE", "record_index": 0}])
        self.assertNotIn("SECRET", str(result.exclusions))

    def test_a03_left_join_and_field_only_accounting(self) -> None:
        classifications = [{"part_number": "A", "decision": "ASM"}, {"part_number": "B", "decision": "PRT"}]
        fields = [{"part_number": "A_masked", "drawing_title": "T", "project_name": "P"}, {"part_number": "C", "drawing_title": "X"}]
        result = build_drawing_index(classifications, fields, config())
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[1]["drawing_title"], "")
        self.assertEqual(result.audit["field_only_count"], 1)

    def test_a03_rejects_normalized_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "colliding"):
            build_drawing_index([{"part_number": "A", "decision": "ASM"}], [{"part_number": "A"}, {"part_number": "A_masked"}], config())

    def test_b01_only_asm_and_reliable_rows(self) -> None:
        index = [{"part_number": "ASM-1", "drawing_type": "ASM"}, {"part_number": "PRT-1", "drawing_type": "PRT"}]
        words = [
            {"part_number": "ASM-1", "source_pdf_sha256": "a" * 64, "page_index": 0, "page_count": 1, "extraction_state": "local_reviewed_asm_word_geometry", "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [90, 0, 100, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "CHILD-1"], [90, 10, 100, 12, "2"],
            ]},
        ]
        result = extract_asm_bom(index, words, config())
        self.assertEqual(result.audit["approved_asm_count"], 1)
        self.assertEqual(result.records[0]["rows"][0]["quantity"], 2)

    def test_b01_missing_header_is_review_finding(self) -> None:
        result = extract_asm_bom([{"part_number": "A", "drawing_type": "ASM"}], [{"part_number": "A", "source_pdf_sha256": "a" * 64, "page_index": 0, "page_count": 1, "extraction_state": "local_reviewed_asm_word_geometry", "words": [[0, 0, 1, 1, "noise"]]}], config())
        self.assertEqual(result.records, [])
        self.assertEqual(result.exclusions[0]["reason_code"], "RELIABLE_BOM_HEADER_NOT_FOUND")

    def test_b01_ignores_numeric_drawing_callout_outside_item_anchor(self) -> None:
        words = [{
            "part_number": "A",
            "source_pdf_sha256": "a" * 64,
            "page_index": 0,
            "page_count": 1,
            "extraction_state": "local_reviewed_asm_word_geometry",
            "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [90, 0, 100, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "CHILD-1"], [90, 10, 100, 12, "2"],
                [-100, 20, -90, 22, "22"], [40, 20, 60, 22, "drawing"],
            ],
        }]
        result = extract_asm_bom(
            [{"part_number": "A", "drawing_type": "ASM"}], words, config()
        )
        self.assertEqual(1, len(result.records[0]["rows"]))
        self.assertEqual([], result.exclusions)

    def test_b01_aligned_item_with_invalid_quantity_remains_finding(self) -> None:
        words = [{
            "part_number": "A",
            "source_pdf_sha256": "a" * 64,
            "page_index": 0,
            "page_count": 1,
            "extraction_state": "local_reviewed_asm_word_geometry",
            "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [90, 0, 100, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "CHILD-1"], [90, 10, 100, 12, "many"],
            ],
        }]
        result = extract_asm_bom(
            [{"part_number": "A", "drawing_type": "ASM"}], words, config()
        )
        self.assertEqual([], result.records)
        self.assertEqual(
            ["INVALID_BOM_QUANTITY", "NO_RELIABLE_BOM_ROWS"],
            [finding["reason_code"] for finding in result.exclusions],
        )

    def test_b01_description_boundary_overlap_does_not_contaminate_part(self) -> None:
        words = [{
            "part_number": "A",
            "source_pdf_sha256": "a" * 64,
            "page_index": 0,
            "page_count": 1,
            "extraction_state": "local_reviewed_asm_word_geometry",
            "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"],
                [80, 0, 100, 2, "description"], [120, 0, 130, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "PART-1"],
                [66, 10, 90, 12, "washer"], [120, 10, 130, 12, "2"],
            ],
        }]
        result = extract_asm_bom(
            [{"part_number": "A", "drawing_type": "ASM"}], words, config()
        )
        self.assertEqual("PART-1", result.records[0]["rows"][0]["part_number"])

    def test_b01_asymmetric_multiline_part_is_ambiguous_not_reassigned(self) -> None:
        words = [{
            "part_number": "A",
            "source_pdf_sha256": "a" * 64,
            "page_index": 0,
            "page_count": 1,
            "extraction_state": "local_reviewed_asm_word_geometry",
            "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [90, 0, 100, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "PART-A"], [90, 10, 100, 12, "1"],
                [40, 16, 60, 18, "CONT-A1"], [40, 22, 60, 24, "CONT-A2"],
                [0, 30, 10, 32, "2"], [40, 30, 60, 32, "PART-B"], [90, 30, 100, 32, "1"],
            ],
        }]
        result = extract_asm_bom(
            [{"part_number": "A", "drawing_type": "ASM"}], words, config()
        )
        self.assertEqual(
            ["PART-A", "PART-B"],
            [row["part_number"] for row in result.records[0]["rows"]],
        )
        self.assertIn(
            "AMBIGUOUS_BOM_PART_CONTINUATION",
            [finding["reason_code"] for finding in result.exclusions],
        )

    def test_b01_continuation_after_last_item_is_ambiguous(self) -> None:
        words = [{
            "part_number": "A",
            "source_pdf_sha256": "a" * 64,
            "page_index": 0,
            "page_count": 1,
            "extraction_state": "local_reviewed_asm_word_geometry",
            "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [90, 0, 100, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "PART-A"], [90, 10, 100, 12, "1"],
                [40, 16, 60, 18, "CONT-A"],
            ],
        }]
        result = extract_asm_bom(
            [{"part_number": "A", "drawing_type": "ASM"}], words, config()
        )
        self.assertEqual("PART-A", result.records[0]["rows"][0]["part_number"])
        self.assertIn(
            "AMBIGUOUS_BOM_PART_CONTINUATION",
            [finding["reason_code"] for finding in result.exclusions],
        )

    def test_b01_historical_reuse_exposes_missing_new_asm(self) -> None:
        index = [
            {"part_number": "ASM-OLD", "drawing_type": "ASM"},
            {"part_number": "ASM-NEW", "drawing_type": "ASM"},
            {"part_number": "PRT-1", "drawing_type": "PRT"},
        ]
        historical = {
            "ASM-OLD": [
                {
                    "item_no": "1",
                    "part_number": "PRT-1",
                    "qty": 2,
                    "description": "synthetic",
                }
            ]
        }
        result = reuse_historical_bom_candidates(index, historical, config())
        self.assertEqual("governed_historical_structured_reuse", result.audit["extraction_mode"])
        self.assertEqual(1, result.audit["output_parent_count"])
        self.assertEqual(1, result.audit["missing_current_asm_source_count"])
        self.assertEqual(2, result.records[0]["rows"][0]["quantity"])

    def test_b01_combines_history_and_fresh_without_double_counting_missing(self) -> None:
        index = [
            {"part_number": "ASM-OLD", "drawing_type": "ASM"},
            {"part_number": "PRT-1", "drawing_type": "PRT"},
            {"part_number": "ASM-NEW", "drawing_type": "ASM"},
            {"part_number": "ASM-NO-BOM", "drawing_type": "ASM"},
        ]
        historical = {
            "ASM-OLD": [{"item_no": "1", "part_number": "PRT-1", "qty": 2}]
        }
        words = [
            {"part_number": "ASM-NEW", "source_pdf_sha256": "b" * 64, "page_index": 0, "page_count": 1, "extraction_state": "local_reviewed_asm_word_geometry", "words": [
                [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [90, 0, 100, 2, "qty"],
                [0, 10, 10, 12, "1"], [40, 10, 60, 12, "PRT-1"], [90, 10, 100, 12, "1"],
            ]},
            {"part_number": "ASM-NO-BOM", "source_pdf_sha256": "c" * 64, "page_index": 0, "page_count": 1, "extraction_state": "local_reviewed_asm_word_geometry", "words": [[0, 0, 10, 2, "drawing"]]},
        ]
        result = combine_bom_candidate_sources(index, historical, words, config())
        self.assertEqual("combined_historical_and_fresh_pdf_words", result.audit["extraction_mode"])
        self.assertEqual(2, result.audit["output_parent_count"])
        self.assertEqual(1, result.audit["unresolved_current_asm_count"])
        self.assertEqual(0, result.audit["historical_precedence_overlap_count"])
        self.assertEqual(
            {"governed_historical_structured_reuse", "fresh_reviewed_pdf_words"},
            {record["bom_source"] for record in result.records},
        )
        self.assertEqual(
            ["RELIABLE_BOM_HEADER_NOT_FOUND"],
            [finding["reason_code"] for finding in result.exclusions],
        )
        self.assertEqual(3, result.exclusions[0]["record_index"])
        self.assertEqual("ASM-NO-BOM", result.exclusions[0]["parent_part_number"])

    def test_manifest_and_results_are_deterministic(self) -> None:
        cfg = config()
        inputs = {"full": [{"part_number": "A", "decision": "ASM"}], "reviewed": []}
        result1 = merge_classifications(inputs["reviewed"], inputs["full"], cfg).as_dict()
        result2 = merge_classifications(copy.deepcopy(inputs["reviewed"]), copy.deepcopy(inputs["full"]), copy.deepcopy(cfg)).as_dict()
        self.assertEqual(result1, result2)
        self.assertEqual(build_manifest(stage="A01", config=cfg, inputs=inputs, result=result1), build_manifest(stage="A01", config=cfg, inputs=inputs, result=result2))

    def test_b02_distinguishes_findings_and_blocks_c01(self) -> None:
        index = [
            {"part_number": "ASM-1", "drawing_type": "ASM"},
            {"part_number": "PRT-1", "drawing_type": "PRT"},
        ]
        bom = [{"parent_part_number": "ASM-1", "rows": [
            {"item_no": "1", "part_number": "", "quantity": "x"},
            {"item_no": "1", "part_number": "PRT-1", "quantity": "2"},
        ]}]
        audit = audit_asm_bom(index, bom, config())
        self.assertEqual(
            set(audit.audit["finding_counts_by_code"]),
            {"BLANK_PART_NUMBER", "DUPLICATE_ITEM_NUMBER", "INVALID_QUANTITY"},
        )
        with self.assertRaisesRegex(ValueError, "C01 blocked"):
            build_relationships(index, bom, audit.records, config())
        with self.assertRaisesRegex(ValueError, "recomputed B02"):
            build_relationships(index, bom, [], config())

    def test_b02_and_c01_preserve_b01_extraction_findings(self) -> None:
        index = [{"part_number": "ASM-1", "drawing_type": "ASM"}]
        bom = [{
            "parent_part_number": "ASM-1",
            "rows": [{"item": "1", "part_number": "CHILD-1", "quantity": 1}],
        }]
        source_findings = [{
            "reason_code": "RELIABLE_BOM_HEADER_NOT_FOUND",
            "parent_part_number": "ASM-1",
            "record_index": 0,
        }]
        audit = audit_asm_bom(
            index, bom, config(), source_findings=source_findings
        )
        self.assertIn(
            "RELIABLE_BOM_HEADER_NOT_FOUND",
            audit.audit["finding_counts_by_code"],
        )
        with self.assertRaisesRegex(ValueError, "C01 blocked"):
            build_relationships(
                index,
                bom,
                audit.records,
                config(),
                source_findings=source_findings,
            )

    def test_b02_source_finding_cannot_downgrade_computed_error(self) -> None:
        index = [{"part_number": "ASM-1", "drawing_type": "ASM"}]
        source_findings = [{
            "code": "CLASSIFICATION_OR_EMPTY_BOM",
            "severity": "warning",
            "parent_part_number": "ASM-1",
        }]
        audit = audit_asm_bom(
            index, [], config(), source_findings=source_findings
        )
        self.assertEqual(1, audit.audit["blocking_finding_count"])
        self.assertEqual("error", audit.records[0]["severity"])
        with self.assertRaisesRegex(ValueError, "severity"):
            audit_asm_bom(
                index,
                [],
                config(),
                source_findings=[{
                    "code": "PENDING_SOURCE_REVIEW",
                    "severity": "ignored",
                    "parent_part_number": "ASM-1",
                }],
            )

    def test_governed_override_allows_c01_and_c02_preserves_semantics(self) -> None:
        index = [
            {"part_number": "ASM-1", "drawing_type": "ASM", "drawing_title": "A"},
            {"part_number": "PRT-1", "drawing_type": "PRT", "drawing_title": "P"},
        ]
        bom = [{"parent_part_number": "ASM-1", "rows": [
            {"item_no": "1", "part_number": "PRT-1", "quantity": "2"},
            {"item_no": "2", "part_number": "OUTSIDE-1", "quantity": "1"},
        ]}]
        audit = audit_asm_bom(index, bom, config())
        relationships = build_relationships(index, bom, audit.records, config())
        self.assertEqual(
            [row["child_semantics"] for row in relationships.records],
            ["confirmed_prt_child", "unknown_child"],
        )
        self.assertEqual(2, len({row["occurrence_id"] for row in relationships.records}))
        self.assertTrue(
            all(row["parent_definition_id"] for row in relationships.records)
        )
        final = build_project_owner_output(index, relationships.records, config())
        self.assertEqual(final.records[0]["child_prt_part_numbers"], ["PRT-1"])
        self.assertEqual(final.records[0]["unknown_child_part_numbers"], ["OUTSIDE-1"])

        blocked_bom = [{"parent_part_number": "ASM-1", "rows": []}]
        blocked = audit_asm_bom(index, blocked_bom, config())
        finding = blocked.records[0]
        override = [{
            "finding_id": finding["finding_id"],
            "source_anchor": "synthetic://review/1",
            "reviewed_by": "reviewer",
            "reviewed_at": "2026-08-03T00:00:00Z",
            "reason": "verified empty assembly",
            "decision_state": "accepted",
        }]
        accepted = build_relationships(index, blocked_bom, blocked.records, config(), overrides=override)
        self.assertEqual(accepted.audit["accepted_risk_count"], 1)

    def _correction_scenario(self) -> tuple[list[dict], dict, list[dict]]:
        """Return (index, historical, words) yielding a BLANK row and a no-header ASM."""
        index = [
            {"part_number": "ASM-1", "drawing_type": "ASM"},
            {"part_number": "ASM-2", "drawing_type": "ASM"},
            {"part_number": "ASM-3", "drawing_type": "ASM"},
            {"part_number": "PRT-1", "drawing_type": "PRT"},
        ]
        historical = {"ASM-1": [{"item_no": "1", "part_number": "PRT-1", "qty": 2}]}
        words = [
            {
                "part_number": "ASM-2",
                "source_pdf_sha256": "b" * 64,
                "page_index": 0,
                "page_count": 1,
                "extraction_state": "local_reviewed_asm_word_geometry",
                "words": [
                    [0, 0, 10, 2, "item"], [40, 0, 60, 2, "part number"], [80, 0, 90, 2, "qty"],
                    [0, 10, 10, 12, "1"], [40, 10, 60, 12, "PART-A"], [80, 10, 90, 12, "1"],
                    [0, 20, 10, 22, "2"], [80, 20, 90, 22, "1"],
                ],
            },
            {
                "part_number": "ASM-3",
                "source_pdf_sha256": "c" * 64,
                "page_index": 0,
                "page_count": 1,
                "extraction_state": "local_reviewed_asm_word_geometry",
                "words": [[0, 0, 10, 2, "drawing"]],
            },
        ]
        return index, historical, words

    def test_b01_corrections_add_repair_and_new_parent_and_clear_findings(self) -> None:
        index, historical, words = self._correction_scenario()
        base = combine_bom_candidate_sources(index, historical, words, config())
        self.assertEqual(2, len(base.exclusions))
        audit = audit_asm_bom(index, base.records, config(), source_findings=base.exclusions)
        ids = {
            (row["code"], row["parent_part_number"], row["row_number"]): row["finding_id"]
            for row in audit.records
        }
        blank_id = ids[("BLANK_BOM_PART_NUMBER", "ASM-2", 2)]
        header_id = ids[("RELIABLE_BOM_HEADER_NOT_FOUND", "ASM-3", None)]

        corrections = [
            {
                "parent_part_number": "ASM-2",
                "item": "2",
                "part_number": "PART-B",
                "quantity": 1,
                "source_anchor": "synthetic://asm2/row2",
                "reviewed_by": "tester",
                "reviewed_at": "2026-08-10T00:00:00Z",
                "reason": "verified on reviewed page",
                "decision_state": "accepted",
                "resolved_finding_ids": [blank_id],
            },
            {
                "parent_part_number": "ASM-3",
                "rows": [{"item": "1", "part_number": "PART-C", "quantity": 1}],
                "source_anchor": "synthetic://asm3/table",
                "reviewed_by": "tester",
                "reviewed_at": "2026-08-10T00:00:00Z",
                "reason": "verified header on reviewed page",
                "decision_state": "accepted",
                "resolved_finding_ids": [header_id],
            },
        ]
        corrected = combine_bom_candidate_sources(
            index, historical, words, config(), corrections=corrections
        )
        self.assertEqual(0, len(corrected.exclusions))
        self.assertEqual(0, corrected.audit["unresolved_current_asm_count"])
        self.assertEqual(2, corrected.audit["correction_count"])
        self.assertEqual(2, corrected.audit["added_row_count"])
        self.assertEqual(0, corrected.audit["repaired_row_count"])
        self.assertEqual(1, corrected.audit["added_parent_count"])
        self.assertEqual(2, corrected.audit["cleared_extraction_finding_count"])

        asm2 = next(r for r in corrected.records if r["parent_part_number"] == "ASM-2")
        self.assertEqual(
            [row["part_number"] for row in asm2["rows"]], ["PART-A", "PART-B"]
        )
        asm3 = next(r for r in corrected.records if r["parent_part_number"] == "ASM-3")
        self.assertEqual("governed_bom_correction", asm3["bom_source"])
        self.assertEqual("PART-C", asm3["rows"][0]["part_number"])
        self.assertEqual("synthetic://asm2/row2", asm2["rows"][1]["source_anchor"])
        self.assertEqual("tester", asm2["rows"][1]["correction_reviewed_by"])

        regenerated = audit_asm_bom(index, corrected.records, config())
        codes = {row["code"] for row in regenerated.records}
        self.assertNotIn("BLANK_BOM_PART_NUMBER", codes)
        self.assertNotIn("RELIABLE_BOM_HEADER_NOT_FOUND", codes)
        self.assertNotIn("CLASSIFICATION_OR_EMPTY_BOM", codes)
        self.assertEqual([], regenerated.records)

    def test_b01_corrections_insert_new_row_in_item_order(self) -> None:
        index, historical, words = self._correction_scenario()
        # Add a third ASM-2 row (item 3) so item 2 sits in the middle, not the tail.
        words[0]["words"] += [
            [0, 30, 10, 32, "3"], [40, 30, 60, 32, "PART-C"], [80, 30, 90, 32, "1"],
        ]
        base = combine_bom_candidate_sources(index, historical, words, config())
        audit = audit_asm_bom(index, base.records, config(), source_findings=base.exclusions)
        blank_id = next(
            row["finding_id"]
            for row in audit.records
            if row["code"] == "BLANK_BOM_PART_NUMBER" and row["parent_part_number"] == "ASM-2"
        )
        correction = [{
            "parent_part_number": "ASM-2",
            "item": "2",
            "part_number": "PART-B",
            "quantity": 1,
            "source_anchor": "synthetic://asm2/row2",
            "reviewed_by": "tester",
            "reviewed_at": "2026-08-10T00:00:00Z",
            "reason": "verified middle row",
            "decision_state": "accepted",
            "resolved_finding_ids": [blank_id],
        }]
        corrected = combine_bom_candidate_sources(
            index, historical, words, config(), corrections=correction
        )
        asm2 = next(r for r in corrected.records if r["parent_part_number"] == "ASM-2")
        self.assertEqual(
            [row["part_number"] for row in asm2["rows"]],
            ["PART-A", "PART-B", "PART-C"],
        )
        self.assertEqual(1, corrected.audit["added_row_count"])

    def test_b01_correction_repairs_existing_row_in_place(self) -> None:
        index, historical, words = self._correction_scenario()
        base = combine_bom_candidate_sources(index, historical, words, config())
        audit = audit_asm_bom(index, base.records, config(), source_findings=base.exclusions)
        blank_id = next(
            row["finding_id"]
            for row in audit.records
            if row["code"] == "BLANK_BOM_PART_NUMBER" and row["parent_part_number"] == "ASM-2"
        )
        correction = [{
            "parent_part_number": "ASM-2",
            "item": "1",
            "part_number": "PART-A2",
            "quantity": 1,
            "source_anchor": "synthetic://asm2/row1",
            "reviewed_by": "tester",
            "reviewed_at": "2026-08-10T00:00:00Z",
            "reason": "verified wrapped value",
            "decision_state": "accepted",
            "resolved_finding_ids": [blank_id],
        }]
        corrected = combine_bom_candidate_sources(
            index, historical, words, config(), corrections=correction
        )
        asm2 = next(r for r in corrected.records if r["parent_part_number"] == "ASM-2")
        self.assertEqual(1, len(asm2["rows"]))
        self.assertEqual("PART-A2", asm2["rows"][0]["part_number"])
        self.assertEqual(1, corrected.audit["repaired_row_count"])
        self.assertEqual(0, corrected.audit["added_row_count"])

    def test_b01_corrections_validate_governed_shape(self) -> None:
        index, historical, words = self._correction_scenario()
        base = combine_bom_candidate_sources(index, historical, words, config())
        audit = audit_asm_bom(index, base.records, config(), source_findings=base.exclusions)
        blank_id = next(
            row["finding_id"]
            for row in audit.records
            if row["code"] == "BLANK_BOM_PART_NUMBER" and row["parent_part_number"] == "ASM-2"
        )
        valid = {
            "parent_part_number": "ASM-2",
            "item": "2",
            "part_number": "PART-B",
            "quantity": 1,
            "source_anchor": "synthetic://x",
            "reviewed_by": "tester",
            "reviewed_at": "2026-08-10T00:00:00Z",
            "reason": "verified",
            "decision_state": "accepted",
            "resolved_finding_ids": [blank_id],
        }
        cases = [
            ("governed correction is missing governed fields", {k: v for k, v in valid.items() if k != "reason"}),
            ("governed correction governed fields must not be blank", {**valid, "reason": "  "}),
            ("governed correction decision_state is unsupported", {**valid, "decision_state": "maybe"}),
            ("resolved_finding_ids must be a list of non-blank strings", {**valid, "resolved_finding_ids": [" "] }),
            ("governed correction parent is absent from drawing index", {**valid, "parent_part_number": "ASM-NOPE"}),
            ("invalid quantity", {**valid, "quantity": "many"}),
        ]
        for message, correction in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    combine_bom_candidate_sources(
                        index, historical, words, config(), corrections=[correction]
                    )
        with self.assertRaisesRegex(ValueError, "duplicates a B01 parent"):
            combine_bom_candidate_sources(
                index,
                historical,
                words,
                config(),
                corrections=[{
                    "parent_part_number": "ASM-1",
                    "rows": [{"item": "1", "part_number": "PART-C", "quantity": 1}],
                    "source_anchor": "synthetic://x",
                    "reviewed_by": "tester",
                    "reviewed_at": "2026-08-10T00:00:00Z",
                    "reason": "verified",
                    "decision_state": "accepted",
                    "resolved_finding_ids": [blank_id],
                }],
            )
        # ASM-3 is in the drawing index but has no B01 record yet: a row-shape
        # correction there must be rejected rather than silently creating a parent.
        with self.assertRaisesRegex(ValueError, "has no B01 record"):
            combine_bom_candidate_sources(
                index,
                historical,
                words,
                config(),
                corrections=[{**valid, "parent_part_number": "ASM-3"}],
            )
        # Two row corrections for the same (parent, item) must be rejected rather
        # than silently applying the second as a re-update.
        with self.assertRaisesRegex(ValueError, "duplicate governed row correction"):
            combine_bom_candidate_sources(
                index,
                historical,
                words,
                config(),
                corrections=[valid, {**valid, "part_number": "PART-B2"}],
            )

    def test_b01_corrections_are_deterministic(self) -> None:
        index, historical, words = self._correction_scenario()
        cfg = config()
        base = combine_bom_candidate_sources(index, historical, words, cfg)
        audit = audit_asm_bom(index, base.records, cfg, source_findings=base.exclusions)
        blank_id = next(
            row["finding_id"]
            for row in audit.records
            if row["code"] == "BLANK_BOM_PART_NUMBER" and row["parent_part_number"] == "ASM-2"
        )
        corrections = [{
            "parent_part_number": "ASM-2",
            "item": "2",
            "part_number": "PART-B",
            "quantity": 1,
            "source_anchor": "synthetic://asm2/row2",
            "reviewed_by": "tester",
            "reviewed_at": "2026-08-10T00:00:00Z",
            "reason": "verified",
            "decision_state": "accepted",
            "resolved_finding_ids": [blank_id],
        }]
        result1 = combine_bom_candidate_sources(
            index, historical, words, copy.deepcopy(cfg), corrections=copy.deepcopy(corrections)
        ).as_dict()
        result2 = combine_bom_candidate_sources(
            index, historical, words, copy.deepcopy(cfg), corrections=copy.deepcopy(corrections)
        ).as_dict()
        self.assertEqual(result1, result2)
        manifest1 = build_manifest(
            stage="B01", config=cfg, inputs={"corrections": corrections}, result=result1
        )
        manifest2 = build_manifest(
            stage="B01", config=cfg, inputs={"corrections": corrections}, result=result2
        )
        self.assertEqual(manifest1, manifest2)

    def test_excluded_drawing_cannot_enter_c01_or_c02(self) -> None:
        index = [
            {"part_number": "ASM-1", "drawing_type": "ASM"},
            {
                "part_number": "EXCLUDED-1",
                "drawing_type": "EXCLUDE",
                "promotion_eligible": False,
            },
        ]
        bom = [
            {
                "parent_part_number": "ASM-1",
                "rows": [
                    {"item_no": "1", "part_number": "EXCLUDED-1", "quantity": 1}
                ],
            }
        ]
        audit = audit_asm_bom(index, bom, config())
        relationships = build_relationships(index, bom, audit.records, config())
        self.assertEqual([], relationships.records)
        self.assertEqual(
            "EXCLUDED_CHILD_NOT_PROMOTED",
            relationships.exclusions[0]["reason_code"],
        )
        self.assertEqual(
            "ASM-1", relationships.exclusions[0]["parent_part_number"]
        )
        self.assertEqual("1", relationships.exclusions[0]["item_no"])
        final = build_project_owner_output(index, [], config())
        self.assertEqual(["ASM-1"], [row["part_number"] for row in final.records])
        self.assertEqual("DRAWING_NOT_PROMOTED", final.exclusions[0]["reason_code"])

    def test_c01_blank_child_exclusion_carries_parent_and_item(self) -> None:
        index = [{"part_number": "ASM-1", "drawing_type": "ASM"}]
        bom = [
            {
                "parent_part_number": "ASM-1",
                "rows": [
                    {"item_no": "4", "part_number": "", "quantity": 1},
                    {"item_no": "5", "part_number": "PRT-1", "quantity": 1},
                ],
            }
        ]
        audit = audit_asm_bom(index, bom, config())
        finding = audit.records[0]
        override = [{
            "finding_id": finding["finding_id"],
            "source_anchor": "synthetic://review/blank-row",
            "reviewed_by": "reviewer",
            "reviewed_at": "2026-08-03T00:00:00Z",
            "reason": "governed accept of historical blank row",
            "decision_state": "accepted",
        }]
        relationships = build_relationships(
            index, bom, audit.records, config(), overrides=override
        )
        self.assertEqual(
            "BLANK_CHILD_IDENTIFIER",
            relationships.exclusions[0]["reason_code"],
        )
        self.assertEqual("ASM-1", relationships.exclusions[0]["parent_part_number"])
        self.assertEqual("4", relationships.exclusions[0]["item_no"])
        self.assertEqual(0, relationships.exclusions[0]["record_index"])
        self.assertEqual(1, relationships.audit["accepted_risk_count"])


if __name__ == "__main__":
    unittest.main()
