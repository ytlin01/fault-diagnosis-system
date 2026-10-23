import copy
import unittest

from services.ingestion.dekg_legacy_adapter import (
    DEKGLegacyAdapterError,
    adapt_dekg_legacy_document,
)
from services.ingestion.fhkb_legacy_adapter import (
    FHKBLegacyAdapterError,
    adapt_fhkb_legacy_records,
)


_METADATA = {
    "release_id": "synthetic-release-v1",
    "source_id": "synthetic-governed-source",
    "source_version": "v1",
    "manifest_digest": "sha256:" + "a" * 64,
    "lineage_ref": "synthetic-lineage-v1",
    "masking_status": "masked",
}


def _legacy_case() -> dict:
    return {
        "rag_candidate_id": "RAG-LEGACY-1",
        "source_type": "field_case_without_standard_fp",
        "relation_type": "historical_similarity",
        "route_target": "rag_case_pool",
        "field_fp_variants": ["Observed trip", "Observed trip"],
        "field_fp_normalized": "normalized trip",
        "RC": ["candidate cause"],
        "PA": None,
        "evidence": {
            "count": 2,
            "total_dt_mins": 14.5,
            "risk_counts": {"medium": 2},
            "status_counts": {"closed": 2},
            "qpl_values": ["Q1"],
            "date_range": {"min": "2026-01-01", "max": "2026-01-02"},
        },
        "source_refs": [
            {
                "source": "synthetic_downtime",
                "record_index": 1,
                "record_number": 2,
                "record_id_field": "id",
                "record_id_value": "ROW-1",
            }
        ],
        "filter_basis": {
            "reason": "synthetic allowlisted candidate",
            "not_for_kg_text2cypher": True,
        },
    }


def _legacy_document() -> dict:
    return {
        "doc_id": "DOC-1",
        "blocks": [
            {
                "block_type": "text",
                "block_id": "TEXT-1",
                "anchor": "section-1",
                "text": "Synthetic serving-safe evidence.",
                "serving_eligible": True,
                "retrieval_eligible": True,
                "language": "en",
            },
            {
                "block_type": "table",
                "block_id": "TABLE-1",
                "anchor": "table-1",
                "table": {"rows": [["code", "meaning"], ["E1", "synthetic"]]},
                "serving_eligible": True,
                "retrieval_eligible": True,
                "page": 3,
            },
        ],
    }


def _partition() -> dict:
    return {
        "decision_id": "TPDX-SELECTION-1",
        "tpdx_extraction_refs": ["TPDX-TABLE-CANDIDATE-1"],
        "tpdx_consumption_state": "candidate_selected",
        "excluded_anchor_refs": ["table-1"],
        "co_source_group_id": "COSOURCE-DOC-1",
    }


class FHKBLegacyAdapterTests(unittest.TestCase):
    def test_maps_legacy_candidate_to_canonical_case(self) -> None:
        package = adapt_fhkb_legacy_records([_legacy_case()], **_METADATA)
        record = package["records"][0]
        self.assertRegex(record["case_id"], r"^FHC_[0-9a-f]{64}$")
        self.assertNotIn("legacy_ids", record)
        self.assertEqual(record["phenomenon"]["observed_texts"], ["Observed trip"])
        self.assertEqual(record["candidate_actions"], [])
        self.assertEqual(record["temporal_context"]["event_time"], None)
        self.assertEqual(record["legacy_context"]["relation_type"], "historical_similarity")
        self.assertEqual(
            record["legacy_context"]["filter_basis_reason"],
            "synthetic allowlisted candidate",
        )
        self.assertEqual(record["evidence_summary"]["event_count"], 2)
        self.assertEqual(
            record["evidence_summary"]["date_range"],
            {"start": "2026-01-01", "end": "2026-01-02"},
        )
        self.assertTrue(record["legacy_context"]["not_for_kg_text2cypher"])
        self.assertEqual(
            record["legacy_context"]["legacy_source_type"],
            "field_case_without_standard_fp",
        )
        self.assertRegex(
            record["source_refs"][0]["source_record_id"],
            r"^FHS_[0-9a-f]{64}$",
        )

    def test_identity_is_deterministic_and_legacy_id_is_not_emitted(self) -> None:
        first = adapt_fhkb_legacy_records([_legacy_case()], **_METADATA)
        changed_legacy_id = _legacy_case()
        changed_legacy_id["rag_candidate_id"] = "RAG-LEGACY-2"
        second = adapt_fhkb_legacy_records([changed_legacy_id], **_METADATA)
        self.assertEqual(
            first["records"][0]["case_id"],
            second["records"][0]["case_id"],
        )
        self.assertNotIn("legacy_ids", first["records"][0])
        self.assertNotIn("legacy_ids", second["records"][0])

    def test_maps_nomic_legacy_type_to_structured_candidate(self) -> None:
        legacy = _legacy_case()
        legacy["source_type"] = "nomic_semantic_related_candidate"
        package = adapt_fhkb_legacy_records([legacy], **_METADATA)
        record = package["records"][0]
        self.assertEqual(record["case_type"], "structured_case_candidate")
        self.assertEqual(
            record["legacy_context"]["legacy_source_type"],
            "nomic_semantic_related_candidate",
        )

    def test_rejects_conflicting_content_for_one_canonical_identity(self) -> None:
        first = _legacy_case()
        second = _legacy_case()
        second["field_fp_normalized"] = "different canonical content"
        with self.assertRaisesRegex(
            FHKBLegacyAdapterError, "conflicting canonical content"
        ):
            adapt_fhkb_legacy_records([first, second], **_METADATA)

    def test_rejects_wrong_route_blocked_promotion_and_ambiguous_provenance(self) -> None:
        wrong_route = _legacy_case()
        wrong_route["route_target"] = "case_retrieval"
        promoted = _legacy_case()
        promoted["confirmed_diagnosis"] = "forbidden"
        missing_record_id = _legacy_case()
        invalid_ref = _legacy_case()
        del invalid_ref["source_refs"][0]["record_index"]
        for candidate in (wrong_route, promoted, invalid_ref):
            with self.subTest(candidate=candidate):
                with self.assertRaises(FHKBLegacyAdapterError):
                    adapt_fhkb_legacy_records([candidate], **_METADATA)


class DEKGLegacyAdapterTests(unittest.TestCase):
    def test_full_document_emits_all_eligible_content(self) -> None:
        package = adapt_dekg_legacy_document(_legacy_document(), **_METADATA)
        self.assertEqual(package["schema_version"], "dekg_evidence_v2")
        self.assertEqual(len(package["records"]), 2)
        self.assertEqual(
            {record["content_kind"] for record in package["records"]},
            {"text", "table"},
        )
        for record in package["records"]:
            self.assertRegex(record["evidence_id"], r"^DEK_[0-9a-f]{64}$")
            self.assertEqual(record["tpdx_partition"]["mode"], "none")

    def test_residual_mode_excludes_selected_table_and_marks_co_source(self) -> None:
        package = adapt_dekg_legacy_document(
            _legacy_document(),
            ingestion_mode="evidence_residual",
            partition_decision=_partition(),
            **_METADATA,
        )
        self.assertEqual(len(package["records"]), 1)
        record = package["records"][0]
        self.assertEqual(record["anchor"], "section-1")
        self.assertNotEqual(record["anchor"], "table-1")
        self.assertEqual(
            record["tpdx_partition"]["excluded_anchor_refs"],
            ["table-1"],
        )
        self.assertEqual(record["co_source"]["group_id"], "COSOURCE-DOC-1")
        self.assertFalse(record["co_source"]["independent_corroboration"])

    def test_identity_is_deterministic(self) -> None:
        first = adapt_dekg_legacy_document(_legacy_document(), **_METADATA)
        second = adapt_dekg_legacy_document(
            copy.deepcopy(_legacy_document()), **_METADATA
        )
        self.assertEqual(
            [record["evidence_id"] for record in first["records"]],
            [record["evidence_id"] for record in second["records"]],
        )

    def test_rejects_non_table_unknown_or_unreviewed_partition(self) -> None:
        non_table = _partition()
        non_table["excluded_anchor_refs"] = ["section-1"]
        unknown = _partition()
        unknown["excluded_anchor_refs"] = ["table-missing"]
        unreviewed = _partition()
        unreviewed["tpdx_consumption_state"] = "extracted"
        for partition in (non_table, unknown, unreviewed):
            with self.subTest(partition=partition):
                with self.assertRaises(DEKGLegacyAdapterError):
                    adapt_dekg_legacy_document(
                        _legacy_document(),
                        ingestion_mode="evidence_residual",
                        partition_decision=partition,
                        **_METADATA,
                    )

    def test_rejects_partition_in_full_mode_and_unsafe_content(self) -> None:
        with self.assertRaises(DEKGLegacyAdapterError):
            adapt_dekg_legacy_document(
                _legacy_document(),
                partition_decision=_partition(),
                **_METADATA,
            )
        unsafe = _legacy_document()
        unsafe["blocks"][0]["raw_response"] = "forbidden provider output"
        with self.assertRaises(DEKGLegacyAdapterError):
            adapt_dekg_legacy_document(unsafe, **_METADATA)

    def test_rejects_residual_with_no_remaining_evidence(self) -> None:
        document = _legacy_document()
        document["blocks"] = [document["blocks"][1]]
        with self.assertRaisesRegex(
            DEKGLegacyAdapterError, "no residual DEKG evidence"
        ):
            adapt_dekg_legacy_document(
                document,
                ingestion_mode="evidence_residual",
                partition_decision=_partition(),
                **_METADATA,
            )


if __name__ == "__main__":
    unittest.main()
