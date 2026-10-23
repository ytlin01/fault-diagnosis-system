from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.reasoning.route_graph import (
    LangGraphUnavailableError,
    _derive_user_root_cause,
    _normalize_conclusion_results,
    build_route_graph,
    route_a_structured_slot,
    run_route_graph,
    run_route_graph_dry_run,
)
from services.routing.query_router import (
    CASE_RETRIEVAL,
    DOCUMENT_EVIDENCE_RETRIEVAL,
    INSUFFICIENT_CONTEXT,
    REVIEWED_DIAGNOSTIC_CHAIN,
    ROUTE_A_STRUCTURED,
    ROUTE_B_DOCUMENT,
    ROUTE_C_CASE_GOVERNANCE,
    ROUTE_FALLBACK,
    RoutingContext,
)


class RouteGraphTests(unittest.TestCase):
    def test_route_a_root_cause_uses_highest_confidence_possible_cause(self) -> None:
        conclusion = {
            "diagnosis_results": [
                {"title": "r1", "possible_cause": "次要原因", "confidence": "low", "description": "", "evidence": []},
                {"title": "r2", "possible_cause": "主要根因", "confidence": "high", "description": "", "evidence": []},
            ]
        }
        normalized = _normalize_conclusion_results(conclusion, REVIEWED_DIAGNOSTIC_CHAIN)
        self.assertEqual(normalized[0]["possible_cause"], "主要根因")
        self.assertEqual(_derive_user_root_cause(normalized), "主要根因")

    def test_route_a_root_cause_fallback_only_when_no_possible_cause_exists(self) -> None:
        conclusion = {
            "root_cause": "没有明确根因",
            "diagnosis_results": [
                {"title": "r1", "possible_cause": "候选原因", "confidence": "medium", "description": "", "evidence": []},
            ],
        }
        normalized = _normalize_conclusion_results(conclusion, REVIEWED_DIAGNOSTIC_CHAIN)
        self.assertEqual(_derive_user_root_cause(normalized), "候选原因")

    def test_route_c_fault_query_reaches_case_governance_slot(self) -> None:
        state = run_route_graph_dry_run(
            {
                "query_text": "cowling fault with no reviewed chain",
                "received_at": "2026-04-29T10:30:00+08:00",
                "available_sources": [
                    "error_codes_standardized_serving",
                    "rag_fp_case_candidates_v1",
                    "data/serving_unstructured_vlm",
                ],
            }
        )

        decision = state["api_response"]["decision"]
        used_source = state["api_response"]["knowledge_context"]["used_sources"][0]
        self.assertEqual(decision["route_family"], ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision["route"], CASE_RETRIEVAL)
        self.assertEqual(decision["answer_type"], "case_reference")
        self.assertEqual(decision["status"], "candidate")
        self.assertTrue(
            all(item["result_type"] != "confirmed_diagnosis" for item in state["api_response"]["diagnosis_results"])
        )
        self.assertEqual(used_source["source_type"], "structured_case_candidate")
        self.assertEqual(set(used_source), {"source_type", "source_id", "snapshot_id", "updated_at"})
        source_metadata = state["route_output"]["source_metadata"][0]
        self.assertEqual(source_metadata["route_target"], "case_retrieval")
        self.assertEqual(source_metadata["contract_scope"], "route_c_source_boundary_v1")
        self.assertNotIn("tokens", state["api_response"]["query"])

    def test_route_c_governance_slot_exposes_boundary_metadata(self) -> None:
        state = run_route_graph_dry_run(
            {
                "query_text": "feeder z axis enable failed",
                "available_sources": ["structured_fp_join_v1_baseline"],
            }
        )

        decision = state["api_response"]["decision"]
        used_source = state["api_response"]["knowledge_context"]["used_sources"][0]
        self.assertEqual(decision["route_family"], ROUTE_C_CASE_GOVERNANCE)
        self.assertEqual(decision["route"], "fp_review_governance")
        self.assertEqual(used_source["source_type"], "governance_candidate")
        self.assertEqual(set(used_source), {"source_type", "source_id", "snapshot_id", "updated_at"})
        source_metadata = state["route_output"]["source_metadata"][0]
        self.assertEqual(source_metadata["route_target"], "fp_review_governance")
        self.assertIn("mapping_id", source_metadata["field_allowlist"])

    def test_route_b_document_query_reaches_document_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            serving_doc = Path(tmp) / "sop_feeder_calibration.json"
            serving_doc.write_text(
                json.dumps(
                    {
                        "doc_id": "sop_feeder_calibration",
                        "blocks": [
                            {
                                "block_id": "b0001",
                                "block_type": "text",
                                "text": "SOP feeder calibration procedure for the feed axis.",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            state = run_route_graph_dry_run(
                {
                    "query_text": "SOP feeder calibration procedure",
                    "available_sources": ["data/serving_unstructured_vlm"],
                    "route_b_source_dir": tmp,
                }
            )

        decision = state["api_response"]["decision"]
        self.assertEqual(decision["route_family"], ROUTE_B_DOCUMENT)
        self.assertEqual(decision["route"], DOCUMENT_EVIDENCE_RETRIEVAL)
        self.assertEqual(decision["answer_type"], "document_evidence")
        self.assertEqual(decision["status"], "evidence_only")
        self.assertEqual(
            state["api_response"]["knowledge_context"]["used_sources"][0]["source_type"],
            "serving_document",
        )

    def test_fallback_produces_empty_sources_and_not_available_status(self) -> None:
        state = run_route_graph_dry_run(
            {
                "query_text": "check",
                "available_sources": ["data/raw/unstructured_input/example.docx"],
            }
        )

        decision = state["api_response"]["decision"]
        self.assertEqual(decision["route_family"], ROUTE_FALLBACK)
        self.assertEqual(decision["route"], INSUFFICIENT_CONTEXT)
        self.assertEqual(decision["answer_type"], "insufficient_context")
        self.assertEqual(decision["status"], "not_available")
        self.assertEqual(state["api_response"]["knowledge_context"]["used_sources"], [])

    def test_route_a_slot_is_guarded_without_allowed_reviewed_source(self) -> None:
        output = route_a_structured_slot(
            {
                "routing_decision": {
                    "route_family": ROUTE_A_STRUCTURED,
                    "route": REVIEWED_DIAGNOSTIC_CHAIN,
                    "intent": "fault_phenomenon",
                    "reason": "forced test state",
                    "allowed_sources": [],
                    "blocked_sources": [],
                    "requires_review": False,
                    "kg_eligible": True,
                    "confidence": "high",
                },
                "trace": {"enabled": False, "node_events": []},
            }
        )

        self.assertEqual(output["route_output"]["used_sources"], [])
        self.assertIn("guarded", output["route_output"]["warnings"][0])

    @patch(
        "services.retrieval.route_a_executor.get_driver",
        side_effect=RuntimeError("Neo4j unavailable in test"),
    )
    def test_route_a_calls_text2cypher_executor(self, _mock_driver: object) -> None:
        # Route A now calls the real text2cypher executor (TASK-018).
        # The query "What does M07LOM1-01-03 mean?" has no matching CAD node name,
        # so the executor returns an empty result with a warning — not the old
        # stub warning about "deferred" execution.
        #
        # The Neo4j driver boundary is mocked so the unit test never opens a
        # live BoltDriver connection (which previously leaked an unclosed
        # driver and emitted a ResourceWarning); the executor's graceful
        # Neo4j-unavailable failure path is still exercised deterministically.
        state = run_route_graph_dry_run(
            {
                "query_text": "What does M07LOM1-01-03 mean?",
                "available_sources": ["reviewed_diagnostic_chain_v1"],
            },
            routing_context=RoutingContext(reviewed_diagnostic_chain_available=True),
        )

        decision = state["api_response"]["decision"]
        self.assertEqual(decision["route_family"], ROUTE_A_STRUCTURED)
        self.assertEqual(decision["route"], REVIEWED_DIAGNOSTIC_CHAIN)
        self.assertEqual(decision["status"], "reviewed")
        self.assertEqual(state["api_response"]["diagnosis_results"], [])
        # Executor returns empty sources when no entity is resolved or Neo4j is unavailable
        self.assertIsInstance(state["api_response"]["knowledge_context"]["used_sources"], list)
        # Executor warning must be present; the old stub "deferred" warning is gone
        self.assertTrue(state["route_output"]["warnings"])
        self.assertNotIn("deferred", state["route_output"]["warnings"][0])

    def test_compiled_langgraph_is_buildable_when_dependency_is_installed(self) -> None:
        try:
            graph = build_route_graph()
        except LangGraphUnavailableError as exc:
            self.skipTest(str(exc))
        self.assertTrue(hasattr(graph, "invoke"))

    def test_compiled_langgraph_runs_end_to_end_when_dependency_is_installed(self) -> None:
        try:
            state = run_route_graph(
                {
                    "query_text": "SOP feeder calibration procedure",
                    "available_sources": ["data/serving_unstructured_vlm"],
                }
            )
        except LangGraphUnavailableError as exc:
            self.skipTest(str(exc))

        self.assertEqual(state["api_response"]["decision"]["route_family"], ROUTE_B_DOCUMENT)
        self.assertEqual(state["api_response"]["decision"]["route"], DOCUMENT_EVIDENCE_RETRIEVAL)


if __name__ == "__main__":
    unittest.main()
