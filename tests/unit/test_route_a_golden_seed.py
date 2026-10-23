from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.evaluation.route_a_golden_annotation import validate_annotation_queue
from services.evaluation.route_a_golden_seed import build_annotation_seed, select_pilot_rows


def _rows() -> list[dict]:
    rows = []
    categories = ["Actual downtime", "Waiting for OP", "", "Actual Downtime"]
    shapes = ["A1A-1-1", "A1A1-1-1", "A1A-1"]
    for index in range(24):
        code = shapes[index % len(shapes)]
        if index >= 3:
            code = f"E{index}A-{index % 7}-{index % 5}"
        rows.append(
            {
                "Error Description": f"Alarm {index}",
                "Code": code,
                "Category": categories[index % len(categories)],
                "Error Description (Chinese)": f"报警 {index}",
                "Repair Actions": f"Action {index % 8}",
                "Local Alarm Code": f"LA-{index:03d}",
            }
        )
    return rows


class GoldenSeedTests(unittest.TestCase):
    def test_selection_is_deterministic_and_bounded(self) -> None:
        first = select_pilot_rows(_rows(), count=15)
        second = select_pilot_rows(_rows(), count=15)
        self.assertEqual(
            [row["_digest"] for row in first],
            [row["_digest"] for row in second],
        )
        self.assertEqual(15, len(first))

    def test_seed_is_development_only_and_has_no_gold_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "masked.json"
            source.write_text(json.dumps(_rows()), encoding="utf-8")
            queue = build_annotation_seed(
                _rows(),
                source_path=source,
                source_id="processed-source",
                manifest_path="data/processed/manifest.json",
                masking_log_id="mask-1",
                count=15,
            )

        validate_annotation_queue(queue)
        self.assertEqual(15, len(queue["cases"]))
        self.assertTrue(
            all(case["partition"] == "development" for case in queue["cases"])
        )
        self.assertEqual([], queue["cause_catalog"])
        self.assertEqual([], queue["cause_action_pair_catalog"])
        self.assertTrue(
            all(
                case["source_context"]["label_authority"]
                == "source_suggested_only"
                for case in queue["cases"]
            )
        )
        self.assertTrue(
            all("expected" not in case for case in queue["cases"])
        )

    def test_seed_context_rejects_graph_derived_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "masked.json"
            source.write_text(json.dumps(_rows()), encoding="utf-8")
            queue = build_annotation_seed(
                _rows(),
                source_path=source,
                source_id="processed-source",
                manifest_path="data/processed/manifest.json",
                masking_log_id="mask-1",
                count=5,
            )
        queue["cases"][0]["source_context"]["graph_node_id"] = "node-1"
        with self.assertRaisesRegex(
            ValueError,
            "prohibited graph/retrieval fields",
        ):
            validate_annotation_queue(queue)


if __name__ == "__main__":
    unittest.main()
