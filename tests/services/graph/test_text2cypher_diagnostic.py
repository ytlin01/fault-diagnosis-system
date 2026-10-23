"""Tests for INTENT_DIAGNOSTIC_CHAIN template routing and formatting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.retrieval.route_a_executor import (
    _format_diagnostic_items,
    _resolve_error_code,
    execute_text2cypher,
)
from services.graph.text2cypher.templates import (
    CYPHER_DIAGNOSTIC,
    INTENT_DIAGNOSTIC_CHAIN,
    INTENT_HIERARCHY,
    VALID_INTENTS,
)


# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------

def test_intent_diagnostic_chain_in_valid_intents():
    assert INTENT_DIAGNOSTIC_CHAIN in VALID_INTENTS


def test_cypher_diagnostic_has_error_code_and_component_keys():
    assert "error_code" in CYPHER_DIAGNOSTIC
    assert "component" in CYPHER_DIAGNOSTIC


def test_cypher_diagnostic_error_code_uses_correct_param():
    assert "$error_code" in CYPHER_DIAGNOSTIC["error_code"]


def test_cypher_diagnostic_component_uses_correct_param():
    assert "$node_id" in CYPHER_DIAGNOSTIC["component"]


# ---------------------------------------------------------------------------
# _resolve_error_code
# ---------------------------------------------------------------------------

def _make_state(ec: str | None = None, component: str | None = None) -> dict:
    return {
        "entities": {
            "diagnostic": {
                "error_code": {"canonical": ec, "raw": ec, "confidence": "high"}
            },
            "asset": {
                "component": {"canonical": component, "raw": component, "confidence": "medium"},
                "module": {"canonical": None, "raw": None, "confidence": "unknown"},
                "station": {"canonical": None, "raw": None, "confidence": "unknown"},
                "subcomponent": {"canonical": None, "raw": None, "confidence": "unknown"},
            },
        }
    }


def test_resolve_error_code_present():
    state = _make_state(ec="W01RBRT-07-03")
    assert _resolve_error_code(state) == "W01RBRT-07-03"


def test_resolve_error_code_absent():
    state = _make_state(ec=None)
    assert _resolve_error_code(state) is None


def test_resolve_error_code_empty_string():
    state = _make_state(ec="")
    assert _resolve_error_code(state) is None


# ---------------------------------------------------------------------------
# _format_diagnostic_items
# ---------------------------------------------------------------------------

def test_format_diagnostic_items_full_chain():
    records = [
        {
            "error_code": {"code_id": "W01RBRT-07-03", "description": "扭力异常"},
            "fault": {"id": "fault:abc", "name": "扭力异常"},
            "cause": {"cause_id": "cause:xyz", "description": "限位螺丝拧得太紧"},
            "action": {"action_id": "action:001", "action_name": "拧松限位螺丝"},
            "steps": [
                {"step_id": "step:001:1", "order": 1, "instruction": "拧松限位螺丝"},
            ],
        }
    ]
    items = _format_diagnostic_items(records)
    assert len(items) == 1
    item = items[0]
    assert item["error_code"]["code_id"] == "W01RBRT-07-03"
    assert item["fault"]["name"] == "扭力异常"
    assert item["cause"]["description"] == "限位螺丝拧得太紧"
    assert item["action"]["action_name"] == "拧松限位螺丝"
    assert len(item["steps"]) == 1
    assert item["steps"][0]["order"] == 1


def test_format_diagnostic_items_missing_optional_fields():
    records = [{"fault": {"id": "fault:abc", "name": "异常"}, "steps": []}]
    items = _format_diagnostic_items(records)
    assert len(items) == 1
    assert "fault" in items[0]
    assert "error_code" not in items[0]
    assert items[0]["steps"] == []


def test_format_diagnostic_items_multiple_rows():
    records = [
        {"fault": {"id": "f1"}, "cause": {"cause_id": "c1"}, "steps": []},
        {"fault": {"id": "f1"}, "cause": {"cause_id": "c2"}, "steps": []},
    ]
    items = _format_diagnostic_items(records)
    assert len(items) == 2


# ---------------------------------------------------------------------------
# execute_text2cypher — diagnostic chain dispatch
# ---------------------------------------------------------------------------

def test_execute_text2cypher_diagnostic_no_anchor_returns_warning():
    state = _make_state(ec=None, component=None)
    result = execute_text2cypher(state, intent=INTENT_DIAGNOSTIC_CHAIN)
    assert result["items"] == []
    assert any("no error_code" in w for w in result["warnings"])


@patch("services.retrieval.route_a_executor._run_cypher")
def test_execute_text2cypher_diagnostic_ec_anchor(mock_run):
    mock_run.return_value = [
        {
            "error_code": {"code_id": "W01RBRT-07-03"},
            "fault": {"id": "fault:abc", "name": "扭力异常"},
            "cause": {"cause_id": "c1", "description": "原因"},
            "action": {"action_id": "a1", "action_name": "处置"},
            "steps": [{"step_id": "s1", "order": 1, "instruction": "步骤1"}],
        }
    ]
    state = _make_state(ec="W01RBRT-07-03")
    result = execute_text2cypher(state, intent=INTENT_DIAGNOSTIC_CHAIN)
    assert result["items"][0]["error_code"]["code_id"] == "W01RBRT-07-03"
    assert result["warnings"] == []
    called_params = mock_run.call_args[0][1]
    assert called_params == {"error_code": "W01RBRT-07-03"}


@patch("services.retrieval.route_a_executor._run_cypher")
def test_execute_text2cypher_diagnostic_not_found(mock_run):
    mock_run.return_value = []
    state = _make_state(ec="UNKNOWN-00-00")
    result = execute_text2cypher(state, intent=INTENT_DIAGNOSTIC_CHAIN)
    assert result["items"] == []
    assert any("not found" in w for w in result["warnings"])


def test_execute_text2cypher_unknown_intent_returns_warning():
    result = execute_text2cypher({}, intent="bad_intent")
    assert result["items"] == []
    assert any("unknown intent" in w for w in result["warnings"])
