from __future__ import annotations

import unittest

from services.evaluation.route_a_golden_annotation import (
    GoldenAnnotationInputError,
    validate_annotation_queue,
)
from services.evaluation.route_a_reviewed_gold import (
    ATTESTATION_REVIEWER,
    GOLD_QUEUE_ID,
    GOLD_V2_QUEUE_ID,
    GOLD_V3_QUEUE_ID,
    PAIRING_PROPOSAL_ID,
    REGISTRY_ID,
    build_gold_v2,
    build_gold_v3,
    build_reviewed_gold,
    build_scenario_registry,
)


def _seed() -> dict:
    def _case(number: int) -> dict:
        return {
            "case_id": f"RA-SEED-C1STN-EC-{number:03d}",
            "scenario_id": f"RA-SEED-C1STN-EC-S{number:03d}",
            "partition": "development",
            "query": f"C1STN alarm TEST-0{number}: 测试告警 (test alarm {number}).",
            "query_language": "zh-en",
            "coverage": {
                "query_type": "ec",
                "difficulty": "low",
                "equipment_scope": "c1stn_unspecified",
            },
            "seed_status": "provisional_annotation_candidate",
            "source_context": {
                "source_id": "processed__serving__structured__test_seed",
                "source_record_id": f"src-c1stn-ec-test{number:03d}",
                "source_anchor": f"serving_record_sha256:test{number:03d}",
                "label_authority": "source_suggested_only",
                "code": f"TEST-0{number}",
                "local_alarm_code": f"TEST-0{number}",
                "category": "Actual downtime",
                "error_description": f"test alarm {number}",
                "error_description_zh": f"测试告警 {number}",
                "source_suggested_repair_action": "检查感应器及线路",
                "source_row_index": number,
                "duplicate_code_count": 1,
            },
        }

    return {
        "schema_version": "route_a_annotation_queue_v1",
        "queue_id": "test_seed_v1",
        "queue_state": "provisional",
        "source": {"source_id": "processed__serving__structured__test_seed"},
        "selection_policy": {"selected_case_count": 2},
        "cases": [_case(1), _case(2)],
        "cause_catalog": [],
        "cause_action_pair_catalog": [],
    }


def _causes() -> list[dict]:
    return [
        {
            "cause_id": "cause.sensor.signal_abnormal",
            "display_name": "感应器信号异常",
            "definition": "传感器信号缺失、漂移或异常。",
            "family": "Sensor",
        },
        {
            "cause_id": "cause.pneumatic.cylinder_stuck",
            "display_name": "气缸卡滞",
            "definition": "气缸动作受阻。",
            "family": "Pneumatic",
        },
    ]


def _actions() -> list[dict]:
    return [
        {
            "action_id": "action.sensor.inspect_wiring",
            "display_name": "检查感应器及线路",
            "definition": "检查感应器电源、接线。",
            "action_type": "Inspect / verify",
        }
    ]


class BuildReviewedGoldTest(unittest.TestCase):
    def test_builds_valid_reviewed_gold(self) -> None:
        gold = build_reviewed_gold(
            _seed(),
            _causes(),
            _actions(),
            seed_path="data/processed/review_pending/route_a/test_seed.json",
            seed_sha256="a" * 64,
            workbook_path="docs/outputs/test_workbook.xlsx",
            workbook_sha256="b" * 64,
        )
        validate_annotation_queue(gold)
        self.assertEqual(gold["queue_id"], GOLD_QUEUE_ID)
        self.assertEqual(gold["queue_state"], "reviewed_by_attestation")
        self.assertEqual(len(gold["cases"]), 2)
        self.assertEqual(gold["cause_action_pair_catalog"], [])
        self.assertEqual(len(gold["cause_catalog"]), 2)
        self.assertEqual(len(gold["repair_action_catalog"]), 1)
        for case in gold["cases"]:
            review = case["review"]
            self.assertEqual(review["decision"], "accept")
            self.assertEqual(review["label_maturity"], "reviewed")
            self.assertEqual(review["review_basis"], "bulk_data_owner_attestation")
            self.assertEqual(review["reviewer"], ATTESTATION_REVIEWER)
            self.assertEqual(review["accepted_material"], "source_suggested_repair_action")
            self.assertEqual(review["mapping_state"], "not_mapped")
            self.assertEqual(review["canonical_cause_ids"], [])
            self.assertEqual(review["canonical_action_ids"], [])
            self.assertEqual(case["seed_status"], "reviewed_by_attestation")
            # Seed source context is preserved verbatim, never rewritten.
            self.assertEqual(
                case["source_context"]["label_authority"], "source_suggested_only"
            )
        provenance = gold["provenance"]
        self.assertEqual(provenance["seed_sha256"], "a" * 64)
        self.assertEqual(provenance["accepted_workbook_sha256"], "b" * 64)
        self.assertIn("verbal attestation", provenance["evidence_basis"])

    def test_catalog_entry_without_display_name_is_rejected(self) -> None:
        causes = _causes()
        causes[0]["display_name"] = ""
        with self.assertRaises(GoldenAnnotationInputError):
            build_reviewed_gold(
                _seed(),
                causes,
                _actions(),
                seed_path="seed.json",
                seed_sha256="a" * 64,
                workbook_path="wb.xlsx",
                workbook_sha256="b" * 64,
            )


class BuildScenarioRegistryTest(unittest.TestCase):
    def test_registry_has_42_planned_rows_with_plan_partitions(self) -> None:
        registry = build_scenario_registry(_seed())
        self.assertEqual(registry["registry_id"], REGISTRY_ID)
        self.assertEqual(registry["planned_target"], {"total": 42, "per_type": 6})
        planned = registry["planned_scenarios"]
        self.assertEqual(len(planned), 42)
        self.assertEqual(len({row["scenario_id"] for row in planned}), 42)
        for type_code in (
            "EC",
            "PHEN",
            "ASSET",
            "AMB",
            "PARTIAL",
            "MULTI",
            "ABSTAIN",
        ):
            rows = [row for row in planned if row["type"] == type_code]
            self.assertEqual(len(rows), 6)
            partitions = [row["partition"] for row in rows]
            self.assertEqual(
                sorted(partitions),
                ["blind", "development", "development", "development", "development", "validation"],
            )
        abstain = [row for row in planned if row["type"] == "ABSTAIN"]
        self.assertTrue(
            all(row["coverage_tags"]["abstention"] == "required" for row in abstain)
        )
        for row in planned:
            self.assertEqual(row["binding_state"], "unbound")
            self.assertEqual(row["bound_case_ids"], [])

    def test_seed_scenarios_bind_as_reviewed(self) -> None:
        registry = build_scenario_registry(_seed())
        bound = registry["bound_seed_scenarios"]
        self.assertEqual(len(bound), 2)
        for row, case_id in zip(bound, ("RA-SEED-C1STN-EC-001", "RA-SEED-C1STN-EC-002")):
            self.assertEqual(row["binding_state"], "bound")
            self.assertEqual(row["bound_case_ids"], [case_id])
            self.assertEqual(row["review_state"], "reviewed_by_attestation")
            self.assertEqual(row["mapping_state"], "not_mapped")
            self.assertEqual(row["binding_queue_id"], GOLD_QUEUE_ID)


class BuildGoldV2Test(unittest.TestCase):
    def _gold_v1(self) -> dict:
        return build_reviewed_gold(
            _seed(),
            _causes(),
            _actions(),
            seed_path="seed.json",
            seed_sha256="a" * 64,
            workbook_path="wb.xlsx",
            workbook_sha256="b" * 64,
        )

    def _proposal(self) -> dict:
        return {
            "proposal_id": "test_proposal_v1",
            "alias_table_version": "test_alias_v1",
            "cases": [
                {
                    "case_id": "RA-SEED-C1STN-EC-001",
                    "scenario_id": "RA-SEED-C1STN-EC-S001",
                    "proposed_causes": [
                        {"catalog_id": "cause.sensor.signal_abnormal", "evidence": []}
                    ],
                    "proposed_actions": [
                        {"catalog_id": "action.sensor.inspect_wiring", "evidence": []}
                    ],
                    "unmapped_reason": {"causes": "", "actions": ""},
                },
                {
                    "case_id": "RA-SEED-C1STN-EC-002",
                    "scenario_id": "RA-SEED-C1STN-EC-S002",
                    "proposed_causes": [],
                    "proposed_actions": [],
                    "unmapped_reason": {
                        "causes": "no alias evidence found for any reviewed cause",
                        "actions": "suggestion text: '推进到位！'",
                    },
                },
            ],
        }

    def test_gold_v2_carries_accepted_canonical_labels(self) -> None:
        gold_v2 = build_gold_v2(
            self._gold_v1(),
            self._proposal(),
            gold_v1_path="gold_v1.json",
            gold_v1_sha256="e" * 64,
            proposal_path="proposal.json",
            proposal_sha256="f" * 64,
        )
        validate_annotation_queue(gold_v2)
        self.assertEqual(gold_v2["queue_id"], GOLD_V2_QUEUE_ID)
        self.assertEqual(
            gold_v2["queue_state"], "reviewed_by_attestation_mapping_confirmed"
        )
        first, second = gold_v2["cases"]
        self.assertEqual(first["review"]["mapping_state"], "mapped")
        self.assertEqual(
            first["review"]["canonical_cause_ids"], ["cause.sensor.signal_abnormal"]
        )
        self.assertEqual(
            first["review"]["canonical_action_ids"], ["action.sensor.inspect_wiring"]
        )
        self.assertEqual(
            first["review"]["mapping_acceptance"]["alias_table_version"],
            "test_alias_v1",
        )
        self.assertEqual(second["review"]["mapping_state"], "not_mapped")
        self.assertIn("no alias evidence", second["review"]["unmapped_reason"]["causes"])
        self.assertEqual(gold_v2["provenance"]["pairing_state"], "not_asserted")
        self.assertEqual(gold_v2["provenance"]["accepted_proposal_sha256"], "f" * 64)

    def test_proposal_missing_case_is_rejected(self) -> None:
        proposal = self._proposal()
        proposal["cases"] = proposal["cases"][:1]
        with self.assertRaises(ValueError):
            build_gold_v2(
                self._gold_v1(),
                proposal,
                gold_v1_path="g.json",
                gold_v1_sha256="e" * 64,
                proposal_path="p.json",
                proposal_sha256="f" * 64,
            )

    def test_out_of_catalog_id_is_rejected(self) -> None:
        proposal = self._proposal()
        proposal["cases"][0]["proposed_causes"][0]["catalog_id"] = "cause.unknown"
        with self.assertRaises(ValueError):
            build_gold_v2(
                self._gold_v1(),
                proposal,
                gold_v1_path="g.json",
                gold_v1_sha256="e" * 64,
                proposal_path="p.json",
                proposal_sha256="f" * 64,
            )


class BuildGoldV3Test(unittest.TestCase):
    def _gold_v2(self) -> dict:
        return build_gold_v2(
            build_reviewed_gold(
                _seed(),
                _causes(),
                _actions(),
                seed_path="seed.json",
                seed_sha256="a" * 64,
                workbook_path="wb.xlsx",
                workbook_sha256="b" * 64,
            ),
            BuildGoldV2Test()._proposal(),
            gold_v1_path="gold_v1.json",
            gold_v1_sha256="e" * 64,
            proposal_path="proposal.json",
            proposal_sha256="f" * 64,
        )

    def _pairing_proposal(self) -> dict:
        return {
            "proposal_id": PAIRING_PROPOSAL_ID,
            "pairing_rule": "accepted_labels_cross_product_with_shared_evidence_basis",
            "cases": [
                {
                    "case_id": "RA-SEED-C1STN-EC-001",
                    "scenario_id": "RA-SEED-C1STN-EC-S001",
                    "pairing_state": "pairs_proposed",
                    "proposed_pairs": [
                        {
                            "cause_id": "cause.sensor.signal_abnormal",
                            "action_id": "action.sensor.inspect_wiring",
                            "basis": "shared_alias_evidence",
                            "shared_patterns": ["检查感应器"],
                        }
                    ],
                    "no_pair_reason": "",
                    "proposed_abstention": "not_expected",
                    "abstention_reason": "case carries accepted canonical causes",
                },
                {
                    "case_id": "RA-SEED-C1STN-EC-002",
                    "scenario_id": "RA-SEED-C1STN-EC-S002",
                    "pairing_state": "unmapped_nothing_to_pair",
                    "proposed_pairs": [],
                    "no_pair_reason": "case has no accepted canonical causes",
                    "proposed_abstention": "required",
                    "abstention_reason": (
                        "case maps to no reviewed cause; recorded unmapped "
                        "reason: no alias evidence found for any reviewed cause"
                    ),
                },
            ],
        }

    def test_gold_v3_carries_asserted_pairs_and_abstention(self) -> None:
        gold_v3 = build_gold_v3(
            self._gold_v2(),
            self._pairing_proposal(),
            gold_v2_path="gold_v2.json",
            gold_v2_sha256="g" * 64,
            proposal_path="pairing_proposal.json",
            proposal_sha256="h" * 64,
        )
        validate_annotation_queue(gold_v3)
        self.assertEqual(gold_v3["queue_id"], GOLD_V3_QUEUE_ID)
        self.assertEqual(
            gold_v3["queue_state"],
            "reviewed_by_attestation_mapping_and_pairing_confirmed",
        )
        self.assertEqual(gold_v3["provenance"]["pairing_state"], "asserted")
        self.assertEqual(gold_v3["provenance"]["acceptance_date"], "2026-08-19")
        self.assertEqual(
            gold_v3["provenance"]["accepted_pairing_proposal_sha256"], "h" * 64
        )
        first, second = gold_v3["cases"]
        self.assertEqual(first["review"]["pairing"]["pairing_state"], "pairs_asserted")
        self.assertEqual(
            first["review"]["pairing"]["acceptable_action_pairs"],
            [
                {
                    "cause_id": "cause.sensor.signal_abnormal",
                    "action_id": "action.sensor.inspect_wiring",
                }
            ],
        )
        self.assertEqual(first["review"]["abstention"]["expected"], "not_expected")
        self.assertEqual(
            first["review"]["pairing_acceptance"]["pairing_rule"],
            "accepted_labels_cross_product_with_shared_evidence_basis",
        )
        self.assertEqual(
            second["review"]["pairing"]["pairing_state"],
            "unmapped_abstention_required",
        )
        self.assertEqual(second["review"]["pairing"]["acceptable_action_pairs"], [])
        self.assertEqual(second["review"]["abstention"]["expected"], "required")
        self.assertIn("no alias evidence", second["review"]["abstention"]["reason"])

    def test_pairing_proposal_missing_case_is_rejected(self) -> None:
        proposal = self._pairing_proposal()
        proposal["cases"] = proposal["cases"][:1]
        with self.assertRaises(ValueError):
            build_gold_v3(
                self._gold_v2(),
                proposal,
                gold_v2_path="g2.json",
                gold_v2_sha256="g" * 64,
                proposal_path="pp.json",
                proposal_sha256="h" * 64,
            )

    def test_out_of_catalog_pair_is_rejected(self) -> None:
        proposal = self._pairing_proposal()
        proposal["cases"][0]["proposed_pairs"][0]["action_id"] = "action.unknown"
        with self.assertRaises(ValueError):
            build_gold_v3(
                self._gold_v2(),
                proposal,
                gold_v2_path="g2.json",
                gold_v2_sha256="g" * 64,
                proposal_path="pp.json",
                proposal_sha256="h" * 64,
            )

    def test_invalid_abstention_encoding_is_rejected(self) -> None:
        proposal = self._pairing_proposal()
        proposal["cases"][0]["proposed_abstention"] = "maybe"
        with self.assertRaises(ValueError):
            build_gold_v3(
                self._gold_v2(),
                proposal,
                gold_v2_path="g2.json",
                gold_v2_sha256="g" * 64,
                proposal_path="pp.json",
                proposal_sha256="h" * 64,
            )

    def test_pairing_proposal_id_matches_pairing_module(self) -> None:
        from services.evaluation.route_a_pairing_proposal import PROPOSAL_ID

        self.assertEqual(PROPOSAL_ID, PAIRING_PROPOSAL_ID)


if __name__ == "__main__":
    unittest.main()
