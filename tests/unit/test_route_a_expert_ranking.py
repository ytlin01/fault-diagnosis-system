from __future__ import annotations

import unittest

from services.evaluation.route_a_expert_ranking import (
    FROZEN_METRIC_POLICY,
    ExpertRankingInputError,
    evaluate_expert_ranking,
)


def _policy() -> dict:
    return {key: value for key, value in FROZEN_METRIC_POLICY.items()}


def _candidate() -> dict:
    return {
        "candidate_id": "cand-test",
        "graph_version": "test-graph",
        "snapshot_id": "snap-test",
        "data_maturity": "provisional",
        "config_digest": "d" * 8,
    }


def _case(
    case_id: str,
    *,
    maturity: str = "reviewed",
    abstention: str = "not_expected",
    causes: list[str] | None = None,
    pairs: list[dict] | None = None,
    results: list[dict] | None = None,
    abstained: bool = False,
) -> dict:
    return {
        "case_id": case_id,
        "scenario_id": f"{case_id}-S",
        "partition": "development",
        "label_maturity": maturity,
        "expected": {
            "abstention": abstention,
            "acceptable_cause_ids": causes if causes is not None else ["cause.a"],
            "acceptable_action_pairs": (
                pairs if pairs is not None else [{"cause_id": "cause.a", "action_id": "action.x"}]
            ),
        },
        "ranked_results": (
            results if results is not None else [
                {"rank": 1, "cause_id": "cause.a", "action_ids": ["action.x"]}
            ]
        ),
        "abstained": abstained,
    }


def _input(cases: list[dict], policy: dict | None = None) -> dict:
    return {
        "schema_version": "route_a_expert_ranking_input_v1",
        "metric_policy": policy if policy is not None else _policy(),
        "candidate": _candidate(),
        "cases": cases,
    }


class ValidationTest(unittest.TestCase):
    def test_rejects_unfrozen_policy(self) -> None:
        policy = _policy()
        policy["ranking_depth"] = 10
        with self.assertRaises(ExpertRankingInputError):
            evaluate_expert_ranking(_input([_case("c1")], policy))

    def test_rejects_six_results(self) -> None:
        results = [
            {"rank": rank, "cause_id": f"cause.{rank}", "action_ids": []}
            for rank in range(1, 7)
        ]
        with self.assertRaises(ExpertRankingInputError):
            evaluate_expert_ranking(_input([_case("c1", results=results)]))

    def test_rejects_duplicate_rank(self) -> None:
        results = [
            {"rank": 1, "cause_id": "cause.a", "action_ids": []},
            {"rank": 1, "cause_id": "cause.b", "action_ids": []},
        ]
        with self.assertRaises(ExpertRankingInputError):
            evaluate_expert_ranking(_input([_case("c1", results=results)]))

    def test_rejects_rank_zero(self) -> None:
        with self.assertRaises(ExpertRankingInputError):
            evaluate_expert_ranking(
                _input(
                    [_case("c1", results=[{"rank": 0, "cause_id": "cause.a", "action_ids": []}])]
                )
            )


class EvaluateTest(unittest.TestCase):
    def test_perfect_ranking_scores_full(self) -> None:
        report = evaluate_expert_ranking(_input([_case("c1"), _case("c2")]))
        self.assertEqual(report["primary_metric"]["value"], 1.0)
        self.assertEqual(report["primary_metric"]["eligible_case_count"], 2)
        self.assertEqual(report["aggregate"]["mean_cause_recall_at_1"], 1.0)
        self.assertEqual(report["aggregate"]["mean_pair_recall_at_3"], 1.0)
        self.assertEqual(report["aggregate"]["mean_mrr_at_5"], 1.0)
        self.assertEqual(report["abstention_safety_gate_failures"], [])
        self.assertEqual(report["composite_score"], "prohibited")

    def test_partial_ranking_arithmetic(self) -> None:
        case = _case(
            "c1",
            causes=["cause.a", "cause.b"],
            pairs=[
                {"cause_id": "cause.a", "action_id": "action.x"},
                {"cause_id": "cause.b", "action_id": "action.y"},
            ],
            results=[
                {"rank": 1, "cause_id": "cause.c", "action_ids": ["action.z"]},
                {"rank": 2, "cause_id": "cause.a", "action_ids": ["action.w", "action.x"]},
                {"rank": 3, "cause_id": "cause.b", "action_ids": []},
            ],
        )
        entry = evaluate_expert_ranking(_input([case]))["cases"][0]
        self.assertEqual(entry["cause_recall_at_1"], 0.0)
        self.assertEqual(entry["cause_recall_at_3"], 1.0)
        self.assertEqual(entry["pair_recall_at_1"], 0.0)
        # (cause.b, action.y) is never proposed: the rank-3 result carries no
        # action_ids, so only (cause.a, action.x) of two acceptable pairs hits.
        self.assertEqual(entry["pair_recall_at_3"], 0.5)
        self.assertEqual(entry["mrr_at_5"], 0.5)
        report = evaluate_expert_ranking(_input([case]))
        self.assertEqual(report["primary_metric"]["value"], 0.5)

    def test_pair_missed_at_three(self) -> None:
        case = _case(
            "c1",
            pairs=[{"cause_id": "cause.a", "action_id": "action.x"}],
            results=[
                {"rank": 1, "cause_id": "cause.a", "action_ids": ["action.w"]},
            ],
        )
        report = evaluate_expert_ranking(_input([case]))
        self.assertEqual(report["primary_metric"]["value"], 0.0)
        self.assertEqual(report["cases"][0]["cause_recall_at_1"], 1.0)

    def test_required_abstention_gate(self) -> None:
        passing = _case("c1", abstention="required", causes=[], pairs=[], results=[], abstained=True)
        failing_with_results = _case(
            "c2",
            abstention="required",
            causes=[],
            pairs=[],
            results=[{"rank": 1, "cause_id": "cause.a", "action_ids": []}],
            abstained=True,
        )
        failing_not_abstained = _case(
            "c3", abstention="required", causes=["cause.a"], abstained=False
        )
        report = evaluate_expert_ranking(
            _input([passing, failing_with_results, failing_not_abstained])
        )
        gates = {c["case_id"]: c["abstention_gate"] for c in report["cases"]}
        self.assertEqual(gates["c1"], "pass")
        self.assertEqual(gates["c2"], "failure")
        self.assertEqual(gates["c3"], "failure")
        self.assertEqual(len(report["abstention_safety_gate_failures"]), 2)

    def test_not_expected_abstention_is_failure(self) -> None:
        case = _case("c1", abstention="allowed", abstained=True)
        report = evaluate_expert_ranking(_input([case]))
        self.assertEqual(report["cases"][0]["abstention_gate"], "pass")
        failing = _case("c2", abstention="not_expected", abstained=True)
        report = evaluate_expert_ranking(_input([failing]))
        self.assertEqual(report["cases"][0]["abstention_gate"], "failure")

    def test_provisional_maturity_excluded_from_domain_aggregates(self) -> None:
        good = _case("c1")
        provisional = _case("c2", maturity="assumed_label_provisional")
        report = evaluate_expert_ranking(_input([good, provisional]))
        self.assertEqual(report["domain_correctness_case_count"], 1)
        self.assertEqual(report["primary_metric"]["eligible_case_count"], 1)
        self.assertEqual(report["primary_metric"]["value"], 1.0)
        self.assertEqual(report["provisional_maturity_case_ids"], ["c2"])
        self.assertIn(
            "label_maturity_not_domain_correctness_eligible",
            report["cases"][1]["excluded_from"],
        )

    def test_case_without_pairs_excluded_from_pair_metric_only(self) -> None:
        case = _case("c1", pairs=[])
        report = evaluate_expert_ranking(_input([case]))
        self.assertIsNone(report["primary_metric"]["value"])
        self.assertEqual(report["primary_metric"]["eligible_case_count"], 0)
        self.assertEqual(report["aggregate"]["mean_cause_recall_at_1"], 1.0)
        self.assertIn("no_acceptable_action_pairs", report["cases"][0]["excluded_from"])


if __name__ == "__main__":
    unittest.main()
