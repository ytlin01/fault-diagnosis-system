from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.retrieval.route_c_case_index import (
    assemble_case_index_text,
    build_route_c_case_records,
    search_route_c_cases,
    tokenize_for_route_c_case,
)
from services.retrieval.route_c_executor import execute_route_c


class RouteCCaseIndexTests(unittest.TestCase):
    def test_case_records_project_only_task005_allowlisted_fields(self) -> None:
        records = build_route_c_case_records(
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
                    "evidence": {"count": 1},
                    "source_refs": [{"source": "y25_downtime"}],
                    "filter_basis": {"reason": "RAG only", "debug": "drop"},
                    "secret": "must not be indexed",
                    "standard_fp": "not allowlisted for this source",
                }
            ]
        )

        self.assertEqual(records[0].case_id, "RAG_1")
        self.assertNotIn("secret", json.dumps(records[0].source_record, ensure_ascii=False))
        self.assertNotIn("standard_fp", records[0].source_record)
        self.assertEqual(records[0].source_record["filter_basis"], {"reason": "RAG only"})
        self.assertIn("feeder z axis enable failed", records[0].indexed_text)

    def test_case_index_blocks_non_case_sources(self) -> None:
        warnings: list[str] = []

        records = build_route_c_case_records(
            [
                {
                    "mapping_id": "SEM_1",
                    "route_target": "fp_review_governance",
                    "standard_fp": "feeder z axis enable failed",
                }
            ],
            source_id="structured_fp_join_v1_baseline",
            warnings=warnings,
        )

        self.assertEqual(records, [])
        self.assertIn("only `rag_fp_case_candidates_v1` is allowed", warnings[0])

    def test_bm25_ranks_related_case_above_generic_case(self) -> None:
        hits = search_route_c_cases(
            "similar case feeder z axis enable failed",
            [
                {
                    "rag_candidate_id": "RAG_generic",
                    "source_type": "field_case_without_standard_fp",
                    "relation_type": "case_evidence",
                    "route_target": "rag_case_pool",
                    "field_fp_variants": ["generic alarm record"],
                    "RC": ["generic cause"],
                    "PA": ["generic action"],
                },
                {
                    "rag_candidate_id": "RAG_feeder",
                    "source_type": "field_case_without_standard_fp",
                    "relation_type": "case_evidence",
                    "route_target": "rag_case_pool",
                    "field_fp_variants": ["feeder z axis enable failed"],
                    "RC": ["candidate cause"],
                    "PA": ["candidate action"],
                },
            ],
            top_k=2,
        )

        self.assertEqual(hits[0].record.case_id, "RAG_feeder")
        self.assertGreater(hits[0].score, 0)

    def test_executor_case_retrieval_returns_schema_compatible_candidate_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_path = Path(tmp) / "rag_fp_case_candidates_v1.json"
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
                            "secret": "drop",
                        }
                    ]
                },
            )

            output = execute_route_c(
                "similar case for feeder z axis enable failed",
                route="case_retrieval",
                allowed_sources=("rag_fp_case_candidates_v1", "structured_fp_join_v1_baseline"),
                source_paths={"rag_fp_case_candidates_v1": case_path},
            )

        item = output["items"][0]
        self.assertEqual(item["result_type"], "case_reference")
        self.assertEqual(item["status"], "candidate")
        self.assertEqual(item["evidence"][0]["evidence_type"], "related_case")
        self.assertEqual(item["evidence"][0]["source_type"], "structured_case_candidate")
        self.assertEqual(item["actions"][0]["source_status"], "candidate_supported")
        self.assertNotEqual(item["result_type"], "confirmed_diagnosis")
        self.assertNotIn("reviewed_structured_chain", json.dumps(item, ensure_ascii=False))
        self.assertNotIn("secret", json.dumps(item, ensure_ascii=False))

    def test_empty_or_unreadable_case_artifact_produces_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "rag_fp_case_candidates_v1.json"
            bad_path.write_text('{"candidates": [', encoding="utf-8")

            output = execute_route_c(
                "similar case for feeder z axis enable failed",
                route="case_retrieval",
                allowed_sources=("rag_fp_case_candidates_v1",),
                source_paths={"rag_fp_case_candidates_v1": bad_path},
            )

        self.assertEqual(output["items"], [])
        self.assertTrue(any("unreadable" in warning for warning in output["warnings"]))

    def test_executor_warns_on_blocked_intermediate_aggregate(self) -> None:
        output = execute_route_c(
            "semantic candidates as cases",
            route="case_retrieval",
            allowed_sources=("structured_fp_join_v1_semantic",),
        )

        self.assertEqual(output["items"], [])
        self.assertTrue(any("Blocked Route C source" in warning for warning in output["warnings"]))

    def test_text_assembly_and_tokenizer_are_allowlist_oriented(self) -> None:
        text = assemble_case_index_text(
            {
                "field_fp_variants": ["LBAS-GE120 feeder failure"],
                "field_fp_normalized": "lbas ge120 feeder failure",
                "RC": ["candidate cause"],
                "PA": ["candidate action"],
                "filter_basis": {"reason": "RAG only"},
                "secret": "drop",
            }
        )
        tokens = tokenize_for_route_c_case("LBAS-GE120 feeder")

        self.assertIn("candidate action", text)
        self.assertNotIn("secret", text)
        self.assertIn("lbas-ge120", tokens)
        self.assertIn("ge120", tokens)

def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
