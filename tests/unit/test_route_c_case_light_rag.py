from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from services.providers.llm import ProviderRequest, ProviderResponse
from services.reasoning.route_graph import run_route_graph_dry_run
from services.retrieval.route_c_case_index import search_route_c_cases
from services.retrieval.route_c_case_light_rag import (
    build_light_rag_request,
    route_c_case_light_rag,
)
from services.retrieval.route_c_executor import execute_route_c


class FakeProvider:
    provider_type = "fake"

    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[ProviderRequest] = []

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(text=self.text, provider_type=self.provider_type, model="fake")


class FailingProvider:
    provider_type = "failing"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise RuntimeError("offline")


class RouteCCaseLightRagTests(unittest.TestCase):
    def test_prompt_projection_uses_only_safe_top_k_candidate_fields(self) -> None:
        hits = search_route_c_cases(
            "feeder z axis enable failed",
            [
                {
                    "rag_candidate_id": "RAG_1",
                    "source_type": "field_case_without_standard_fp",
                    "relation_type": "case_evidence",
                    "route_target": "rag_case_pool",
                    "field_fp_variants": ["feeder z axis enable failed"],
                    "field_fp_normalized": "feeder z axis enable failed",
                    "RC": ["candidate cause"],
                    "PA": ["candidate action"],
                    "evidence": {"count": 1, "raw_record": "drop"},
                    "source_refs": [{"path": "data/raw/private.xlsx"}],
                    "filter_basis": {"reason": "RAG only", "debug": "drop"},
                    "standard_fp": "not allowed",
                    "secret": "drop",
                }
            ],
            top_k=1,
        )

        request = build_light_rag_request("feeder z axis enable failed", hits)
        payload = json.loads(request.prompt)
        candidate = payload["candidates"][0]

        self.assertEqual(candidate["rag_candidate_id"], "RAG_1")
        self.assertEqual(candidate["filter_basis"], {"reason": "RAG only"})
        prompt_text = request.prompt
        self.assertNotIn("secret", prompt_text)
        self.assertNotIn('"standard_fp"', prompt_text)
        self.assertNotIn("source_refs", prompt_text)
        self.assertNotIn("data/raw", prompt_text)
        self.assertNotIn("raw_record", prompt_text)

    def test_light_rag_reranks_only_lexical_hits_and_keeps_missing_hits(self) -> None:
        hits = search_route_c_cases(
            "axis enable failed",
            [
                _case("RAG_1", "axis enable failed"),
                _case("RAG_2", "axis enable failed candidate"),
                _case("RAG_3", "axis enable failed generic"),
            ],
            top_k=3,
        )
        provider = FakeProvider(
            json.dumps(
                {
                    "ranking": [
                        {"rag_candidate_id": "RAG_2", "relevance_reason": "closer"},
                        {"rag_candidate_id": "RAG_unknown", "relevance_reason": "ignored"},
                    ],
                    "summaries": {"RAG_2": "Candidate case appears closer to the query wording."},
                }
            )
        )

        result = route_c_case_light_rag(
            "axis enable failed",
            hits,
            config={"enabled": True, "provider_type": "stub"},
            provider=provider,
        )

        self.assertEqual(result.hits[0].record.case_id, "RAG_2")
        self.assertEqual({hit.record.case_id for hit in result.hits}, {"RAG_1", "RAG_2", "RAG_3"})
        self.assertIn("RAG_2", result.summaries)

    def test_executor_light_rag_preserves_candidate_only_result_contract(self) -> None:
        provider = FakeProvider(
            json.dumps(
                {
                    "ranking": [{"rag_candidate_id": "RAG_2"}],
                    "summaries": {"RAG_2": "Similar candidate evidence, not a confirmed outcome."},
                }
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            case_path = Path(tmp) / "rag_fp_case_candidates_v1.json"
            _write_json(
                case_path,
                {
                    "candidates": [
                        _case("RAG_1", "axis enable failed"),
                        _case("RAG_2", "axis enable failed with positioning drift"),
                    ]
                },
            )

            output = execute_route_c(
                "axis enable failed positioning",
                route="case_retrieval",
                allowed_sources=("rag_fp_case_candidates_v1",),
                source_paths={"rag_fp_case_candidates_v1": case_path},
                top_k=2,
                enable_light_rag=True,
                light_rag_config={"provider_type": "stub"},
                light_rag_provider=provider,
            )

        item = output["items"][0]
        self.assertEqual(item["evidence"][0]["source_id"], "rag_fp_case_candidates_v1:RAG_2")
        self.assertEqual(item["result_type"], "case_reference")
        self.assertEqual(item["status"], "candidate")
        self.assertEqual(item["evidence"][0]["source_type"], "structured_case_candidate")
        self.assertEqual(item["actions"][0]["source_status"], "candidate_supported")
        self.assertNotIn("confirmed_diagnosis", json.dumps(item, ensure_ascii=False))
        self.assertNotIn("reviewed_structured_chain", json.dumps(item, ensure_ascii=False))

    def test_provider_failure_falls_back_to_lexical_ranking(self) -> None:
        hits = search_route_c_cases(
            "feeder axis",
            [_case("RAG_1", "feeder axis"), _case("RAG_2", "generic alarm")],
            top_k=2,
        )

        result = route_c_case_light_rag(
            "feeder axis",
            hits,
            config={"enabled": True, "provider_type": "stub"},
            provider=FailingProvider(),
        )

        self.assertEqual([hit.record.case_id for hit in result.hits], [hit.record.case_id for hit in hits])
        self.assertTrue(any("lexical ranking retained" in warning for warning in result.warnings))

    def test_light_rag_does_not_expand_blocked_sources(self) -> None:
        output = execute_route_c(
            "semantic candidates as cases",
            route="case_retrieval",
            allowed_sources=("structured_fp_join_v1_semantic", "data/processed/aggregates"),
            enable_light_rag=True,
            light_rag_config={"provider_type": "stub"},
        )

        self.assertEqual(output["items"], [])
        self.assertTrue(any("Blocked Route C source" in warning for warning in output["warnings"]))

    def test_route_graph_requires_explicit_light_rag_enablement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_path = Path(tmp) / "rag_fp_case_candidates_v1.json"
            _write_json(case_path, {"candidates": [_case("RAG_1", "case retrieval smoke")]})

            state = run_route_graph_dry_run(
                {
                    "query_text": "case retrieval smoke",
                    "query_type_hint": "case_retrieval",
                    "available_sources": ["rag_fp_case_candidates_v1"],
                    "route_c_source_paths": {"rag_fp_case_candidates_v1": str(case_path)},
                    "route_c_light_rag": {"enabled": True, "provider_type": "stub"},
                }
            )

        response = state["api_response"]
        self.assertEqual(response["decision"]["route"], "case_retrieval")
        self.assertEqual(response["diagnosis_results"][0]["result_type"], "case_reference")
        self.assertEqual(response["diagnosis_results"][0]["status"], "candidate")


def _case(candidate_id: str, text: str) -> dict[str, Any]:
    return {
        "rag_candidate_id": candidate_id,
        "source_type": "field_case_without_standard_fp",
        "relation_type": "case_evidence",
        "route_target": "rag_case_pool",
        "field_fp_variants": [text],
        "field_fp_normalized": text,
        "RC": ["candidate cause"],
        "PA": ["candidate action"],
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
