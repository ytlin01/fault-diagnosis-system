"""Unit tests for the pairing and abstention proposal builder."""

from __future__ import annotations

import json
import unittest

from services.evaluation.route_a_pairing_proposal import (
    MAPPING_PROPOSAL_ID,
    PROPOSAL_ID,
    build_pairing_abstention_proposal,
)
from services.evaluation.route_a_reviewed_gold import GOLD_V2_QUEUE_ID


def _gold_case(case_id: str, causes: list[str], actions: list[str]) -> dict:
    unmapped_cause_reason = "" if causes else "no alias evidence found for any reviewed cause"
    unmapped_action_reason = "" if actions else "no reviewed action for this case"
    return {
        "case_id": case_id,
        "scenario_id": f"{case_id}-S",
        "partition": "development",
        "query": f"query for {case_id}",
        "query_language": "zh-en",
        "coverage": {
            "query_type": "ec",
            "difficulty": "medium",
            "equipment_scope": "c1stn_unspecified",
        },
        "review": {
            "decision": "accept",
            "label_maturity": "reviewed",
            "canonical_cause_ids": causes,
            "canonical_action_ids": actions,
            "mapping_state": "mapped" if causes else "not_mapped",
            "unmapped_reason": {
                "causes": unmapped_cause_reason,
                "actions": unmapped_action_reason,
            },
        },
    }


def _gold_v2(cases: list[dict]) -> dict:
    return {
        "schema_version": "route_a_annotation_queue_v1",
        "queue_id": GOLD_V2_QUEUE_ID,
        "queue_state": "reviewed_by_attestation_mapping_confirmed",
        "cases": cases,
    }


def _proposed(catalog_id: str, patterns: list[str]) -> dict:
    return {
        "catalog_id": catalog_id,
        "evidence": [
            {"pattern": pattern, "matched_in": ["source_suggested_repair_action"], "basis": "catalog_token"}
            for pattern in patterns
        ],
    }


def _proposal_case(case_id: str, causes: list[dict], actions: list[dict]) -> dict:
    return {
        "case_id": case_id,
        "proposed_causes": causes,
        "proposed_actions": actions,
    }


def _mapping_proposal(cases: list[dict]) -> dict:
    return {
        "schema_version": "route_a_canonical_mapping_proposal_v1",
        "proposal_id": MAPPING_PROPOSAL_ID,
        "cases": cases,
    }


def _build(gold: dict, proposal: dict) -> dict:
    return build_pairing_abstention_proposal(
        gold,
        proposal,
        gold_v2_path="data/eval/route_a/gold_v2.json",
        gold_v2_sha256="0" * 64,
        mapping_proposal_path="data/eval/route_a/mapping_proposal.json",
        mapping_proposal_sha256="1" * 64,
    )


class PairingAbstentionProposalTest(unittest.TestCase):
    def test_shared_and_cross_pair_basis(self):
        gold = _gold_v2(
            [
                _gold_case(
                    "C-1",
                    ["cause.a.one", "cause.b.two"],
                    ["action.a.check", "action.b.verify"],
                )
            ]
        )
        proposal = _mapping_proposal(
            [
                _proposal_case(
                    "C-1",
                    [
                        _proposed("cause.a.one", ["负压"]),
                        _proposed("cause.b.two", ["视觉定位"]),
                    ],
                    [
                        _proposed("action.a.check", ["负压"]),
                        _proposed("action.b.verify", ["视觉定位"]),
                    ],
                )
            ]
        )
        result = _build(gold, proposal)
        self.assertEqual(result["proposal_id"], PROPOSAL_ID)
        case = result["cases"][0]
        self.assertEqual(case["pairing_state"], "pairs_proposed")
        self.assertEqual(len(case["proposed_pairs"]), 4)
        by_pair = {
            (pair["cause_id"], pair["action_id"]): pair
            for pair in case["proposed_pairs"]
        }
        shared = by_pair[("cause.a.one", "action.a.check")]
        self.assertEqual(shared["basis"], "shared_alias_evidence")
        self.assertEqual(shared["shared_patterns"], ["负压"])
        cross = by_pair[("cause.a.one", "action.b.verify")]
        self.assertEqual(cross["basis"], "case_level_cross_product")
        self.assertEqual(cross["shared_patterns"], [])
        self.assertEqual(case["proposed_abstention"], "not_expected")
        self.assertEqual(result["summary"]["binding_review_case_ids"], ["C-1"])
        self.assertEqual(result["summary"]["shared_evidence_pair_count"], 2)
        self.assertEqual(result["summary"]["cross_product_only_pair_count"], 2)

    def test_mapped_case_without_actions_has_no_pairs(self):
        gold = _gold_v2(
            [_gold_case("C-2", ["cause.a.one"], [])]
        )
        proposal = _mapping_proposal(
            [_proposal_case("C-2", [_proposed("cause.a.one", ["负压"])], [])]
        )
        case = _build(gold, proposal)["cases"][0]
        self.assertEqual(case["pairing_state"], "no_reviewed_action_to_pair")
        self.assertEqual(case["proposed_pairs"], [])
        self.assertEqual(case["no_pair_reason"], "no reviewed action for this case")
        self.assertEqual(case["proposed_abstention"], "not_expected")

    def test_unmapped_case_proposes_required_abstention(self):
        gold = _gold_v2([_gold_case("C-3", [], [])])
        proposal = _mapping_proposal([_proposal_case("C-3", [], [])])
        result = _build(gold, proposal)
        case = result["cases"][0]
        self.assertEqual(case["pairing_state"], "unmapped_nothing_to_pair")
        self.assertEqual(case["proposed_pairs"], [])
        self.assertEqual(case["proposed_abstention"], "required")
        self.assertIn(
            "no alias evidence found for any reviewed cause",
            case["abstention_reason"],
        )
        self.assertEqual(result["summary"]["abstention_required_case_ids"], ["C-3"])

    def test_single_cause_action_pair_needs_no_binding_review(self):
        gold = _gold_v2(
            [_gold_case("C-4", ["cause.a.one"], ["action.a.check"])]
        )
        proposal = _mapping_proposal(
            [
                _proposal_case(
                    "C-4",
                    [_proposed("cause.a.one", ["负压"])],
                    [_proposed("action.a.check", ["负压"])],
                )
            ]
        )
        result = _build(gold, proposal)
        self.assertEqual(result["summary"]["binding_review_case_ids"], [])
        self.assertEqual(result["summary"]["proposed_pair_count"], 1)

    def test_rejects_wrong_gold_queue(self):
        gold = _gold_v2([_gold_case("C-1", ["cause.a.one"], [])])
        gold["queue_id"] = "some_other_queue"
        with self.assertRaises(ValueError):
            _build(gold, _mapping_proposal([]))

    def test_rejects_wrong_mapping_proposal_id(self):
        gold = _gold_v2([_gold_case("C-1", ["cause.a.one"], [])])
        proposal = _mapping_proposal([])
        proposal["proposal_id"] = "other_proposal"
        with self.assertRaises(ValueError):
            _build(gold, proposal)

    def test_rejects_missing_proposal_case(self):
        gold = _gold_v2([_gold_case("C-1", ["cause.a.one"], [])])
        with self.assertRaises(ValueError):
            _build(gold, _mapping_proposal([]))

    def test_rejects_diverging_canonical_labels(self):
        gold = _gold_v2(
            [_gold_case("C-1", ["cause.a.one", "cause.b.two"], [])]
        )
        proposal = _mapping_proposal(
            [_proposal_case("C-1", [_proposed("cause.a.one", ["负压"])], [])]
        )
        with self.assertRaises(ValueError):
            _build(gold, proposal)

    def test_deterministic_output(self):
        gold = _gold_v2(
            [
                _gold_case("C-1", ["cause.a.one"], ["action.a.check"]),
                _gold_case("C-2", [], []),
            ]
        )
        proposal = _mapping_proposal(
            [
                _proposal_case(
                    "C-1",
                    [_proposed("cause.a.one", ["负压"])],
                    [_proposed("action.a.check", ["负压"])],
                ),
                _proposal_case("C-2", [], []),
            ]
        )
        first = json.dumps(_build(gold, proposal), ensure_ascii=False, sort_keys=True)
        second = json.dumps(_build(gold, proposal), ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
