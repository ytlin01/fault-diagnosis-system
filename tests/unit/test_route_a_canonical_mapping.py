from __future__ import annotations

import unittest

from services.evaluation.route_a_canonical_mapping import (
    ALIAS_TABLE_VERSION,
    PROPOSAL_ID,
    build_mapping_proposal,
)


def _gold() -> dict:
    def _case(number: int, suggestion: str, description_zh: str) -> dict:
        return {
            "case_id": f"RA-SEED-C1STN-EC-{number:03d}",
            "scenario_id": f"RA-SEED-C1STN-EC-S{number:03d}",
            "query": f"C1STN alarm TEST-0{number}: {description_zh}",
            "source_context": {
                "error_description_zh": description_zh,
                "error_description": f"test alarm {number}",
                "source_suggested_repair_action": suggestion,
            },
        }

    return {
        "queue_id": "test_gold_v1",
        "cause_catalog": [
            {"cause_id": "cause.sensor.signal_abnormal", "display_name": "感应器信号异常"},
            {"cause_id": "cause.vacuum.system_fault", "display_name": "真空系统异常"},
            {"cause_id": "cause.material.missing_or_removed", "display_name": "物料缺失或被移除"},
        ],
        "repair_action_catalog": [
            {"action_id": "action.sensor.inspect_wiring", "display_name": "检查感应器及线路"},
            {"action_id": "action.pneumatic.verify_air_supply", "display_name": "检查供气与压力"},
        ],
        "cases": [
            _case(1, "气缸未上升到位或者感应器异常", "压块气缸上升位信号超时"),
            _case(2, "请检查Flex负压", "取螺丝失败"),
            _case(3, "无", "非生产时间优化设备"),
            _case(4, "推进到位！", "抽屉未推进"),
        ],
    }


class BuildMappingProposalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.proposal = build_mapping_proposal(
            _gold(), gold_path="data/eval/route_a/test_gold.json", gold_sha256="c" * 64
        )

    def test_proposal_identity_and_provenance(self) -> None:
        self.assertEqual(self.proposal["proposal_id"], PROPOSAL_ID)
        self.assertEqual(self.proposal["alias_table_version"], ALIAS_TABLE_VERSION)
        self.assertEqual(self.proposal["derived_from"]["gold_sha256"], "c" * 64)
        self.assertEqual(self.proposal["derived_from"]["gold_queue_id"], "test_gold_v1")
        self.assertIn("domain review", self.proposal["review_gate"])

    def test_matching_case_proposes_catalog_ids_with_evidence(self) -> None:
        first = self.proposal["cases"][0]
        self.assertEqual(first["case_id"], "RA-SEED-C1STN-EC-001")
        cause_ids = [item["catalog_id"] for item in first["proposed_causes"]]
        self.assertIn("cause.sensor.signal_abnormal", cause_ids)
        sensor = next(
            item
            for item in first["proposed_causes"]
            if item["catalog_id"] == "cause.sensor.signal_abnormal"
        )
        patterns = {ev["pattern"] for ev in sensor["evidence"]}
        self.assertIn("感应器异常", patterns)
        self.assertIn("信号超时", patterns)
        bases = {ev["basis"] for ev in sensor["evidence"]}
        self.assertIn("interpretive_alias", bases)
        self.assertEqual(sensor["basis_summary"], "interpretive")

    def test_negative_pressure_maps_vacuum_cause_and_air_supply_action(self) -> None:
        second = self.proposal["cases"][1]
        self.assertEqual(
            [item["catalog_id"] for item in second["proposed_causes"]],
            ["cause.vacuum.system_fault"],
        )
        self.assertEqual(
            [item["catalog_id"] for item in second["proposed_actions"]],
            ["action.pneumatic.verify_air_supply"],
        )
        vacuum = second["proposed_causes"][0]
        self.assertEqual(vacuum["evidence"][0]["matched_in"], ["source_suggested_repair_action"])

    def test_empty_suggestion_marker_maps_nothing_with_reason(self) -> None:
        third = self.proposal["cases"][2]
        self.assertEqual(third["proposed_causes"], [])
        self.assertEqual(third["proposed_actions"], [])
        self.assertIn("no-content marker", third["unmapped_reason"]["causes"])

    def test_unmatched_case_stays_explicitly_unmapped(self) -> None:
        fourth = self.proposal["cases"][3]
        self.assertEqual(fourth["proposed_causes"], [])
        self.assertEqual(fourth["proposed_actions"], [])
        self.assertIn("no alias evidence", fourth["unmapped_reason"]["causes"])
        self.assertIn("suggestion text", fourth["unmapped_reason"]["actions"])
        for case in self.proposal["cases"]:
            self.assertEqual(case["proposal_state"], "proposed_not_reviewed")

    def test_aliases_outside_catalog_are_never_proposed(self) -> None:
        # "气缸未上升到位" bridges to cause.pneumatic.cylinder_stuck, which is
        # absent from the synthetic catalog; it must not appear in output.
        first = self.proposal["cases"][0]
        cause_ids = [item["catalog_id"] for item in first["proposed_causes"]]
        self.assertNotIn("cause.pneumatic.cylinder_stuck", cause_ids)

    def test_empty_gold_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_mapping_proposal(
                {"cases": []}, gold_path="x", gold_sha256="d" * 64
            )


if __name__ == "__main__":
    unittest.main()
