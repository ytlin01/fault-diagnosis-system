from __future__ import annotations

import unittest

from services.canonicalization import (
    CANDIDATE,
    REVIEWED,
    canonicalize_case_candidate,
    canonicalize_query,
    canonicalize_serving_document,
    canonicalize_serving_document_batch,
    canonicalize_structured_record,
)


class CanonicalizationPreKgTests(unittest.TestCase):
    def test_query_builds_minimal_state_without_mapping_records(self) -> None:
        state = canonicalize_query(
            "cowling组装一直NG，机械也没报具体什么错，昨天也是",
            received_at="2026-04-28T10:30:00+08:00",
        )

        payload = state.as_dict()

        self.assertEqual(
            set(payload.keys()),
            {"contract_version", "query", "entities", "mapping_records", "source_refs"},
        )
        self.assertEqual(payload["query"]["normalized_text"], "cowling组装一直NG，机械也没报具体什么错，昨天也是")
        self.assertEqual(payload["entities"]["asset"]["module"]["canonical"], "cowling组装模块")
        self.assertEqual(payload["entities"]["observation"]["time_context"]["canonical"], "持续多日")
        self.assertEqual(payload["mapping_records"], [])
        self.assertEqual(payload["source_refs"], [])

    def test_structured_record_preserves_source_fields_and_reviewed_status(self) -> None:
        record = {
            "EC": "EC-001",
            "FP": "Cowling 组装NG",
            "RC": "吸取偏移",
            "PA": "检查吸嘴位置",
            "action_steps": ["检查吸嘴位置", "检查吸取点位"],
        }

        state = canonicalize_structured_record(
            record,
            source_id="reviewed_structured_chain_v1",
            source_type="reviewed_structured_chain",
            status=REVIEWED,
            record_id="row-1",
        )
        mapping = state.as_dict()["mapping_records"][0]

        self.assertEqual(mapping["status"], REVIEWED)
        self.assertFalse(mapping["requires_review"])
        self.assertEqual(mapping["error_code"]["source_field"], "EC")
        self.assertEqual(mapping["fault"]["source_field"], "FP")
        self.assertEqual(mapping["cause"]["source_field"], "RC")
        self.assertEqual(mapping["action"]["source_field"], "PA")
        self.assertEqual(mapping["action_steps"][0]["action"]["source_field"], "PA")
        self.assertTrue(mapping["evidence_refs"][0]["reviewed"])

    def test_case_candidate_stays_candidate_and_requires_review(self) -> None:
        state = canonicalize_case_candidate(
            {
                "FP": "cowling组装NG",
                "RC": "吸取或定位偏移",
                "PA": "检查吸嘴位置和吸取点位",
            },
            source_id="rag_fp_case_candidates_v1",
            record_id="case-cowling-ng-001",
        )
        mapping = state.as_dict()["mapping_records"][0]

        self.assertEqual(mapping["status"], CANDIDATE)
        self.assertTrue(mapping["requires_review"])
        self.assertFalse(mapping["evidence_refs"][0]["reviewed"])
        self.assertEqual(mapping["fault"]["source_field"], "FP")

    def test_case_candidate_preserves_route_c_boundary_metadata(self) -> None:
        state = canonicalize_case_candidate(
            {
                "FP": "cowling组装NG",
                "RC": "吸取或定位偏移",
                "PA": "检查吸嘴位置和吸取点位",
                "route_target": "case_retrieval",
                "publication_status": "candidate",
                "field_allowlist": ["FP", "RC", "PA"],
                "promotion_rules": {"route_a_in_place_promotion": False},
            },
            source_id="rag_fp_case_candidates_v1",
            record_id="case-cowling-ng-001",
        )
        source_ref = state.as_dict()["source_refs"][0]

        self.assertEqual(source_ref["metadata"]["route_target"], "case_retrieval")
        self.assertEqual(source_ref["metadata"]["publication_status"], "candidate")
        self.assertEqual(source_ref["metadata"]["field_allowlist"], ["FP", "RC", "PA"])
        self.assertFalse(source_ref["metadata"]["promotion_rules"]["route_a_in_place_promotion"])
        self.assertFalse(source_ref["reviewed"])

    def test_serving_document_is_evidence_only_and_does_not_create_mapping_record(self) -> None:
        state = canonicalize_serving_document(
            {
                "text": "SOP suggests checking nozzle pickup position.",
                "serving_safe": True,
            },
            source_id="serving_unstructured_vlm",
            record_id="chunk-1",
        )
        payload = state.as_dict()

        self.assertEqual(payload["mapping_records"], [])
        self.assertEqual(payload["source_refs"][0]["source_type"], "serving_document")
        self.assertTrue(payload["source_refs"][0]["serving_safe"])
        self.assertFalse(payload["source_refs"][0]["reviewed"])
        self.assertIn("nozzle", payload["entities"]["observation"]["phenomenon_text"]["canonical"])

    def test_serving_vlm_text_preserves_route_b_block_metadata(self) -> None:
        state = canonicalize_serving_document(
            {
                "text": "Masked VLM observation: nozzle pickup position may be offset.",
                "serving_safe": True,
                "block_type": "vlm_text",
                "source_anchor": "page-1:block-3:image-2",
                "retrieval_eligible": True,
                "graph_eligible": False,
                "derived_from_block_type": "figure",
                "raw_asset_included": False,
            },
            source_id="serving_unstructured_vlm",
            record_id="chunk-vlm-1",
        )
        payload = state.as_dict()
        source_ref = payload["source_refs"][0]

        self.assertEqual(payload["mapping_records"], [])
        self.assertEqual(source_ref["anchor"], "page-1:block-3:image-2")
        self.assertEqual(source_ref["metadata"]["block_type"], "vlm_text")
        self.assertTrue(source_ref["metadata"]["retrieval_eligible"])
        self.assertFalse(source_ref["metadata"]["graph_eligible"])
        self.assertEqual(source_ref["metadata"]["derived_from_block_type"], "figure")
        self.assertFalse(source_ref["metadata"]["raw_asset_included"])

    def test_document_adapter_rejects_non_serving_safe_input(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_serving_document(
                {"text": "raw internal snippet", "serving_safe": False},
                source_id="data/processed/unstructured_vlm",
            )

    def test_serving_document_batch_builds_offline_artifact_without_mappings(self) -> None:
        artifact = canonicalize_serving_document_batch(
            [
                {
                    "chunk_id": "chunk-sop-nozzle-001",
                    "text": "SOP suggests checking nozzle pickup position when cowling assembly is NG.",
                    "serving_safe": True,
                },
                {
                    "chunk_id": "chunk-sop-light-002",
                    "text": "Check sensor light status before replacing parts.",
                    "serving_safe": True,
                    "anchor": "page-2:block-7",
                },
            ],
            source_id="serving_unstructured_vlm",
        )

        self.assertEqual(artifact["mode"], "offline_batch_serving_document")
        self.assertEqual(artifact["record_count"], 2)
        self.assertEqual(artifact["summary"]["mapping_record_count"], 0)
        self.assertEqual(artifact["summary"]["status"], "evidence_only")
        first_record = artifact["records"][0]
        self.assertEqual(first_record["mapping_records"], [])
        self.assertEqual(first_record["source_refs"][0]["record_id"], "chunk-sop-nozzle-001")
        self.assertFalse(first_record["source_refs"][0]["reviewed"])

    def test_result_projection_only_exposes_query_and_entities(self) -> None:
        state = canonicalize_query("EC-001 是什么？", received_at="2026-04-28T10:30:00+08:00")

        projection = state.result_projection()

        self.assertEqual(set(projection.keys()), {"query", "entities"})
        self.assertNotIn("mapping_records", projection)


if __name__ == "__main__":
    unittest.main()
