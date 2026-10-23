"""Tests for the opt-in Route C Qwen vector index adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from services.retrieval.route_c_qwen_vector import search_route_c_qwen_cases


class RouteCQwenVectorTests(unittest.TestCase):
    def test_search_returns_candidate_hit_from_normalized_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            record = {
                "rag_candidate_id": "C1STN_CASE_TEST",
                "source_type": "structured_case_candidate",
                "relation_type": "related_case",
                "route_target": "rag_case_pool",
                "field_fp_variants": ["motor alarm"],
                "field_fp_normalized": "motor alarm",
                "RC": "suspected motor wear",
                "PA": "replace motor",
                "evidence": {"dt_mins": 5},
                "source_refs": [{"source_row": 2}],
                "filter_basis": {"reason": "test"},
            }
            (directory / "metadata.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            np.save(directory / "vectors.npy", np.asarray([[1.0, 0.0]], dtype=np.float32))
            (directory / "index_manifest.json").write_text(
                json.dumps(
                    {
                        "embedding_model": "qwen3-embedding:4b",
                        "embedding_dimensions": 2,
                        "vector_file": "vectors.npy",
                        "metadata_file": "metadata.jsonl",
                        "route_target": "rag_case_pool",
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "services.retrieval.route_c_qwen_vector._embed_query",
                return_value=np.asarray([1.0, 0.0], dtype=np.float32),
            ):
                hits = search_route_c_qwen_cases(
                    "motor alarm",
                    index_dir=directory,
                    top_k=1,
                    min_score=0.9,
                )

            self.assertEqual([hit.record.case_id for hit in hits], ["C1STN_CASE_TEST"])
            self.assertEqual(hits[0].record.source_record["RC"], "suspected motor wear")
            self.assertAlmostEqual(hits[0].score, 1.0)

    def test_model_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "index_manifest.json").write_text(
                json.dumps(
                    {
                        "embedding_model": "other-model",
                        "route_target": "rag_case_pool",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                search_route_c_qwen_cases(
                    "motor alarm", index_dir=directory, top_k=1
                )


if __name__ == "__main__":
    unittest.main()
