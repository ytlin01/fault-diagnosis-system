from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "evaluation"
    / "route_a_expert_ranking_input_v1.schema.json"
)


class ExpertRankingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_frozen_metric_policy_constants(self) -> None:
        properties = cls_metric_properties(self.schema)
        expected = {
            "policy_version": "route_a_expert_ranking_metrics_v1",
            "ranking_depth": 5,
            "primary_metric": "cause_action_pair_recall_at_3",
            "cause_recall_cutoffs": [1, 3, 5],
            "pair_recall_cutoffs": [1, 3, 5],
            "mrr_cutoff": 5,
            "domain_correctness_label_maturities": ["reviewed", "adjudicated"],
            "abstention_safety_gate": (
                "required_abstention_requires_no_ranked_results;"
                "not_expected_abstention_is_failure"
            ),
            "composite_score": "prohibited",
        }
        self.assertEqual(
            expected,
            {name: definition["const"] for name, definition in properties.items()},
        )

    def test_top_five_constraints_are_frozen(self) -> None:
        self.assertEqual(
            5,
            self.schema["$defs"]["result"]["properties"]["rank"]["maximum"],
        )
        self.assertEqual(
            5,
            self.schema["$defs"]["case"]["properties"]["ranked_results"][
                "maxItems"
            ],
        )


def cls_metric_properties(schema: dict) -> dict:
    return schema["$defs"]["metric_policy"]["properties"]


if __name__ == "__main__":
    unittest.main()
