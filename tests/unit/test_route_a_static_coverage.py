from __future__ import annotations

import unittest

from services.evaluation.route_a_static_coverage import StaticCoverageInputError, evaluate_static_coverage


def _payload() -> dict:
    return {
        "schema_version": "route_a_static_coverage_input_v1",
        "candidate": {"candidate_id": "old-tpdx", "graph_version": "legacy", "snapshot_id": "snapshot-1", "data_maturity": "assumed_label_provisional", "config_digest": "digest"},
        "nodes": [{"concept_id": "e1", "concept_type": "ErrorCode", "review_state": "unknown"}, {"concept_id": "f1", "concept_type": "Fault", "review_state": "pending"}, {"concept_id": "a1", "concept_type": "Action", "review_state": "reviewed"}],
        "relations": [{"subject_id": "e1", "relation": "INDICATES", "object_id": "f1", "provenance": {"source_id": "s", "anchor": "row-1", "review_state": "pending"}}, {"subject_id": "f1", "relation": "RESOLVED_BY", "object_id": "a1", "provenance": {"source_id": "s", "anchor": "row-2", "review_state": "pending"}}],
        "coverage_targets": {"expected_entities": [{"concept_id": "e1", "concept_type": "ErrorCode"}, {"concept_id": "f1", "concept_type": "Fault"}], "expected_relations": [{"subject_id": "e1", "relation": "INDICATES", "object_id": "f1"}], "expected_paths": [{"path_id": "diagnostic-1", "kind": "diagnostic", "edges": [{"subject_id": "e1", "relation": "INDICATES", "object_id": "f1"}, {"subject_id": "f1", "relation": "RESOLVED_BY", "object_id": "a1"}]}], "bridge": {"source_types": ["ErrorCode"], "relation_types": ["INDICATES"]}, "provenance_required_relations": ["INDICATES", "RESOLVED_BY"]},
    }


class StaticCoverageTests(unittest.TestCase):
    def test_full_coverage_preserves_maturity(self) -> None:
        report = evaluate_static_coverage(_payload())
        self.assertEqual("assumed_label_provisional", report["maturity"])
        self.assertEqual(1.0, report["coverage"]["entity_recall"])
        self.assertEqual(1.0, report["coverage"]["path_recall"])
        self.assertEqual([], report["blockers"])

    def test_dangling_relation_is_a_blocker(self) -> None:
        payload = _payload()
        payload["relations"].append({"subject_id": "e1", "relation": "INDICATES", "object_id": "missing"})
        report = evaluate_static_coverage(payload)
        self.assertEqual(1, report["integrity"]["dangling_relations"])
        self.assertIn("dangling_relations", report["blockers"])

    def test_missing_required_provenance_is_a_blocker(self) -> None:
        payload = _payload()
        del payload["relations"][0]["provenance"]
        report = evaluate_static_coverage(payload)
        self.assertEqual(0.5, report["provenance"]["completeness"])
        self.assertIn("missing_required_provenance", report["blockers"])

    def test_rejects_unknown_schema(self) -> None:
        payload = _payload()
        payload["schema_version"] = "wrong"
        with self.assertRaises(StaticCoverageInputError):
            evaluate_static_coverage(payload)


if __name__ == "__main__":
    unittest.main()
