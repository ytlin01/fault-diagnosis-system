from __future__ import annotations

import unittest

from services.routing.query_router import (
    ASSET_STRUCTURED_QUERY,
    CASE_RETRIEVAL,
    DOCUMENT_EVIDENCE_RETRIEVAL,
    FP_REVIEW_GOVERNANCE,
    INSUFFICIENT_CONTEXT,
    INTENT_ASSET,
    INTENT_DOCUMENT_PROCEDURE,
    INTENT_ERROR_CODE,
    INTENT_FAULT_PHENOMENON,
    REVIEWED_DIAGNOSTIC_CHAIN,
    ROUTE_A_STRUCTURED,
    ROUTE_B_DOCUMENT,
    ROUTE_C_CASE_GOVERNANCE,
    ROUTE_FALLBACK,
    STRUCTURED_CATALOG,
    RoutingContext,
    RoutingRequest,
    route_query,
)


class QueryRouterTests(unittest.TestCase):
    def test_error_code_routes_to_route_c_catalog_fallback_without_reviewed_chain(self) -> None:
        decision = route_query(RoutingRequest(query_text="What does M07LOM1-01-03 mean?"))

        self.assertEqual(decision.intent, INTENT_ERROR_CODE)
        self.assertEqual(decision.route_family, ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision.route, STRUCTURED_CATALOG)
        self.assertFalse(decision.kg_eligible)
        self.assertIn("error_codes_standardized_serving", decision.allowed_sources)
        self.assertIn("catalog fallback", decision.reason)

    def test_error_code_routes_to_reviewed_chain_when_context_allows_it(self) -> None:
        request = RoutingRequest(
            query_text="What does M07LOM1-01-03 mean?",
            available_sources=("reviewed_diagnostic_chain_v1", "structured_fp_join_v1_baseline"),
        )
        context = RoutingContext(reviewed_diagnostic_chain_available=True)

        decision = route_query(request, context)

        self.assertEqual(decision.route_family, ROUTE_A_STRUCTURED)
        self.assertEqual(decision.route, REVIEWED_DIAGNOSTIC_CHAIN)
        self.assertTrue(decision.kg_eligible)
        self.assertIn("reviewed_diagnostic_chain_v1", decision.allowed_sources)
        self.assertTrue(any(blocked.source == "structured_fp_join_v1_baseline" for blocked in decision.blocked_sources))

    def test_fault_phenomenon_prefers_route_a_but_falls_back_to_case_retrieval(self) -> None:
        decision = route_query(RoutingRequest(query_text="feeder z axis enable failed"))

        self.assertEqual(decision.intent, INTENT_FAULT_PHENOMENON)
        self.assertEqual(decision.route_family, ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision.route, CASE_RETRIEVAL)
        self.assertFalse(decision.kg_eligible)
        self.assertIn("Route A", decision.reason)

    def test_fault_phenomenon_uses_review_governance_when_only_baseline_exists(self) -> None:
        request = RoutingRequest(
            query_text="feeder z axis enable failed",
            available_sources=("structured_fp_join_v1_baseline",),
        )

        decision = route_query(request)

        self.assertEqual(decision.intent, INTENT_FAULT_PHENOMENON)
        self.assertEqual(decision.route_family, ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision.route, FP_REVIEW_GOVERNANCE)
        self.assertTrue(decision.requires_review)
        self.assertIn("structured_fp_join_v1_baseline", decision.allowed_sources)

    def test_fault_phenomenon_routes_to_reviewed_chain_when_reviewed_chain_exists(self) -> None:
        request = RoutingRequest(
            query_text="feeder z axis enable failed",
            available_sources=("reviewed_diagnostic_chain_v1", "rag_fp_case_candidates_v1"),
        )
        context = RoutingContext(reviewed_diagnostic_chain_available=True)

        decision = route_query(request, context)

        self.assertEqual(decision.route_family, ROUTE_A_STRUCTURED)
        self.assertEqual(decision.route, REVIEWED_DIAGNOSTIC_CHAIN)
        self.assertTrue(decision.kg_eligible)
        self.assertTrue(any(blocked.source == "rag_fp_case_candidates_v1" for blocked in decision.blocked_sources))

    def test_asset_query_routes_to_asset_structured_query_when_source_exists(self) -> None:
        request = RoutingRequest(
            query_text="which module owns feeder z axis",
            query_type_hint="asset",
            available_sources=("asset_kg_v1",),
        )

        decision = route_query(request)

        self.assertEqual(decision.intent, INTENT_ASSET)
        self.assertEqual(decision.route_family, ROUTE_A_STRUCTURED)
        self.assertEqual(decision.route, ASSET_STRUCTURED_QUERY)
        self.assertIn("asset_kg_v1", decision.allowed_sources)

    def test_asset_query_falls_back_when_asset_source_is_unavailable(self) -> None:
        request = RoutingRequest(
            query_text="which module owns feeder z axis",
            query_type_hint="asset",
            available_sources=("error_codes_standardized_serving",),
        )

        decision = route_query(request)

        self.assertEqual(decision.route_family, ROUTE_FALLBACK)
        self.assertEqual(decision.route, INSUFFICIENT_CONTEXT)

    def test_document_query_allows_serving_vlm_and_blocks_internal_vlm(self) -> None:
        request = RoutingRequest(
            query_text="SOP feeder calibration procedure",
            available_sources=("data/serving_unstructured_vlm", "data/processed/unstructured_vlm"),
        )

        decision = route_query(request)

        self.assertEqual(decision.intent, INTENT_DOCUMENT_PROCEDURE)
        self.assertEqual(decision.route_family, ROUTE_B_DOCUMENT)
        self.assertEqual(decision.route, DOCUMENT_EVIDENCE_RETRIEVAL)
        self.assertIn("data/serving_unstructured_vlm", decision.allowed_sources)
        self.assertTrue(any(blocked.source == "data/processed/unstructured_vlm" for blocked in decision.blocked_sources))

    def test_case_like_query_routes_to_case_retrieval(self) -> None:
        decision = route_query(RoutingRequest(query_text="similar case history for feeder fault"))

        self.assertEqual(decision.route_family, ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision.route, CASE_RETRIEVAL)
        self.assertIn("rag_fp_case_candidates_v1", decision.allowed_sources)

    def test_deprecated_structured_catalog_alias_is_blocked(self) -> None:
        decision = route_query(
            RoutingRequest(
                query_text="What does M07LOM1-01-03 mean?",
                available_sources=("structured_error_code_catalog_v1",),
            )
        )

        self.assertEqual(decision.route, STRUCTURED_CATALOG)
        self.assertEqual(decision.allowed_sources, ())
        self.assertTrue(any(blocked.source == "structured_error_code_catalog_v1" for blocked in decision.blocked_sources))

    def test_semantic_intermediate_aggregate_is_blocked_for_route_c(self) -> None:
        decision = route_query(
            RoutingRequest(
                query_text="feeder z axis enable failed",
                available_sources=("structured_fp_join_v1_semantic",),
            )
        )

        self.assertEqual(decision.route_family, ROUTE_FALLBACK)
        self.assertEqual(decision.route, INSUFFICIENT_CONTEXT)

    def test_case_candidate_source_does_not_enter_fp_review_governance(self) -> None:
        decision = route_query(
            RoutingRequest(
                query_text="feeder z axis enable failed",
                available_sources=("rag_fp_case_candidates_v1",),
            )
        )

        self.assertEqual(decision.route_family, ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision.route, CASE_RETRIEVAL)
        self.assertNotIn("structured_fp_join_v1_baseline", decision.allowed_sources)

    def test_unknown_query_uses_safe_fallback(self) -> None:
        decision = route_query(RoutingRequest(query_text="check"))

        self.assertEqual(decision.route_family, ROUTE_FALLBACK)
        self.assertEqual(decision.route, INSUFFICIENT_CONTEXT)
        self.assertEqual(decision.confidence, "low")

    def test_raw_unknown_and_future_executors_are_blocked(self) -> None:
        request = RoutingRequest(
            query_text="SOP feeder calibration procedure",
            available_sources=(
                "data/raw/unstructured_input/example.docx",
                "unknown_demo_source",
                "graphrag",
                "text2cypher_diagnosis",
                "data/serving_unstructured_vlm",
            ),
        )

        decision = route_query(request)
        blocked_sources = {blocked.source for blocked in decision.blocked_sources}

        self.assertEqual(decision.route, DOCUMENT_EVIDENCE_RETRIEVAL)
        self.assertIn("data/raw/unstructured_input/example.docx", blocked_sources)
        self.assertIn("unknown_demo_source", blocked_sources)
        self.assertIn("graphrag", blocked_sources)
        self.assertIn("text2cypher_diagnosis", blocked_sources)

    def test_dict_request_is_supported_for_cli_or_api_callers(self) -> None:
        decision = route_query(
            {
                "query_text": "feeder z axis enable failed",
                "query_type_hint": "symptom",
                "available_sources": ["rag_fp_case_candidates_v1"],
            }
        )

        self.assertEqual(decision.intent, INTENT_FAULT_PHENOMENON)
        self.assertEqual(decision.route, CASE_RETRIEVAL)
        self.assertEqual(decision.as_dict()["route_family"], ROUTE_C_CASE_GOVERNANCE)


if __name__ == "__main__":
    unittest.main()
