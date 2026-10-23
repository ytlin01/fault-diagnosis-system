from __future__ import annotations

import unittest
from unittest.mock import patch

from services.retrieval.route_a_executor import (
    INTENT_CONNECTIONS,
    INTENT_CROSS_MODULE,
    INTENT_HIERARCHY,
    _resolve_anchor,
    execute_text2cypher,
)


def _state(label: str, node_id: str) -> dict:
    """Build a minimal canonical_state dict with a single filled asset slot."""
    asset: dict = {
        "station": {"canonical": None, "confidence": "unknown", "raw": None},
        "module": {"canonical": None, "confidence": "unknown", "raw": None},
        "component": {"canonical": None, "confidence": "unknown", "raw": None},
        "subcomponent": {"canonical": None, "confidence": "unknown", "raw": None},
    }
    asset[label] = {"canonical": node_id, "confidence": "medium", "raw": "test"}
    return {"entities": {"asset": asset}}


class ResolveAnchorTests(unittest.TestCase):
    def test_subcomponent_wins_over_lower_priority(self) -> None:
        state = _state("subcomponent", "SC_111")
        state["entities"]["asset"]["module"] = {"canonical": "M_999", "confidence": "medium", "raw": "x"}
        node_id, label = _resolve_anchor(state)
        self.assertEqual(node_id, "SC_111")
        self.assertEqual(label, "subcomponent")

    def test_empty_state_returns_none(self) -> None:
        node_id, label = _resolve_anchor({})
        self.assertIsNone(node_id)
        self.assertIsNone(label)


class ExecuteText2CypherTests(unittest.TestCase):

    def test_module_hierarchy_query_returns_items(self) -> None:
        fake_records = [
            {
                "node": {"module_id": "M_9494197", "name": "AE1-387-D274-10000", "module_type": "mechanical", "station_id": "C1STN"},
                "children": [{"component_id": "C_9494220", "name": "part-A", "component_type": "mechanical", "module_id": "M_9494197"}],
            }
        ]
        with patch("services.retrieval.route_a_executor._run_cypher", return_value=fake_records):
            result = execute_text2cypher(_state("module", "M_9494197"), intent=INTENT_HIERARCHY)

        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["label"], "Module")
        self.assertEqual(item["properties"]["module_id"], "M_9494197")
        self.assertEqual(len(item["children"]), 1)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["used_sources"][0]["source_type"], "reviewed_asset_graph")

    def test_component_hierarchy_query_returns_subcomponents(self) -> None:
        fake_records = [
            {
                "node": {"component_id": "C_9494220", "name": "part-A", "component_type": "mechanical", "module_id": "M_9494197"},
                "children": [
                    {"subcomponent_id": "SC_9494222", "name": "sub-A1", "component_type": "mechanical", "module_id": "M_9494197"},
                ],
            }
        ]
        with patch("services.retrieval.route_a_executor._run_cypher", return_value=fake_records):
            result = execute_text2cypher(_state("component", "C_9494220"), intent=INTENT_HIERARCHY)

        self.assertEqual(result["items"][0]["label"], "Component")
        self.assertEqual(len(result["items"][0]["children"]), 1)
        self.assertFalse(result["warnings"])

    def test_subcomponent_hierarchy_returns_parent(self) -> None:
        fake_records = [
            {
                "node": {"subcomponent_id": "SC_9494222", "name": "sub-A1", "component_type": "mechanical", "module_id": "M_9494197"},
                "parent_label": "Component",
                "parent_props": {"component_id": "C_9494220", "name": "part-A", "component_type": "mechanical", "module_id": "M_9494197"},
            }
        ]
        with patch("services.retrieval.route_a_executor._run_cypher", return_value=fake_records):
            result = execute_text2cypher(_state("subcomponent", "SC_9494222"), intent=INTENT_HIERARCHY)

        item = result["items"][0]
        self.assertEqual(item["label"], "Subcomponent")
        self.assertEqual(item["parent"]["label"], "Component")
        self.assertEqual(item["parent"]["properties"]["component_id"], "C_9494220")

    def test_component_connections_query(self) -> None:
        fake_records = [
            {
                "source": {"component_id": "C_9494220", "name": "part-A", "component_type": "mechanical", "module_id": "M_9494197"},
                "neighbor_label": "SubComponent",
                "neighbor": {"subcomponent_id": "SC_9494222", "name": "sub-A1", "component_type": "mechanical", "module_id": "M_9494197"},
                "connection_type": "planar_contact",
                "confidence": 0.9,
            }
        ]
        with patch("services.retrieval.route_a_executor._run_cypher", return_value=fake_records):
            result = execute_text2cypher(_state("component", "C_9494220"), intent=INTENT_CONNECTIONS)

        item = result["items"][0]
        self.assertEqual(item["connection_type"], "planar_contact")
        self.assertEqual(item["neighbor"]["label"], "SubComponent")
        self.assertFalse(result["warnings"])

    def test_node_not_found_returns_warning(self) -> None:
        with patch("services.retrieval.route_a_executor._run_cypher", return_value=[]):
            result = execute_text2cypher(_state("module", "M_NONEXISTENT"), intent=INTENT_HIERARCHY)

        self.assertEqual(result["items"], [])
        self.assertTrue(any("not found" in w for w in result["warnings"]))

    def test_no_entity_slot_returns_warning(self) -> None:
        empty_state: dict = {"entities": {"asset": {
            "station": {"canonical": None}, "module": {"canonical": None},
            "component": {"canonical": None}, "subcomponent": {"canonical": None},
        }}}
        result = execute_text2cypher(empty_state)
        self.assertEqual(result["items"], [])
        self.assertTrue(result["warnings"])

    def test_neo4j_connection_error_returns_warning_not_exception(self) -> None:
        def raise_conn_error(cypher, params):
            raise ConnectionRefusedError("Cannot connect to Neo4j")

        with patch("services.retrieval.route_a_executor._run_cypher", side_effect=raise_conn_error):
            result = execute_text2cypher(_state("module", "M_9494197"))

        self.assertEqual(result["items"], [])
        self.assertTrue(any("Neo4j" in w or "connect" in w.lower() for w in result["warnings"]))

    def test_cross_module_intent(self) -> None:
        fake_records = [
            {
                "node": {"module_id": "M_9494197", "name": "AE1-387-D274-10000", "module_type": "mechanical", "station_id": "C1STN"},
                "components": [{"component_id": "C_9494220", "name": "part-A", "component_type": "mechanical", "module_id": "M_9494197"}],
                "subcomponents": [],
            }
        ]
        with patch("services.retrieval.route_a_executor._run_cypher", return_value=fake_records):
            result = execute_text2cypher(_state("module", "M_9494197"), intent=INTENT_CROSS_MODULE)

        self.assertFalse(result["warnings"])
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("components", result["items"][0])
