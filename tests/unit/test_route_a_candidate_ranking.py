"""Unit tests for old-KG candidate ranking and input assembly."""

from __future__ import annotations

import unittest

from services.evaluation.old_tpdx_expert_ranking_mapping import build_mapping
from services.evaluation.route_a_candidate_ranking import (
    build_expert_ranking_input,
    build_ranked_results,
    unmapped_cause_id,
)


def _chain_rows() -> list[dict]:
    return [
        {
            "cause_element_id": "c1",
            "cause_text": "气缸卡滞",
            "action_element_id": "a1",
            "action_text": "测试气缸运动",
            "error_codes": ["S02SSCY-32-03"],
        },
        {
            "cause_element_id": "c2",
            "cause_text": "感应器信号异常",
            "action_element_id": "a2",
            "action_text": "检查感应器及线路",
            "error_codes": ["S02SSCY-32-03"],
        },
        {
            "cause_element_id": "c3",
            "cause_text": "未登记的新原因",
            "action_element_id": "a3",
            "action_text": "未登记的新动作",
            "error_codes": ["F99OOOO-09"],
        },
    ]


def _gold_v3() -> dict:
    return {
        "queue_id": "v2_task001_c1stn_error_code_reviewed_gold_v3",
        "cause_catalog": [
            {"cause_id": "cause.pneumatic.cylinder_stuck", "display_name": "气缸卡滞"},
            {"cause_id": "cause.sensor.signal_abnormal", "display_name": "感应器信号异常"},
        ],
        "repair_action_catalog": [
            {"action_id": "action.pneumatic.test_cylinder", "display_name": "测试气缸运动"},
            {"action_id": "action.sensor.inspect_wiring", "display_name": "检查感应器及线路"},
        ],
        "cases": [
            {
                "case_id": "RA-SEED-C1STN-EC-001",
                "scenario_id": "RA-SEED-C1STN-EC-S001",
                "partition": "development",
                "review": {
                    "label_maturity": "reviewed",
                    "canonical_cause_ids": ["cause.pneumatic.cylinder_stuck"],
                    "canonical_action_ids": ["action.pneumatic.test_cylinder"],
                    "pairing": {
                        "acceptable_action_pairs": [
                            {
                                "cause_id": "cause.pneumatic.cylinder_stuck",
                                "action_id": "action.pneumatic.test_cylinder",
                            }
                        ]
                    },
                    "abstention": {
                        "expected": "not_expected",
                        "reason": "case carries accepted canonical causes",
                    },
                },
            },
            {
                "case_id": "RA-SEED-C1STN-EC-002",
                "scenario_id": "RA-SEED-C1STN-EC-S002",
                "partition": "development",
                "review": {
                    "label_maturity": "reviewed",
                    "canonical_cause_ids": [],
                    "canonical_action_ids": [],
                    "pairing": {"acceptable_action_pairs": []},
                    "abstention": {
                        "expected": "required",
                        "reason": "case maps to no reviewed cause",
                    },
                },
            },
        ],
    }


def _mapping(approved: bool = True) -> dict:
    return build_mapping(
        _chain_rows(),
        _gold_v3(),
        gold_v3_path="gold_v3.json",
        gold_v3_sha256="0" * 64,
        graph_version="neo4j_cad_kg_v3_2",
        approved=approved,
    )


def _retrieval_items() -> list[dict]:
    # Executor shape: one row per (fault, cause, action); repeated cause
    # with a second action must merge under one rank.
    return [
        {
            "error_code": {"code_id": "S02SSCY-32-03"},
            "fault": {"description": "压块气缸上升位信号超时"},
            "cause": {"description": "气缸卡滞"},
            "action": {"action_name": "测试气缸运动"},
            "steps": [],
        },
        {
            "error_code": {"code_id": "S02SSCY-32-03"},
            "fault": {"description": "压块气缸上升位信号超时"},
            "cause": {"description": "气缸卡滞"},
            "action": {"action_name": "检查感应器及线路"},
            "steps": [],
        },
        {
            "error_code": {"code_id": "S02SSCY-32-03"},
            "fault": {"description": "压块气缸上升位信号超时"},
            "cause": {"description": "感应器信号异常"},
            "action": {"action_name": "检查感应器及线路"},
            "steps": [],
        },
        {
            "error_code": {"code_id": "F99OOOO-09"},
            "fault": {"description": "其他故障"},
            "cause": {"description": "未登记的新原因"},
            "action": {"action_name": "未登记的新动作"},
            "steps": [],
        },
    ]


class BuildRankedResultsTest(unittest.TestCase):
    def test_dedup_merges_actions_and_keeps_executor_order(self) -> None:
        ranked = build_ranked_results(_retrieval_items(), _mapping())
        results = ranked["ranked_results"]
        self.assertFalse(ranked["abstained"])
        self.assertEqual(
            [r["cause_id"] for r in results],
            [
                "cause.pneumatic.cylinder_stuck",
                "cause.sensor.signal_abnormal",
                unmapped_cause_id("未登记的新原因"),
            ],
        )
        self.assertEqual([r["rank"] for r in results], [1, 2, 3])
        self.assertEqual(
            results[0]["action_ids"],
            ["action.pneumatic.test_cylinder", "action.sensor.inspect_wiring"],
        )
        self.assertEqual(results[2]["action_ids"], [])

    def test_top_k_cuts_after_five_causes(self) -> None:
        items = []
        for index in range(7):
            items.append(
                {
                    "cause": {"description": f"气缸卡滞{index}"},
                    "action": {"action_name": "测试气缸运动"},
                    "steps": [],
                }
            )
        ranked = build_ranked_results(items, _mapping(), top_k=5)
        self.assertEqual(len(ranked["ranked_results"]), 5)
        self.assertEqual(
            [r["rank"] for r in ranked["ranked_results"]], [1, 2, 3, 4, 5]
        )

    def test_unmapped_cause_keeps_rank_slot_without_canonical_claim(self) -> None:
        ranked = build_ranked_results(_retrieval_items(), _mapping())
        unmapped = ranked["ranked_results"][2]
        self.assertTrue(unmapped["cause_id"].startswith("unmapped:"))
        self.assertNotIn("cause.", unmapped["cause_id"])

    def test_empty_retrieval_abstains(self) -> None:
        ranked = build_ranked_results([], _mapping())
        self.assertTrue(ranked["abstained"])
        self.assertEqual(ranked["ranked_results"], [])

    def test_unapproved_mapping_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_ranked_results(_retrieval_items(), _mapping(approved=False))


class BuildExpertRankingInputTest(unittest.TestCase):
    def test_assembled_input_passes_frozen_contract(self) -> None:
        retrieval_outputs = {
            "RA-SEED-C1STN-EC-001": {"items": _retrieval_items(), "warnings": []},
            "RA-SEED-C1STN-EC-002": {"items": [], "warnings": ["not found"]},
        }
        payload = build_expert_ranking_input(
            _gold_v3(),
            _mapping(),
            retrieval_outputs,
            candidate_id="old_tpdx_baseline_v1",
            graph_version="neo4j_cad_kg_v3_2",
            snapshot_id="sha256:" + "a" * 64,
            data_maturity="assumed_label_provisional",
            config_path="configs/route_a_expert_ranking_old_kg_v1.json",
            config_digest="sha256:" + "b" * 64,
        )
        self.assertEqual(
            payload["schema_version"], "route_a_expert_ranking_input_v1"
        )
        self.assertEqual(
            payload["candidate"],
            {
                "candidate_id": "old_tpdx_baseline_v1",
                "graph_version": "neo4j_cad_kg_v3_2",
                "snapshot_id": "sha256:" + "a" * 64,
                "data_maturity": "assumed_label_provisional",
                "config_digest": "sha256:" + "b" * 64,
            },
        )
        first, second = payload["cases"]
        self.assertEqual(first["label_maturity"], "reviewed")
        self.assertEqual(first["expected"]["abstention"], "not_expected")
        self.assertFalse(first["abstained"])
        self.assertEqual(
            first["expected"]["acceptable_action_pairs"],
            [
                {
                    "cause_id": "cause.pneumatic.cylinder_stuck",
                    "action_id": "action.pneumatic.test_cylinder",
                }
            ],
        )
        self.assertEqual(second["expected"]["abstention"], "required")
        self.assertTrue(second["abstained"])

    def test_missing_retrieval_output_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            build_expert_ranking_input(
                _gold_v3(),
                _mapping(),
                {"RA-SEED-C1STN-EC-001": {"items": []}},
                candidate_id="c",
                graph_version="g",
                snapshot_id="s",
                data_maturity="assumed_label_provisional",
                config_path="p",
                config_digest="d",
            )


if __name__ == "__main__":
    unittest.main()
