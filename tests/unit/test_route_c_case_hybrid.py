from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.retrieval.route_c_case_hybrid import search_route_c_cases_hybrid, search_route_c_cases_vector
from services.retrieval.route_c_executor import execute_route_c


class RouteCCaseHybridEvalTests(unittest.TestCase):
    def test_hybrid_projection_does_not_surface_unallowlisted_fields(self) -> None:
        records = [
            {
                "rag_candidate_id": "RAG_safe",
                "source_type": "field_case_without_standard_fp",
                "relation_type": "case_evidence",
                "route_target": "rag_case_pool",
                "field_fp_variants": ["feed axis zero return tray overturned"],
                "RC": ["candidate cause"],
                "PA": ["candidate action"],
                "source_refs": [{"path": "data/raw/private.xlsx"}],
                "secret": "drop",
                "standard_fp": "drop",
            }
        ]

        vector_hits = search_route_c_cases_vector("feed axis tray", records, top_k=1)
        hybrid_hits = search_route_c_cases_hybrid("feed axis tray", records, top_k=1)

        for hit in [*vector_hits, *hybrid_hits]:
            serialized = hit.record.indexed_text
            self.assertNotIn("secret", serialized)
            self.assertNotIn("standard_fp", serialized)
            self.assertNotIn("data/raw", serialized)
            self.assertEqual(hit.record.case_id, "RAG_safe")

    def test_executor_keeps_hybrid_results_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_path = Path(tmp) / "rag_fp_case_candidates_v1.json"
            case_path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "rag_candidate_id": "RAG_1",
                                "source_type": "field_case_without_standard_fp",
                                "relation_type": "case_evidence",
                                "route_target": "rag_case_pool",
                                "field_fp_variants": ["feed axis zero return tray overturned"],
                                "RC": ["candidate cause"],
                                "PA": ["candidate action"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            output = execute_route_c(
                "feed axis tray",
                route="case_retrieval",
                allowed_sources=("rag_fp_case_candidates_v1",),
                source_paths={"rag_fp_case_candidates_v1": case_path},
                case_ranking_strategy="hybrid_bm25_local_sparse_vector",
            )

        item = output["items"][0]
        self.assertEqual(item["result_type"], "case_reference")
        self.assertEqual(item["status"], "candidate")
        self.assertEqual(item["evidence"][0]["source_type"], "structured_case_candidate")
        self.assertEqual(item["actions"][0]["source_status"], "candidate_supported")
        self.assertNotIn("confirmed_diagnosis", json.dumps(item, ensure_ascii=False))
        self.assertNotIn("reviewed_structured_chain", json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
