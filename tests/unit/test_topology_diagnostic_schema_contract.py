import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator


class TopologyDiagnosticSchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "../contracts/schema/tpdx_kg_schema_v4_1.schema.json"
        with schema_path.open("r", encoding="utf-8") as handle:
            cls.schema = json.load(handle)

    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    def definition_validator(self, definition_name: str) -> Draft202012Validator:
        return Draft202012Validator(
            {
                "$schema": self.schema["$schema"],
                "$defs": self.schema["$defs"],
                "$ref": f"#/$defs/{definition_name}",
            }
        )

    def test_topology_payload_rejects_diagnostic_nodes(self) -> None:
        payload = {
            "schema_version": "4.1",
            "payload_kind": "topology",
            "nodes": [
                {
                    "label": "Station",
                    "id": "ST_" + "a" * 64,
                    "properties": {
                        "station_id": "ST_" + "a" * 64,
                        "name": "Station A",
                        "station_type": "production",
                        "identity_namespace": "demo",
                        "source_native_id": "station-a",
                        "identity_rule_version": "topology_identity_v1",
                    },
                },
                {
                    "label": "Module",
                    "id": "M_" + "b" * 64,
                    "properties": {
                        "module_id": "M_" + "b" * 64,
                        "name": "Module A",
                        "module_type": "mechanical",
                        "station_id": "ST_" + "a" * 64,
                        "identity_namespace": "demo",
                        "source_native_id": "module-a",
                        "identity_rule_version": "topology_identity_v1",
                    },
                },
                {
                    "label": "ErrorCode",
                    "id": "EC_" + "c" * 64,
                    "properties": {
                        "error_code_id": "EC_" + "c" * 64,
                        "namespace": "demo",
                        "code": "E-001",
                        "identity_rule_version": "v1",
                    },
                },
            ],
            "edges": [
                {
                    "type": "HAS_MODULE",
                    "from": "ST_" + "a" * 64,
                    "to": "M_" + "b" * 64,
                    "properties": {
                        "source": "cad_geometry",
                        "extracted_from": "source",
                        "quantity": 1,
                    },
                }
            ],
            "exclusions": [],
        }

        validator = Draft202012Validator(self.schema)
        with self.assertRaises(Exception):
            validator.validate(payload)

    def test_diagnostic_edge_endpoints_use_canonical_prefixes(self) -> None:
        edge = {
            "type": "USES_ERROR_CODE",
            "from": "bad-id",
            "to": "EC_" + "a" * 64,
            "properties": {
                "source": "manual",
                "extracted_from": "source",
                "confidence": 0.9,
            },
        }

        validator = self.definition_validator("uses_error_code_edge")
        with self.assertRaises(Exception):
            validator.validate(edge)

    def test_scoped_to_accepts_mapping_record_to_module(self) -> None:
        edge = {
            "type": "SCOPED_TO",
            "from": "MR_" + "a" * 64,
            "to": "M_" + "b" * 64,
            "properties": {},
        }

        validator = self.definition_validator("scoped_to_edge")
        validator.validate(edge)

    def test_scoped_to_rejects_component_and_subcomponent_targets(self) -> None:
        validator = self.definition_validator("scoped_to_edge")

        for target in ("C_" + "b" * 64, "SC_" + "c" * 64):
            edge = {
                "type": "SCOPED_TO",
                "from": "MR_" + "a" * 64,
                "to": target,
                "properties": {},
            }
            with self.subTest(target=target), self.assertRaises(Exception):
                validator.validate(edge)


if __name__ == "__main__":
    unittest.main()
