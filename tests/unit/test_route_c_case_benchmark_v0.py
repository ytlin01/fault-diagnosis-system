from __future__ import annotations

import unittest

from scripts.run_eval.run_route_c_case_benchmark_v0 import (
    evaluate_fixture,
    load_fixture,
    summarize,
)


class RouteCCaseBenchmarkV0Tests(unittest.TestCase):
    def test_route_c_case_benchmark_blocks_wrong_source_id(self) -> None:
        fixture = dict(load_fixture())
        fixture["source_id"] = "structured_fp_join_v1_baseline"

        results = evaluate_fixture(fixture)
        summary = summarize(results, fixture)

        self.assertEqual(summary["source_safety_pass"]["passed"], 0)
        self.assertTrue(all(not result.ranked_candidate_ids for result in results))


if __name__ == "__main__":
    unittest.main()
