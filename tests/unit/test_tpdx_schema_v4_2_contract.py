import copy
import json
from pathlib import Path
import unittest

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # Project dependency is optional in the active env.
    Draft202012Validator = None

from services.governance.tpdx_schema_v4_2 import (
    SchemaV42SemanticError,
    assertion_edge_id,
    validate_v4_2_semantics,
)


class TPDXSchemaV42ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema_path = (
            Path(__file__).resolve().parents[2]
            / "contracts/schema/tpdx_kg_schema_v4_2.schema.json"
        )
        with cls.schema_path.open("r", encoding="utf-8") as handle:
            cls.schema = json.load(handle)
        cls.validator = None
        if Draft202012Validator is not None:
            cls.validator = Draft202012Validator(cls.schema)

    @staticmethod
    def _id(prefix: str, character: str) -> str:
        return prefix + "_" + character * 64

    @classmethod
    def valid_payload(cls) -> dict:
        module_id = cls._id("M", "1")
        mr_id = cls._id("MR", "2")
        phenomenon_id = cls._id("PH", "3")
        error_code_id = cls._id("EC", "4")
        cause_id = cls._id("CA", "5")
        action_id = cls._id("AC", "6")
        step_id = cls._id("AS", "7")

        def projection(edge_type: str, from_id: str, to_id: str) -> dict:
            properties = {
                "assertion_edge_id": assertion_edge_id(
                    edge_type, from_id, to_id, mr_id
                ),
                "mapping_record_id": mr_id,
                "source": "manual",
                "extracted_from": "synthetic:row-1",
                "confidence": 1.0,
            }
            if edge_type == "HAS_ACTION":
                properties["cause_action_pair_id"] = "synthetic:pair-1"
            return {
                "type": edge_type,
                "from": from_id,
                "to": to_id,
                "properties": properties,
            }

        return {
            "schema_version": "4.2",
            "payload_kind": "diagnostic",
            "nodes": [
                {
                    "label": "MappingRecord",
                    "id": mr_id,
                    "properties": {
                        "mapping_record_id": mr_id,
                        "source_id": "synthetic-source",
                        "source_snapshot_id": "synthetic-snapshot",
                        "source_record_id": "row-1",
                        "review_status": "reviewed",
                        "serving_safe": True,
                        "promotion_decision_id": "synthetic-decision",
                        "identity_rule_version": "mapping_record_identity_v1",
                    },
                },
                {
                    "label": "Phenomenon",
                    "id": phenomenon_id,
                    "properties": {
                        "phenomenon_id": phenomenon_id,
                        "canonical_text": "Synthetic phenomenon",
                        "identity_rule_version": "diagnostic_identity_v1",
                    },
                },
                {
                    "label": "ErrorCode",
                    "id": error_code_id,
                    "properties": {
                        "error_code_id": error_code_id,
                        "namespace": "synthetic",
                        "code": "E-001",
                        "identity_rule_version": "diagnostic_identity_v1",
                    },
                },
                {
                    "label": "Cause",
                    "id": cause_id,
                    "properties": {
                        "cause_id": cause_id,
                        "canonical_text": "Synthetic possible cause",
                        "identity_rule_version": "diagnostic_identity_v1",
                    },
                },
                {
                    "label": "Action",
                    "id": action_id,
                    "properties": {
                        "action_id": action_id,
                        "action_name": "Synthetic action",
                        "identity_rule_version": "diagnostic_identity_v1",
                    },
                },
                {
                    "label": "ActionStep",
                    "id": step_id,
                    "properties": {
                        "step_id": step_id,
                        "order": 1,
                        "instruction": "Perform the synthetic step",
                    },
                },
            ],
            "edges": [
                {
                    "type": "SCOPED_TO",
                    "from": mr_id,
                    "to": module_id,
                    "properties": {},
                },
                {
                    "type": "OBSERVES",
                    "from": mr_id,
                    "to": phenomenon_id,
                    "properties": {},
                },
                {
                    "type": "USES_ERROR_CODE",
                    "from": mr_id,
                    "to": error_code_id,
                    "properties": {},
                },
                {
                    "type": "ASSERTS_CAUSE",
                    "from": mr_id,
                    "to": cause_id,
                    "properties": {},
                },
                {
                    "type": "RECOMMENDS_ACTION",
                    "from": mr_id,
                    "to": action_id,
                    "properties": {},
                },
                projection("HAS_CODE", phenomenon_id, error_code_id),
                projection("HAS_CAUSE", phenomenon_id, cause_id),
                projection("HAS_ACTION", cause_id, action_id),
                projection("HAS_STEPS", action_id, step_id),
            ],
            "exclusions": [],
        }

    def assert_semantic_failure(self, payload: dict, text: str, **kwargs) -> None:
        with self.assertRaises(SchemaV42SemanticError) as raised:
            validate_v4_2_semantics(payload, **kwargs)
        self.assertIn(text, str(raised.exception))

    def test_assertion_edge_identity_has_a_fixed_vector(self) -> None:
        self.assertEqual(
            assertion_edge_id(
                "HAS_ACTION", "CA_" + "a" * 64, "AC_" + "b" * 64,
                "MR_" + "c" * 64
            ),
            "AE_5ed8daa397dc587e92882ce4e80e0f9f817b1b6193063e99fa58425f91d04e08",
        )

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_complete_mapping_record_backed_chain_passes(self) -> None:
        payload = self.valid_payload()
        self.validator.validate(payload)
        validate_v4_2_semantics(payload)

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_frozen_has_step_relationship_is_rejected(self) -> None:
        payload = self.valid_payload()
        edge = payload["edges"][-1]
        edge["type"] = "HAS_STEP"
        with self.assertRaises(Exception):
            self.validator.validate(payload)

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_projection_requires_mapping_record_id_structurally(self) -> None:
        payload = self.valid_payload()
        del payload["edges"][-1]["properties"]["mapping_record_id"]
        with self.assertRaises(Exception):
            self.validator.validate(payload)

    def test_projection_rejects_wrong_deterministic_id(self) -> None:
        payload = self.valid_payload()
        payload["edges"][-1]["properties"]["assertion_edge_id"] = (
            "AE_" + "f" * 64
        )
        self.assert_semantic_failure(payload, "assertion_edge_id must be")

    def test_projection_rejects_unknown_mapping_record(self) -> None:
        payload = self.valid_payload()
        edge = payload["edges"][-1]
        edge["properties"]["mapping_record_id"] = self._id("MR", "9")
        edge["properties"]["assertion_edge_id"] = assertion_edge_id(
            edge["type"], edge["from"], edge["to"],
            edge["properties"]["mapping_record_id"]
        )
        self.assert_semantic_failure(payload, "references unknown MappingRecord")

    def test_has_action_requires_explicit_backing_memberships(self) -> None:
        payload = self.valid_payload()
        payload["edges"] = [
            edge
            for edge in payload["edges"]
            if edge["type"] != "ASSERTS_CAUSE"
        ]
        self.assert_semantic_failure(payload, "lacks backing membership")

    def test_has_action_requires_explicit_pair_evidence(self) -> None:
        payload = self.valid_payload()
        edge = next(edge for edge in payload["edges"] if edge["type"] == "HAS_ACTION")
        del edge["properties"]["cause_action_pair_id"]
        self.assert_semantic_failure(payload, "cause_action_pair_id")

    def test_projection_rejects_unresolved_endpoint(self) -> None:
        payload = self.valid_payload()
        payload["nodes"] = [
            node for node in payload["nodes"] if node["label"] != "Phenomenon"
        ]
        self.assert_semantic_failure(payload, "unresolved from endpoint")

    def test_mapping_record_requires_exactly_one_observes_edge(self) -> None:
        payload = self.valid_payload()
        observes = next(edge for edge in payload["edges"] if edge["type"] == "OBSERVES")
        payload["edges"].append(copy.deepcopy(observes))
        self.assert_semantic_failure(payload, "exactly 1 OBSERVES")

    def test_mapping_record_id_property_must_equal_node_id(self) -> None:
        payload = self.valid_payload()
        record = next(
            node for node in payload["nodes"] if node["label"] == "MappingRecord"
        )
        record["properties"]["mapping_record_id"] = self._id("MR", "9")
        self.assert_semantic_failure(payload, "mapping_record_id must equal node id")

    def test_mapping_record_governance_requirements_are_enforced(self) -> None:
        cases = (
            ("review_status", "candidate", "is not reviewed"),
            ("serving_safe", False, "is not serving-safe"),
            ("promotion_decision_id", "", "has no promotion decision"),
        )
        for field, value, expected_error in cases:
            with self.subTest(field=field):
                payload = self.valid_payload()
                record = next(
                    node
                    for node in payload["nodes"]
                    if node["label"] == "MappingRecord"
                )
                record["properties"][field] = value
                self.assert_semantic_failure(payload, expected_error)

    def test_projection_rejects_duplicate_against_existing_graph(self) -> None:
        payload = self.valid_payload()
        existing_projection = copy.deepcopy(payload["edges"][-1])
        self.assert_semantic_failure(
            payload,
            "duplicates assertion_edge_id",
            existing_edges=[existing_projection],
        )

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_has_action_requires_pair_evidence_structurally(self) -> None:
        payload = self.valid_payload()
        edge = next(edge for edge in payload["edges"] if edge["type"] == "HAS_ACTION")
        del edge["properties"]["cause_action_pair_id"]
        with self.assertRaises(Exception):
            self.validator.validate(payload)

    def test_duplicate_assertion_edge_id_is_rejected(self) -> None:
        payload = self.valid_payload()
        payload["edges"].append(copy.deepcopy(payload["edges"][-1]))
        self.assert_semantic_failure(payload, "duplicates assertion_edge_id")

    def test_step_orders_must_be_contiguous(self) -> None:
        payload = self.valid_payload()
        step = next(
            node for node in payload["nodes"] if node["label"] == "ActionStep"
        )
        step["properties"]["order"] = 2
        self.assert_semantic_failure(payload, "contiguous from 1")

    def test_complete_mapping_record_backed_chain_passes_semantics(self) -> None:
        validate_v4_2_semantics(self.valid_payload())

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_topology_payload_still_rejects_diagnostic_projection(self) -> None:
        payload = self.valid_payload()
        payload["payload_kind"] = "topology"
        with self.assertRaises(Exception):
            self.validator.validate(payload)


if __name__ == "__main__":
    unittest.main()
