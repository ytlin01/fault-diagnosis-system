from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    Draft202012Validator = None

from scripts.build_graph.build_tpdx_schema_v4_2_candidate import (
    CandidateBuildError,
    build_candidate,
)
from services.ingestion.tpdx_schema_v4_2_migration import (
    MigrationError,
    canonical_json_bytes,
    migrate_v4_1_payload,
)


ROOT = Path(__file__).resolve().parents[2]


def _id(prefix: str, character: str) -> str:
    return prefix + "_" + character * 64


def _node(label: str, node_id: str, properties: dict) -> dict:
    return {"label": label, "id": node_id, "properties": properties}


def _membership(edge_type: str, from_id: str, to_id: str) -> dict:
    return {
        "type": edge_type,
        "from": from_id,
        "to": to_id,
        "properties": {"source": "synthetic", "extracted_from": "row-1"},
    }


def fixture_payload(*, second_cause: bool = False, second_action: bool = False) -> dict:
    station_id = _id("ST", "0")
    module_id = _id("M", "1")
    record_id = _id("MR", "2")
    phenomenon_id = _id("PH", "3")
    error_code_id = _id("EC", "4")
    cause_id = _id("CA", "5")
    action_id = _id("AC", "6")
    step_id = _id("AS", "7")
    nodes = [
        _node(
            "Station",
            station_id,
            {
                "station_id": station_id,
                "name": "Synthetic Station",
                "station_type": "unknown",
                "identity_namespace": "synthetic",
                "source_native_id": "station-1",
                "identity_rule_version": "topology_identity_v1",
                "source_snapshot_id": "snapshot-1",
            },
        ),
        _node(
            "Module",
            module_id,
            {
                "module_id": module_id,
                "name": "Synthetic Module",
                "module_type": "mechanical",
                "station_id": station_id,
                "identity_namespace": "synthetic",
                "source_native_id": "module-1",
                "identity_rule_version": "topology_identity_v1",
                "source_snapshot_id": "snapshot-1",
            },
        ),
        _node(
            "MappingRecord",
            record_id,
            {
                "mapping_record_id": record_id,
                "source_id": "synthetic-source",
                "source_snapshot_id": "snapshot-1",
                "source_record_id": "row-1",
                "source_anchor": "row-1",
                "review_status": "reviewed",
                "serving_safe": True,
                "promotion_decision_id": "decision-1",
                "identity_rule_version": "mapping_record_identity_v1",
            },
        ),
        _node(
            "Phenomenon",
            phenomenon_id,
            {
                "phenomenon_id": phenomenon_id,
                "canonical_text": "Synthetic phenomenon",
                "identity_rule_version": "diagnostic_identity_v1",
            },
        ),
        _node(
            "ErrorCode",
            error_code_id,
            {
                "error_code_id": error_code_id,
                "namespace": "synthetic",
                "code": "E-001",
                "identity_rule_version": "diagnostic_identity_v1",
            },
        ),
        _node(
            "Cause",
            cause_id,
            {
                "cause_id": cause_id,
                "canonical_text": "Synthetic cause",
                "identity_rule_version": "diagnostic_identity_v1",
            },
        ),
        _node(
            "Action",
            action_id,
            {
                "action_id": action_id,
                "action_name": "Synthetic action",
                "identity_rule_version": "diagnostic_identity_v1",
            },
        ),
        _node(
            "ActionStep",
            step_id,
            {
                "step_id": step_id,
                "order": 1,
                "instruction": "Perform the synthetic step",
            },
        ),
    ]
    causes = [cause_id]
    actions = [action_id]
    if second_cause:
        second_cause_id = _id("CA", "8")
        causes.append(second_cause_id)
        nodes.append(
            _node(
                "Cause",
                second_cause_id,
                {
                    "cause_id": second_cause_id,
                    "canonical_text": "Second synthetic cause",
                    "identity_rule_version": "diagnostic_identity_v1",
                },
            )
        )
    if second_action:
        second_action_id = _id("AC", "9")
        actions.append(second_action_id)
        nodes.append(
            _node(
                "Action",
                second_action_id,
                {
                    "action_id": second_action_id,
                    "action_name": "Second synthetic action",
                    "identity_rule_version": "diagnostic_identity_v1",
                },
            )
        )
    edges = [
        _membership("SCOPED_TO", record_id, module_id),
        _membership("OBSERVES", record_id, phenomenon_id),
        _membership("USES_ERROR_CODE", record_id, error_code_id),
        *[_membership("ASSERTS_CAUSE", record_id, value) for value in causes],
        *[_membership("RECOMMENDS_ACTION", record_id, value) for value in actions],
        _membership("HAS_STEP", action_id, step_id),
    ]
    return {
        "schema_version": "4.1",
        "payload_kind": "combined",
        "nodes": nodes,
        "edges": edges,
        "exclusions": [],
    }


def pairings(*, review_status: str = "reviewed") -> list[dict]:
    return [
        {
            "mapping_record_id": _id("MR", "2"),
            "cause_id": _id("CA", "5"),
            "action_id": _id("AC", "6"),
            "cause_action_pair_id": "pair-1",
            "review_status": review_status,
            "serving_safe": True,
            "source": "synthetic-review",
            "extracted_from": "review:pair-1",
        }
    ]


class TPDXSchemaV42MigrationTests(unittest.TestCase):
    def test_explicit_pair_and_unique_step_are_migrated(self) -> None:
        result = migrate_v4_1_payload(fixture_payload(), pairings=pairings())
        self.assertTrue(result.complete)
        self.assertEqual(result.candidate["schema_version"], "4.2")
        projection_types = [edge["type"] for edge in result.candidate["edges"]]
        self.assertNotIn("HAS_STEP", projection_types)
        self.assertEqual(projection_types.count("HAS_CODE"), 1)
        self.assertEqual(projection_types.count("HAS_CAUSE"), 1)
        self.assertEqual(projection_types.count("HAS_ACTION"), 1)
        self.assertEqual(projection_types.count("HAS_STEPS"), 1)
        action = next(edge for edge in result.candidate["edges"] if edge["type"] == "HAS_ACTION")
        self.assertEqual(action["properties"]["cause_action_pair_id"], "pair-1")

    def test_schema_accepts_migrated_candidate(self) -> None:
        result = migrate_v4_1_payload(fixture_payload(), pairings=pairings())
        schema = json.loads(
            (ROOT / "contracts/schema/tpdx_kg_schema_v4_2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        if Draft202012Validator is None:
            self.skipTest("jsonschema is not installed")
        Draft202012Validator(schema).validate(result.candidate)

    def test_no_cause_action_cartesian_product(self) -> None:
        result = migrate_v4_1_payload(
            fixture_payload(second_cause=True, second_action=True),
            pairings=pairings(),
        )
        actions = [edge for edge in result.candidate["edges"] if edge["type"] == "HAS_ACTION"]
        self.assertEqual(len(actions), 1)
        self.assertTrue(any("no explicit reviewed cause-action pairing" in item["detail"] for item in result.exclusions))

    def test_unreviewed_pair_is_excluded(self) -> None:
        result = migrate_v4_1_payload(fixture_payload(), pairings=pairings(review_status="candidate"))
        self.assertFalse(result.complete)
        self.assertFalse(any(edge["type"] == "HAS_ACTION" for edge in result.candidate["edges"]))
        self.assertTrue(any("not reviewed" in item["detail"] for item in result.exclusions))

    def test_ambiguous_step_backing_is_excluded(self) -> None:
        payload = fixture_payload()
        extra = fixture_payload()
        extra["nodes"][2]["id"] = _id("MR", "a")
        extra["nodes"][2]["properties"]["mapping_record_id"] = _id("MR", "a")
        for edge in extra["edges"]:
            if edge["from"] == _id("MR", "2"):
                edge["from"] = _id("MR", "a")
        payload["nodes"].append(extra["nodes"][2])
        payload["edges"].extend(extra["edges"][:5])
        result = migrate_v4_1_payload(payload, pairings=pairings())
        self.assertFalse(any(edge["type"] == "HAS_STEPS" for edge in result.candidate["edges"]))
        self.assertTrue(any("multiple MappingRecord backings" in item["detail"] for item in result.exclusions))

    def test_unreviewed_mapping_record_fails_closed(self) -> None:
        payload = fixture_payload()
        record = next(node for node in payload["nodes"] if node["label"] == "MappingRecord")
        record["properties"]["review_status"] = "candidate"
        with self.assertRaises(MigrationError):
            migrate_v4_1_payload(payload, pairings=pairings())

    def test_rerun_is_byte_deterministic(self) -> None:
        first = migrate_v4_1_payload(fixture_payload(), pairings=pairings())
        payload = fixture_payload()
        payload["nodes"] = list(reversed(payload["nodes"]))
        payload["edges"] = list(reversed(payload["edges"]))
        second = migrate_v4_1_payload(payload, pairings=list(reversed(pairings())))
        self.assertEqual(canonical_json_bytes(first.candidate), canonical_json_bytes(second.candidate))
        self.assertEqual(canonical_json_bytes(list(first.exclusions)), canonical_json_bytes(list(second.exclusions)))
        self.assertEqual(canonical_json_bytes(list(first.lineage)), canonical_json_bytes(list(second.lineage)))

    def test_candidate_builder_manifest_and_exclusion_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.json"
            pairings_path = root / "pairings.json"
            config_path = root / "config.json"
            input_path.write_text(json.dumps(fixture_payload()), encoding="utf-8")
            pairings_path.write_text(json.dumps(pairings()), encoding="utf-8")
            config_path.write_text(json.dumps({"profile": "synthetic"}), encoding="utf-8")
            paths = {
                "input_path": input_path,
                "candidate_path": root / "candidate.json",
                "exclusions_path": root / "exclusions.json",
                "lineage_path": root / "lineage.json",
                "manifest_path": root / "manifest.json",
                "schema_path": ROOT / "contracts/schema/tpdx_kg_schema_v4_2.schema.json",
                "rollback_schema_path": ROOT / "contracts/schema/tpdx_kg_schema_v4_1.schema.json",
                "pairings_path": pairings_path,
                "config_path": config_path,
            }
            manifest = build_candidate(**paths)
            self.assertEqual(manifest["run_status"], "complete_candidate")
            self.assertTrue(paths["candidate_path"].exists())
            second = build_candidate(**paths)
            self.assertEqual(manifest, second)

    def test_candidate_builder_fails_closed_without_exclusion_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "input.json"
            pairings_path = root / "pairings.json"
            input_path.write_text(json.dumps(fixture_payload()), encoding="utf-8")
            pairings_path.write_text(
                json.dumps(pairings(review_status="candidate")), encoding="utf-8"
            )
            paths = {
                "input_path": input_path,
                "candidate_path": root / "candidate.json",
                "exclusions_path": root / "exclusions.json",
                "lineage_path": root / "lineage.json",
                "manifest_path": root / "manifest.json",
                "schema_path": ROOT / "contracts/schema/tpdx_kg_schema_v4_2.schema.json",
                "rollback_schema_path": ROOT / "contracts/schema/tpdx_kg_schema_v4_1.schema.json",
                "pairings_path": pairings_path,
            }
            with self.assertRaises(CandidateBuildError):
                build_candidate(**paths)
            self.assertFalse(paths["candidate_path"].exists())
            self.assertTrue(paths["exclusions_path"].exists())
            manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_status"], "blocked_by_exclusions")
            acknowledged_paths = {
                **paths,
                "candidate_path": root / "candidate_ack.json",
                "manifest_path": root / "manifest_ack.json",
            }
            acknowledged = build_candidate(**acknowledged_paths, allow_exclusions=True)
            self.assertEqual(acknowledged["run_status"], "candidate_with_exclusions")
            self.assertTrue(acknowledged_paths["candidate_path"].exists())


if __name__ == "__main__":
    unittest.main()
