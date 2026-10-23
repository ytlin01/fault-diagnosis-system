from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.providers.llm import StubProvider
from services.reasoning.route_graph import run_route_graph_dry_run
from services.reasoning.unified_answer_assembler import fixture_route_output, synthesize_route_output
from services.routing.query_router import CASE_RETRIEVAL, DOCUMENT_EVIDENCE_RETRIEVAL


class UnifiedAnswerAssemblerTests(unittest.TestCase):
    def test_route_b_fixture_assembles_evidence_only(self) -> None:
        fixture = _fixture("route_b", "RB-SAFE-001")
        route_output = fixture_route_output(fixture)
        conclusion = synthesize_route_output(
            fixture["input"]["query_text"],
            DOCUMENT_EVIDENCE_RETRIEVAL,
            route_output,
            provider=StubProvider(),
        )

        self.assertEqual(conclusion["route_used"], "route_b")
        self.assertEqual(conclusion["root_cause_actions"], [])
        self.assertIn("不确认根因", conclusion["root_cause"])
        self.assertEqual(len(conclusion["diagnosis_results"]), 1)
        result = conclusion["diagnosis_results"][0]
        self.assertIsNone(result["possible_cause"])
        self.assertEqual(result["evidence"][0]["evidence_type"], "document_snippet")
        self.assertNotIn("confirmed_diagnosis", json.dumps(conclusion, ensure_ascii=False))
        self.assertNotIn('"status": "reviewed"', json.dumps(conclusion, ensure_ascii=False))

    def test_route_c_fixture_assembles_candidate_only(self) -> None:
        fixture = _fixture("route_c", "RC-SAFE-001")
        route_output = fixture_route_output(fixture)
        conclusion = synthesize_route_output(
            fixture["input"]["query_text"],
            CASE_RETRIEVAL,
            route_output,
            provider=StubProvider(),
        )

        self.assertEqual(conclusion["route_used"], "route_c")
        self.assertEqual(conclusion["root_cause_actions"], [])
        self.assertIn("不确认根因", conclusion["root_cause"])
        self.assertEqual(len(conclusion["diagnosis_results"]), 1)
        result = conclusion["diagnosis_results"][0]
        self.assertIsNone(result["possible_cause"])
        self.assertEqual(result["evidence"][0]["evidence_type"], "related_case")
        self.assertNotIn("confirmed_diagnosis", json.dumps(conclusion, ensure_ascii=False))
        self.assertNotIn('"status": "reviewed"', json.dumps(conclusion, ensure_ascii=False))

    def test_no_hit_fixtures_do_not_crash_or_fabricate_results(self) -> None:
        for route_name, fixture_id, route in (
            ("route_b", "RB-SAFE-002", DOCUMENT_EVIDENCE_RETRIEVAL),
            ("route_b", "RB-SAFE-004", DOCUMENT_EVIDENCE_RETRIEVAL),
            ("route_c", "RC-SAFE-002", CASE_RETRIEVAL),
        ):
            fixture = _fixture(route_name, fixture_id)
            route_output = fixture_route_output(fixture)
            conclusion = synthesize_route_output(
                fixture["input"]["query_text"],
                route,
                route_output,
                provider=StubProvider(),
            )
            self.assertEqual(conclusion["diagnosis_results"], [])
            self.assertEqual(conclusion["root_cause_actions"], [])
            self.assertTrue(conclusion["warnings"])

    def test_serving_safe_fixture_sets_cover_required_smoke_categories(self) -> None:
        route_b = _fixture_payload("route_b")
        route_c = _fixture_payload("route_c")

        route_b_scenarios = {item["scenario"] for item in route_b["fixtures"]}
        self.assertTrue(
            {
                "normal_document_evidence_hit",
                "graphrag_neo4j_evidence_only",
                "no_hit_insufficient_evidence",
                "source_safety_negative",
            }.issubset(route_b_scenarios)
        )
        route_b_negative = _fixture("route_b", "RB-SAFE-004")
        self.assertTrue(route_b_negative["expected"]["source_safety_negative"])
        self.assertTrue(route_b_negative["expected"]["no_hit"])

        route_c_scenarios = {item["scenario"] for item in route_c["fixtures"]}
        self.assertTrue({"normal_case_reference_hit", "no_hit", "hard_case", "candidate_only_safety"}.issubset(route_c_scenarios))
        route_c_candidate_only = _fixture("route_c", "RC-SAFE-004")
        self.assertTrue(route_c_candidate_only["expected"]["candidate_only"])
        self.assertEqual(route_c_candidate_only["expected"]["status"], "candidate")

    def test_route_graph_route_b_response_stays_schema_shaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "serving"
            source_dir.mkdir()
            (source_dir / "sop_serving.json").write_text(
                json.dumps(
                    {
                        "doc_id": "demo_sop",
                        "blocks": [
                            {
                                "block_id": "b1",
                                "block_type": "text",
                                "text": "SOP TCP IPv4 IP address settings",
                                "serving_eligible": True,
                                "retrieval_eligible": True,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            state = run_route_graph_dry_run(
                {
                    "query_text": "SOP TCP IPv4 IP address settings",
                    "available_sources": ["data/serving_unstructured_vlm"],
                    "route_b_source_dir": str(source_dir),
                    "_provider": StubProvider(),
                }
            )

        response = state["api_response"]
        _assert_result_design_core(self, response)
        self.assertEqual(response["decision"]["answer_type"], "document_evidence")
        self.assertEqual(response["decision"]["status"], "evidence_only")
        self.assertEqual(response["root_cause_actions"], [])
        self.assertEqual(response["diagnosis_results"][0]["result_type"], "document_evidence")
        self.assertEqual(response["diagnosis_results"][0]["status"], "evidence_only")


def _fixture(route_name: str, fixture_id: str) -> dict:
    payload = _fixture_payload(route_name)
    for item in payload["fixtures"]:
        if item["fixture_id"] == fixture_id:
            return item
    raise AssertionError(f"fixture not found: {fixture_id}")


def _fixture_payload(route_name: str) -> dict:
    path = Path("data/eval") / route_name / f"{route_name}_serving_safe_fixtures_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_result_design_core(testcase: unittest.TestCase, response: dict) -> None:
    testcase.assertEqual(
        set(response),
        {
            "contract_version",
            "query",
            "decision",
            "entities",
            "knowledge_context",
            "summary",
            "diagnosis_results",
            "root_cause",
            "root_cause_actions",
        },
    )
    testcase.assertIn(response["decision"]["status"], {"reviewed", "candidate", "evidence_only", "not_available"})


if __name__ == "__main__":
    unittest.main()
