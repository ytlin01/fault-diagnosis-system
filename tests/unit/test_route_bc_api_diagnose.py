from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apps.api.diagnose import diagnose
from services.providers import CompanyApiProvider, ProviderRequest, StubProvider, build_provider
from services.reasoning.route_graph import route_a_structured_slot, run_route_graph_dry_run
from services.retrieval.route_b_executor import execute_route_b_document
from services.retrieval.route_c_executor import execute_route_c
from services.routing.query_router import REVIEWED_DIAGNOSTIC_CHAIN, ROUTE_A_STRUCTURED


class RouteBcApiDiagnoseTests(unittest.TestCase):
    def test_route_b_executor_reads_only_serving_safe_document_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "serving"
            source_dir.mkdir()
            _write_json(
                source_dir / "sop_serving.json",
                {
                    "doc_id": "demo_sop",
                    "serving_policy": {"raw_assets_included": False},
                    "blocks": [
                        {
                            "block_id": "b1",
                            "block_type": "vlm_text",
                            "text": "SOP feeder calibration procedure and visual summary",
                            "serving_eligible": True,
                            "retrieval_eligible": True,
                        },
                        {
                            "block_id": "b2",
                            "block_type": "image",
                            "asset_ref": "must_not_be_read_as_evidence",
                            "serving_eligible": False,
                        },
                    ],
                },
            )

            output = execute_route_b_document(
                "SOP feeder calibration procedure",
                allowed_sources=("data/serving_unstructured_vlm", "data/processed/unstructured_vlm"),
                source_dir=source_dir,
            )

        self.assertEqual(output["used_sources"][0]["source_type"], "serving_document")
        self.assertEqual(output["items"][0]["result_type"], "document_evidence")
        self.assertEqual(output["items"][0]["status"], "evidence_only")
        self.assertEqual(output["items"][0]["evidence"][0]["evidence_type"], "document_snippet")
        self.assertNotIn("asset_ref", json.dumps(output["items"], ensure_ascii=False))

    def test_route_b_executor_blocks_internal_canonical_source_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "data" / "processed" / "unstructured_vlm"
            source_dir.mkdir(parents=True)
            _write_json(
                source_dir / "internal.json",
                {
                    "doc_id": "internal_doc",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "block_type": "text",
                            "text": "internal canonical text must not be served",
                        }
                    ],
                },
            )

            output = execute_route_b_document(
                "internal canonical",
                allowed_sources=("data/serving_unstructured_vlm",),
                source_dir=source_dir,
            )

        self.assertEqual(output["items"], [])
        self.assertEqual(output["used_sources"], [])
        self.assertIn("blocked", output["warnings"][0].lower())

    def test_route_c_structured_catalog_returns_candidate_only_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog_path = Path(tmp) / "error_codes_standardized_serving.json"
            _write_json(
                catalog_path,
                [
                    {
                        "Index": 78,
                        "Item": "motor",
                        "Error code": "M07LOM1-01-03",
                        "Description": "Z axis servo communication abnormal",
                        "secret": "drop",
                    }
                ],
            )

            output = execute_route_c(
                "What does M07LOM1-01-03 mean?",
                route="structured_catalog",
                allowed_sources=("error_codes_standardized_serving",),
                source_paths={"error_codes_standardized_serving": catalog_path},
            )

        item = output["items"][0]
        self.assertEqual(item["result_type"], "diagnostic_hypothesis")
        self.assertEqual(item["status"], "candidate")
        self.assertNotEqual(item["result_type"], "confirmed_diagnosis")
        self.assertNotIn("secret", json.dumps(item, ensure_ascii=False))
        self.assertEqual(item["evidence"][0]["source_type"], "structured_catalog")

    def test_route_c_case_retrieval_and_governance_stay_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_path = Path(tmp) / "rag_fp_case_candidates_v1.json"
            governance_path = Path(tmp) / "structured_fp_join_v1_baseline.json"
            _write_json(
                case_path,
                {
                    "candidates": [
                        {
                            "rag_candidate_id": "RAG_1",
                            "source_type": "field_case_without_standard_fp",
                            "relation_type": "case_evidence",
                            "route_target": "rag_case_pool",
                            "field_fp_variants": ["feeder z axis enable failed"],
                            "RC": ["candidate cause"],
                            "PA": ["candidate action"],
                        }
                    ]
                },
            )
            _write_json(
                governance_path,
                {
                    "records": [
                        {
                            "mapping_id": "SEM_1",
                            "EC": "E01",
                            "standard_fp": "feeder z axis enable failed",
                            "RC": ["review cause"],
                            "PA": ["review action"],
                            "review_status": "needs_review",
                            "kg_diagnosis_eligible": False,
                            "route_target": "fp_review_governance",
                        }
                    ]
                },
            )

            case_output = execute_route_c(
                "similar case for feeder z axis enable failed",
                route="case_retrieval",
                allowed_sources=("rag_fp_case_candidates_v1",),
                source_paths={"rag_fp_case_candidates_v1": case_path},
            )
            governance_output = execute_route_c(
                "feeder z axis enable failed",
                route="fp_review_governance",
                allowed_sources=("structured_fp_join_v1_baseline",),
                source_paths={"structured_fp_join_v1_baseline": governance_path},
            )

        self.assertEqual(case_output["items"][0]["result_type"], "case_reference")
        self.assertEqual(case_output["items"][0]["status"], "candidate")
        self.assertEqual(governance_output["items"][0]["result_type"], "diagnostic_hypothesis")
        self.assertEqual(governance_output["items"][0]["status"], "candidate")
        self.assertTrue(governance_output["source_metadata"][0]["promotion_rules"]["review_only"])

    def test_api_diagnose_returns_schema_compatible_fallback(self) -> None:
        response = diagnose({"query_text": "check", "received_at": "2026-05-05T00:00:00+00:00"})

        self.assertEqual(response["contract_version"], "1.0.0-draft")
        self.assertEqual(response["decision"]["route_family"], "fallback")
        self.assertEqual(response["decision"]["route"], "insufficient_context")
        self.assertEqual(response["decision"]["status"], "not_available")
        self.assertEqual(response["knowledge_context"]["used_sources"], [])
        self.assertEqual(response["diagnosis_results"], [])
        self.assertEqual(response["root_cause"], "证据不足，暂无法确认")
        self.assertEqual(response["root_cause_actions"], [])
        self.assertEqual(set(response), {"contract_version", "query", "decision", "entities", "knowledge_context", "summary", "diagnosis_results", "root_cause", "root_cause_actions"})

    def test_route_graph_route_b_can_fill_result_design_v1_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "serving"
            source_dir.mkdir()
            _write_json(
                source_dir / "sop_serving.json",
                {
                    "doc_id": "demo_sop",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "block_type": "text",
                            "text": "SOP feeder calibration procedure",
                            "serving_eligible": True,
                            "retrieval_eligible": True,
                        }
                    ],
                },
            )

            state = run_route_graph_dry_run(
                {
                    "query_text": "SOP feeder calibration procedure",
                    "available_sources": ["data/serving_unstructured_vlm"],
                    "route_b_source_dir": str(source_dir),
                }
            )

        response = state["api_response"]
        self.assertEqual(response["decision"]["route_family"], "route_b_document")
        self.assertEqual(response["diagnosis_results"][0]["result_type"], "document_evidence")
        self.assertEqual(response["diagnosis_results"][0]["status"], "evidence_only")

    def test_route_a_guarded_slot_does_not_execute_baseline_candidates(self) -> None:
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

        self.assertEqual(output["route_output"]["items"], [])
        self.assertEqual(output["route_output"]["used_sources"], [])

    def test_provider_abstraction_contracts(self) -> None:
        stub = StubProvider()
        self.assertEqual(stub.generate(ProviderRequest(prompt="serving-safe prompt")).text, "serving-safe prompt")
        with mock.patch.dict(os.environ, {"FAULTDX_PROVIDER_TYPE": "stub"}, clear=False):
            self.assertEqual(build_provider({"type": "stub"}).provider_type, "stub")

        company = CompanyApiProvider()
        with self.assertRaises(NotImplementedError):
            company.generate(ProviderRequest(prompt="approved prompt"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
