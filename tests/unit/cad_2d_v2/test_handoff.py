from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.ingestion.cad_2d_pipeline_v2.handoff import (
    JSON_PATHS,
    compare_legacy_triples,
    load_cleaned_handoff,
)


class CleanedHandoffTests(unittest.TestCase):
    def test_snapshot_validation_and_normalization(self) -> None:
        payloads = {
            "a01": [{
                "part_number": "ASM-1",
                "decision": "asm",
                "drawing_type": "asm",
                "review_needed": "review explanation",
            }],
            "a02": {"ASM-1": {"drawing_title": "Assembly", "project_name": ""}},
            "a03": [{
                "part_number": "ASM-1",
                "drawing_type": "asm",
                "drawing_title": "Assembly",
                "project_name": "",
            }],
            "b01": {"ASM-1": [{
                "item_no": "1", "part_number": "CHILD-1", "description": "", "qty": "1"
            }]},
            "b02": {"issues_by_asm": {}, "summary": {}, "asm_count": 1},
            "b02_history": {},
            "c01_edges": [{
                "asm": "ASM-1", "prt": "CHILD-1", "item_no": "1", "qty": "1"
            }],
            "c01_combined": [{"part_number": "ASM-1"}],
            "c02": [{"part_number": "ASM-1"}],
            "round1": {
                "tp": [{"part_number": "ASM-1"}], "tn": [], "fp": [], "fn": []
            },
            "round2": {"items": [{"part_number": "ASM-1"}]},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, relative in JSON_PATHS.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payloads[name]), encoding="utf-8")
            snapshot = load_cleaned_handoff(root)
        self.assertEqual(snapshot.classifications[0]["decision"], "ASM")
        self.assertEqual(snapshot.classifications[0]["review_state"], "human_reviewed")
        self.assertEqual(snapshot.evidence["counts"]["non_boolean_review_flag_count"], 1)
        self.assertFalse(snapshot.evidence["serving_eligible"])

    def test_legacy_comparison_is_not_an_occurrence_join(self) -> None:
        result = compare_legacy_triples(
            {
                "nodes": [
                    {"id": "one", "properties": {"name": "PART-1"}},
                    {"id": "two", "properties": {"name": "PART-1"}},
                ]
            },
            [{"part_number": "PART-1"}],
        )
        self.assertEqual(result["exact_display_name_overlap_count"], 1)
        self.assertEqual(result["ambiguous_display_name_overlap_count"], 1)
        self.assertFalse(result["join_approved"])


if __name__ == "__main__":
    unittest.main()
