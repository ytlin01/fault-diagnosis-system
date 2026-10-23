"""Unit tests for supplementary text2cypher templates (TASK-018A).

Covers new/fixed templates and executor routing logic using mocked Neo4j.
Does NOT require a live Neo4j instance.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.retrieval.route_a_executor import (
    _format_diagnostic_items,
    execute_text2cypher,
)
from services.graph.text2cypher.templates import (
    CYPHER_DIAGNOSTIC,
    INTENT_DIAGNOSTIC_CHAIN,
    VALID_INTENTS,
)


# ---------------------------------------------------------------------------
# Template content checks
# ---------------------------------------------------------------------------

def test_cypher_diagnostic_has_module_key():
    assert "module" in CYPHER_DIAGNOSTIC


def test_cypher_diagnostic_module_uses_node_id_param():
    assert "$node_id" in CYPHER_DIAGNOSTIC["module"]


def test_cypher_diagnostic_module_traverses_has_component():
    assert "HAS_COMPONENT" in CYPHER_DIAGNOSTIC["module"]


def test_cypher_diagnostic_module_traverses_triggers():
    assert "TRIGGERS" in CYPHER_DIAGNOSTIC["module"]


def test_cypher_diagnostic_module_returns_component_field():
    assert "AS component" in CYPHER_DIAGNOSTIC["module"]


def test_steps_ordering_uses_coalesce_in_error_code_template():
    assert "COALESCE(s.order" in CYPHER_DIAGNOSTIC["error_code"]


def test_steps_ordering_uses_coalesce_in_component_template():
    assert "COALESCE(s.order" in CYPHER_DIAGNOSTIC["component"]


def test_steps_ordering_uses_coalesce_in_module_template():
    assert "COALESCE(s.order" in CYPHER_DIAGNOSTIC["module"]


# ---------------------------------------------------------------------------
# executor: module anchor routing
# ---------------------------------------------------------------------------

def _module_state(module_id: str) -> dict:
    return {
        "entities": {
            "asset": {
                "station": {"canonical": None, "raw": None, "confidence": "unknown"},
                "module": {"canonical": module_id, "raw": module_id, "confidence": "high"},
                "component": {"canonical": None, "raw": None, "confidence": "unknown"},
                "subcomponent": {"canonical": None, "raw": None, "confidence": "unknown"},
            },
            "diagnostic": {
                "error_code": {"canonical": None, "raw": None, "confidence": "unknown"},
            },
        }
    }


def test_execute_text2cypher_module_anchor_no_data_returns_not_found():
    """Module anchor with no TRIGGERS data → not_found warning, no exception."""
    with patch("services.retrieval.route_a_executor._run_cypher") as mock_run:
        mock_run.return_value = []
        state = _module_state("M_test_01")
        result = execute_text2cypher(state, intent=INTENT_DIAGNOSTIC_CHAIN)

    assert result["items"] == []
    assert any("not found" in w for w in result["warnings"])
    called_params = mock_run.call_args[0][1]
    assert called_params == {"node_id": "M_test_01"}


@patch("services.retrieval.route_a_executor._run_cypher")
def test_execute_text2cypher_module_anchor_with_data(mock_run):
    """Module anchor with TRIGGERS data → items populated with component field."""
    mock_run.return_value = [
        {
            "component": {"component_id": "C_001", "name": "夹具"},
            "fault": {"fault_id": "fault:abc", "name": "夹具松动"},
            "cause": {"cause_id": "cause:xyz", "description": "螺钉磨损"},
            "action": {"action_id": "action:001", "action_name": "更换螺钉"},
            "steps": [{"step_id": "s1", "order": 1, "instruction": "拆卸螺钉"}],
        }
    ]
    state = _module_state("M_cowling_01")
    result = execute_text2cypher(state, intent=INTENT_DIAGNOSTIC_CHAIN)

    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["component"]["name"] == "夹具"
    assert item["fault"]["name"] == "夹具松动"
    assert result["warnings"] == []
    called_params = mock_run.call_args[0][1]
    assert called_params == {"node_id": "M_cowling_01"}


def test_execute_text2cypher_module_anchor_no_error_code_no_component_falls_through():
    """When no error_code and no component/module anchor: returns warning."""
    state = {
        "entities": {
            "asset": {
                "station": {"canonical": None, "raw": None, "confidence": "unknown"},
                "module": {"canonical": None, "raw": None, "confidence": "unknown"},
                "component": {"canonical": None, "raw": None, "confidence": "unknown"},
                "subcomponent": {"canonical": None, "raw": None, "confidence": "unknown"},
            },
            "diagnostic": {
                "error_code": {"canonical": None, "raw": None, "confidence": "unknown"},
            },
        }
    }
    result = execute_text2cypher(state, intent=INTENT_DIAGNOSTIC_CHAIN)
    assert result["items"] == []
    assert any("anchor" in w.lower() or "no error_code" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# _format_diagnostic_items: component field handling
# ---------------------------------------------------------------------------

def test_format_diagnostic_items_includes_component_field():
    records = [
        {
            "component": {"component_id": "C_001", "name": "夹具"},
            "fault": {"fault_id": "f1", "name": "松动"},
            "cause": {"cause_id": "c1", "description": "磨损"},
            "action": {"action_id": "a1", "action_name": "更换"},
            "steps": [],
        }
    ]
    items = _format_diagnostic_items(records)
    assert len(items) == 1
    assert "component" in items[0]
    assert items[0]["component"]["name"] == "夹具"
    assert "fault" in items[0]


def test_format_diagnostic_items_component_field_absent_when_not_in_record():
    """Records without 'component' key (e.g. from error_code anchor) should not have it."""
    records = [
        {
            "error_code": {"code_id": "E01", "description": "报警"},
            "fault": {"fault_id": "f1", "name": "松动"},
            "cause": None,
            "action": None,
            "steps": [],
        }
    ]
    items = _format_diagnostic_items(records)
    assert "component" not in items[0]
    assert "error_code" in items[0]


def test_format_diagnostic_items_steps_without_order_does_not_raise():
    """Steps missing the 'order' property should not cause a failure."""
    records = [
        {
            "fault": {"fault_id": "f1", "name": "异常"},
            "cause": None,
            "action": None,
            "steps": [
                {"step_id": "s1", "instruction": "步骤一"},  # no 'order' key
                {"step_id": "s2", "instruction": "步骤二"},
            ],
        }
    ]
    items = _format_diagnostic_items(records)
    assert len(items[0]["steps"]) == 2
