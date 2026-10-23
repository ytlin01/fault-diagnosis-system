from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from services.graph.tpdx_schema_v4_2_import import (
    GraphImportError,
    apply_import_plan,
    build_import_plan,
)
from services.ingestion.tpdx_schema_v4_2_migration import migrate_v4_1_payload
from tests.unit.test_tpdx_schema_v4_2_migration import fixture_payload, pairings


ROOT = Path(__file__).resolve().parents[3]


class TPDXSchemaV42ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "contracts/schema/tpdx_kg_schema_v4_2.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.candidate = migrate_v4_1_payload(
            fixture_payload(), pairings=pairings()
        ).candidate

    def test_import_plan_is_idempotent_for_existing_candidate(self) -> None:
        plan = build_import_plan(self.candidate, schema=self.schema)
        nodes = {node["id"]: copy.deepcopy(node) for node in self.candidate["nodes"]}
        edges = {
            (edge["type"], edge["from"], edge["to"]): copy.deepcopy(edge)
            for edge in self.candidate["edges"]
        }
        rerun = build_import_plan(
            self.candidate,
            schema=self.schema,
            existing_nodes=nodes.values(),
            existing_edges=edges.values(),
        )
        self.assertEqual(plan.operation_count, len(self.candidate["nodes"]) + len(self.candidate["edges"]))
        self.assertEqual(rerun.operation_count, 0)
        self.assertEqual(rerun.nodes_already_present, len(nodes))
        self.assertEqual(rerun.edges_already_present, len(edges))

    def test_apply_import_plan_is_explicitly_in_memory(self) -> None:
        plan = build_import_plan(self.candidate, schema=self.schema)
        nodes: dict[str, dict] = {}
        edges: dict[tuple[str, str, str, str], dict] = {}
        apply_import_plan(plan, node_store=nodes, edge_store=edges)
        self.assertEqual(len(nodes), len(self.candidate["nodes"]))
        self.assertEqual(len(edges), len(self.candidate["edges"]))

    def test_independent_mapping_record_assertions_conflict(self) -> None:
        existing_edges = [
            edge
            for edge in self.candidate["edges"]
            if edge["type"] == "HAS_CAUSE"
        ]
        conflicting = copy.deepcopy(existing_edges[0])
        conflicting["properties"]["mapping_record_id"] = "MR_" + "a" * 64
        with self.assertRaises(GraphImportError) as raised:
            build_import_plan(
                self.candidate,
                schema=self.schema,
                existing_edges=[conflicting],
            )
        self.assertIn("independent MappingRecord-backed assertions", str(raised.exception))

    def test_has_step_is_rejected_at_import_boundary(self) -> None:
        invalid = copy.deepcopy(self.candidate)
        invalid["edges"].append(
            {
                "type": "HAS_STEP",
                "from": next(node["id"] for node in invalid["nodes"] if node["label"] == "Action"),
                "to": next(node["id"] for node in invalid["nodes"] if node["label"] == "ActionStep"),
                "properties": {},
            }
        )
        with self.assertRaises(GraphImportError):
            build_import_plan(invalid, schema=self.schema)

    def test_non_frozen_schema_is_rejected(self) -> None:
        schema = copy.deepcopy(self.schema)
        schema["x-contract-status"] = "REVIEWED_PROPOSAL"
        with self.assertRaises(GraphImportError):
            build_import_plan(self.candidate, schema=schema)


if __name__ == "__main__":
    unittest.main()
