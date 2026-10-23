"""Unit tests for the old-TP-DX canonical mapping service."""

from __future__ import annotations

import unittest

from services.evaluation.old_tpdx_expert_ranking_mapping import (
    MAPPING_ID,
    SCHEMA_VERSION,
    build_mapping,
    graph_snapshot_id,
    mapping_lookup,
    normalize_text,
)


def _chain_row(
    cause: str, action: str, *, cause_id: str = "c1", action_id: str = "a1"
) -> dict:
    return {
        "cause_element_id": cause_id,
        "cause_text": cause,
        "action_element_id": action_id,
        "action_text": action,
        "error_codes": ["S02SSCY-32-03"],
    }


def _gold_v3() -> dict:
    return {
        "queue_id": "v2_task001_c1stn_error_code_reviewed_gold_v3",
        "cause_catalog": [
            {"cause_id": "cause.pneumatic.cylinder_stuck", "display_name": "气缸卡滞"},
            {"cause_id": "cause.sensor.signal_abnormal", "display_name": "感应器信号异常"},
        ],
        "repair_action_catalog": [
            {
                "action_id": "action.pneumatic.test_cylinder",
                "display_name": "测试气缸运动",
            }
        ],
    }


class NormalizeTextTest(unittest.TestCase):
    def test_nfkc_folds_presentation_forms_and_casefolds(self) -> None:
        self.assertEqual(normalize_text("ＡＢＣ ｘｙｚ"), "abc xyz")
        self.assertEqual(normalize_text("氣缸卡滯"), normalize_text("氣缸卡滯"))

    def test_whitespace_is_collapsed(self) -> None:
        self.assertEqual(normalize_text("  a\t b \n c  "), "a b c")

    def test_different_texts_never_match(self) -> None:
        self.assertNotEqual(normalize_text("气缸卡滞"), normalize_text("气缸 卡滞"))
        self.assertNotEqual(normalize_text("气缸卡滞"), normalize_text("气缸本体损坏"))


class GraphSnapshotIdTest(unittest.TestCase):
    def test_order_independent_and_content_sensitive(self) -> None:
        rows = [_chain_row("气缸卡滞", "测试气缸运动"), _chain_row("感应器信号异常", "更换感应器")]
        self.assertEqual(graph_snapshot_id(rows), graph_snapshot_id(list(reversed(rows))))
        changed = [_chain_row("气缸卡滞", "测试气缸运动")]
        self.assertNotEqual(graph_snapshot_id(rows), graph_snapshot_id(changed))


class BuildMappingTest(unittest.TestCase):
    def test_exact_normalized_matches_only(self) -> None:
        rows = [
            _chain_row("气缸卡滞", "测试气缸运动"),
            _chain_row("Ａｂｃ", "xyz"),  # unmatched pair, folds but matches nothing
        ]
        mapping = build_mapping(
            rows,
            _gold_v3(),
            gold_v3_path="data/eval/route_a/gold_v3.json",
            gold_v3_sha256="0" * 64,
            graph_version="neo4j_cad_kg_v3_2",
        )
        self.assertEqual(mapping["schema_version"], SCHEMA_VERSION)
        self.assertEqual(mapping["mapping_id"], MAPPING_ID)
        self.assertFalse(mapping["approved"])
        self.assertEqual(
            [m["catalog_id"] for m in mapping["cause_matches"]],
            ["cause.pneumatic.cylinder_stuck"],
        )
        self.assertEqual(
            [m["catalog_id"] for m in mapping["action_matches"]],
            ["action.pneumatic.test_cylinder"],
        )
        counts = mapping["unmatched_graph_counts"]
        self.assertEqual(counts["distinct_causes"], 2)
        self.assertEqual(counts["unmatched_causes"], 1)
        self.assertEqual(counts["distinct_actions"], 2)
        self.assertEqual(counts["unmatched_actions"], 1)

    def test_fullwidth_variant_matches_same_catalog_entry(self) -> None:
        rows = [_chain_row("气缸卡滞", "测试气缸运动"), _chain_row("气缸卡滞", "测试气缸运动")]
        mapping = build_mapping(
            rows,
            _gold_v3(),
            gold_v3_path="g.json",
            gold_v3_sha256="0" * 64,
            graph_version="neo4j_cad_kg_v3_2",
        )
        match = mapping["cause_matches"][0]
        self.assertEqual(match["graph_texts"], ["气缸卡滞"])

    def test_incomplete_chain_row_is_rejected(self) -> None:
        rows = [_chain_row("", "测试气缸运动")]
        with self.assertRaises(ValueError):
            build_mapping(
                rows,
                _gold_v3(),
                gold_v3_path="g.json",
                gold_v3_sha256="0" * 64,
                graph_version="neo4j_cad_kg_v3_2",
            )

    def test_deterministic_output(self) -> None:
        rows = [_chain_row("气缸卡滞", "测试气缸运动")]
        args = (
            rows,
            _gold_v3(),
        )
        kwargs = dict(
            gold_v3_path="g.json",
            gold_v3_sha256="0" * 64,
            graph_version="neo4j_cad_kg_v3_2",
        )
        import json

        first = json.dumps(build_mapping(*args, **kwargs), sort_keys=True, ensure_ascii=False)
        second = json.dumps(build_mapping(*args, **kwargs), sort_keys=True, ensure_ascii=False)
        self.assertEqual(first, second)


class MappingLookupTest(unittest.TestCase):
    def _mapping(self, approved: bool) -> dict:
        rows = [_chain_row("气缸卡滞", "测试气缸运动")]
        return build_mapping(
            rows,
            _gold_v3(),
            gold_v3_path="g.json",
            gold_v3_sha256="0" * 64,
            graph_version="neo4j_cad_kg_v3_2",
            approved=approved,
        )

    def test_unapproved_mapping_cannot_feed_scored_evaluation(self) -> None:
        with self.assertRaises(ValueError):
            mapping_lookup(self._mapping(approved=False))

    def test_approved_mapping_produces_lookup_tables(self) -> None:
        causes, actions = mapping_lookup(self._mapping(approved=True))
        self.assertEqual(causes["气缸卡滞"], "cause.pneumatic.cylinder_stuck")
        self.assertEqual(actions["测试气缸运动"], "action.pneumatic.test_cylinder")


if __name__ == "__main__":
    unittest.main()
