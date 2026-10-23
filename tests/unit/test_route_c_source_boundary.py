from __future__ import annotations

import unittest

from services.routing.route_c_source_boundary import (
    allowed_fields_for_source,
    allowed_route_c_sources,
    blocked_route_c_material,
    project_route_c_record,
    route_c_contract_version,
    route_c_policy,
    route_c_source_metadata,
    route_c_target_for_source,
)


class RouteCSourceBoundaryTests(unittest.TestCase):
    def test_contract_exposes_expected_official_sources(self) -> None:
        self.assertEqual(
            allowed_route_c_sources(),
            (
                "rag_fp_case_candidates_v1",
                "structured_fp_join_v1_baseline",
                "error_codes_standardized_serving",
            ),
        )
        self.assertEqual(route_c_contract_version(), "route_c_source_boundary_v1")

    def test_target_mapping_matches_task_boundary(self) -> None:
        self.assertEqual(route_c_target_for_source("rag_fp_case_candidates_v1"), "case_retrieval")
        self.assertEqual(route_c_target_for_source("structured_fp_join_v1_baseline"), "fp_review_governance")
        self.assertEqual(route_c_target_for_source("error_codes_standardized_serving"), "structured_catalog")

    def test_policy_disallows_in_place_promotion(self) -> None:
        policy = route_c_policy()
        self.assertFalse(policy["route_c_may_emit_confirmed_diagnosis"])
        self.assertFalse(policy["review_or_candidate_material_may_promote_in_place"])

        metadata = route_c_source_metadata("structured_fp_join_v1_baseline")
        self.assertFalse(metadata["promotion_rules"]["may_promote_to_reviewed_diagnosis"])
        self.assertEqual(metadata["publication_status"], "review_only")

    def test_projection_keeps_only_allowlisted_fields(self) -> None:
        record = {
            "rag_candidate_id": "RAG_123",
            "source_type": "field_case_without_standard_fp",
            "relation_type": "case_evidence",
            "route_target": "rag_case_pool",
            "field_fp_variants": ["sample"],
            "field_fp_normalized": "sample",
            "RC": ["pending"],
            "PA": ["check"],
            "evidence": {"count": 1},
            "source_refs": [{"source": "y25_downtime"}],
            "filter_basis": {"reason": "No baseline candidate.", "debug": "drop"},
            "extra_field": "drop",
        }

        projection = project_route_c_record("rag_fp_case_candidates_v1", record)

        self.assertEqual(
            set(projection.keys()),
            set(field.split(".")[0] for field in allowed_fields_for_source("rag_fp_case_candidates_v1")),
        )
        self.assertEqual(projection["filter_basis"], {"reason": "No baseline candidate."})
        self.assertNotIn("extra_field", projection)

    def test_intermediate_aggregate_is_marked_blocked(self) -> None:
        blocked = blocked_route_c_material()
        self.assertIn("structured_fp_join_v1_semantic", blocked)


if __name__ == "__main__":
    unittest.main()
