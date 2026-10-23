"""Tests for error code detection in prekg canonicalization."""

from __future__ import annotations

import pytest

from services.canonicalization.prekg import (
    _detect_error_code,
    canonicalize_query,
)


# ---------------------------------------------------------------------------
# _detect_error_code — pattern matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("W01RBRT-07-03报警", "W01RBRT-07-03"),
    ("M03CVMA-02-03 error occurred", "M03CVMA-02-03"),
    ("N03OOOO-04-03异常", "N03OOOO-04-03"),
    ("E99OOOO-02-03触发", "E99OOOO-02-03"),
    ("V020441-01 alarm", "V020441-01"),
    ("C02CVCY-05-03 fault", "C02CVCY-05-03"),
    ("W99RBRT-15-03 triggered", "W99RBRT-15-03"),
    ("EC-123 detected", "EC-123"),
])
def test_detect_error_code_matches(text: str, expected: str):
    assert _detect_error_code(text) == expected


@pytest.mark.parametrize("text", [
    "顶升气缸无法手动触发",
    "Cowling扣不上",
    "机械手取料异常",
    "",
])
def test_detect_error_code_no_match(text: str):
    assert _detect_error_code(text) is None


# ---------------------------------------------------------------------------
# canonicalize_query — error_code slot populated
# ---------------------------------------------------------------------------

def test_canonicalize_query_populates_error_code_slot():
    state = canonicalize_query("W01RBRT-07-03报警如何处理")
    ec_slot = state.entities["diagnostic"]["error_code"]
    assert ec_slot.canonical == "W01RBRT-07-03"
    assert ec_slot.confidence == "high"


def test_canonicalize_query_no_error_code_slot_is_none():
    state = canonicalize_query("电批扭力异常")
    ec_slot = state.entities["diagnostic"]["error_code"]
    assert ec_slot.canonical is None

 
def test_canonicalize_query_v_style_error_code():
    state = canonicalize_query("V020441-01触发了报警")
    ec_slot = state.entities["diagnostic"]["error_code"]
    assert ec_slot.canonical == "V020441-01"


def test_canonicalize_query_error_code_in_entities_structure():
    state = canonicalize_query("M03CVMA-02-03故障")
    entities = state.as_dict()["entities"]
    assert "diagnostic" in entities
    assert "error_code" in entities["diagnostic"]
    assert entities["diagnostic"]["error_code"]["canonical"] == "M03CVMA-02-03"
