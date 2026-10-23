"""Route A answer quality eval — TASK-029A.

Covers:
  - Schema field completeness (evidence[].source_id / evidence_type / source_name / actions[])
  - Empty KG return: diagnosis_results==[] + warnings triggered
  - Confidence cap by chain completeness (EC+Fault+Cause+Action+Step → high; no Steps → ≤medium)
  - root_cause derivation correctness (equals first non-null possible_cause in sorted order)

Three fixture-based scenarios validate end-to-end assembler behaviour without live KG or LLM.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.providers.llm import ProviderResponse
from services.reasoning.diagnosis_synthesizer import (
    _apply_confidence_cap,
    _chain_max_confidence,
    synthesize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_provider(response_text: str) -> MagicMock:
    provider = MagicMock()
    provider.generate.return_value = ProviderResponse(
        text=response_text,
        provider_type="mock",
        model="mock-model",
    )
    return provider


def _make_conclusion_json(
    *,
    confidence: str,
    possible_cause: str | None = "电机过热",
    source_id: str = "fault:a1b2c3",
    evidence_type: str = "reviewed_mapping",
    source_name: str = "FAN_DRIVE_FAULT",
    include_actions: bool = True,
) -> str:
    result: dict[str, Any] = {
        "title": "风扇驱动故障",
        "possible_cause": possible_cause,
        "description": "电机持续高温触发热保护",
        "confidence": confidence,
        "evidence": [
            {
                "evidence_type": evidence_type,
                "source_name": source_name,
                "source_id": source_id,
                "summary": "风扇驱动故障节点",
            }
        ],
        "actions": [{"step": 1, "action": "断电"}, {"step": 2, "action": "更换电机"}]
        if include_actions
        else [],
    }
    return json.dumps(
        {
            "summary": {"headline": "风扇驱动故障", "user_safe_summary": "建议更换电机"},
            "diagnosis_results": [result],
            "warnings": [],
            "route_used": "route_a",
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# FIXTURE-001: Full chain — EC + Fault + Cause + Action + Steps
# LLM returns high → output must be high
# ---------------------------------------------------------------------------

_FIXTURE_001_FULL_CHAIN: dict[str, Any] = {
    "items": [
        {
            "error_code": {"code_id": "M03CVMA-02-03", "description": "FAN_DRIVE_FAULT"},
            "fault": {"id": "fault:a1b2c3", "name": "FAN_DRIVE_FAULT"},
            "cause": {"cause_id": "cause:b2c3d4", "description": "电机过热"},
            "action": {"action_id": "action:001", "action_name": "断电冷却后检查风扇叶片"},
            "steps": [
                {"step_id": "step:001:1", "order": 1, "instruction": "断开主电源"},
                {"step_id": "step:001:2", "order": 2, "instruction": "检查叶片"},
            ],
        }
    ],
    "used_sources": [{"source_id": "neo4j_cad_kg_v3_2"}],
    "warnings": [],
}


def test_fixture001_full_chain_high_confidence_preserved():
    provider = _mock_provider(_make_conclusion_json(confidence="high"))
    result = synthesize("M03CVMA-02-03 风扇驱动故障", _FIXTURE_001_FULL_CHAIN, "route_a", provider=provider)

    assert result["diagnosis_results"], "full chain must yield at least one result"
    assert result["diagnosis_results"][0]["confidence"] == "high"


def test_fixture001_full_chain_evidence_fields_complete():
    provider = _mock_provider(_make_conclusion_json(confidence="high"))
    result = synthesize("M03CVMA-02-03 风扇驱动故障", _FIXTURE_001_FULL_CHAIN, "route_a", provider=provider)

    for dr in result["diagnosis_results"]:
        assert dr["evidence"], "evidence list must not be empty"
        for ev in dr["evidence"]:
            assert ev.get("source_id"), f"evidence missing source_id: {ev}"
            assert ev.get("evidence_type"), f"evidence missing evidence_type: {ev}"
            assert ev.get("source_name"), f"evidence missing source_name: {ev}"
            assert ev.get("summary") is not None, f"evidence missing summary: {ev}"


def test_fixture001_full_chain_actions_present():
    provider = _mock_provider(_make_conclusion_json(confidence="high"))
    result = synthesize("M03CVMA-02-03 风扇驱动故障", _FIXTURE_001_FULL_CHAIN, "route_a", provider=provider)

    for dr in result["diagnosis_results"]:
        assert dr["actions"], "actions[] must not be empty for a full-chain result"


def test_fixture001_root_cause_equals_first_possible_cause():
    provider = _mock_provider(_make_conclusion_json(confidence="high", possible_cause="电机过热"))
    result = synthesize("M03CVMA-02-03 风扇驱动故障", _FIXTURE_001_FULL_CHAIN, "route_a", provider=provider)

    assert result["root_cause"] == "电机过热"


# ---------------------------------------------------------------------------
# FIXTURE-002: Partial chain — Action present but Steps missing
# LLM returns high → must be capped to medium
# ---------------------------------------------------------------------------

_FIXTURE_002_NO_STEPS: dict[str, Any] = {
    "items": [
        {
            "error_code": {"code_id": "E002", "description": "MOTOR_OVERLOAD"},
            "fault": {"id": "fault:d4e5f6", "name": "MOTOR_OVERLOAD"},
            "cause": {"cause_id": "cause:e5f6a7", "description": "电机过载"},
            "action": {"action_id": "action:002", "action_name": "复位过载保护"},
            "steps": [],  # no steps — chain is partial
        }
    ],
    "used_sources": [{"source_id": "neo4j_cad_kg_v3_2"}],
    "warnings": [],
}


def test_fixture002_no_steps_caps_high_to_medium():
    provider = _mock_provider(_make_conclusion_json(confidence="high", possible_cause="电机过载",
                                                    source_id="fault:d4e5f6", source_name="MOTOR_OVERLOAD"))
    result = synthesize("电机过载报警", _FIXTURE_002_NO_STEPS, "route_a", provider=provider)

    assert result["diagnosis_results"], "partial chain must still yield a result"
    assert result["diagnosis_results"][0]["confidence"] in {"medium", "low", "unknown"}, (
        "confidence must not be high when steps are missing"
    )


def test_fixture002_no_steps_medium_confidence_not_further_capped():
    provider = _mock_provider(_make_conclusion_json(confidence="medium", possible_cause="电机过载",
                                                    source_id="fault:d4e5f6", source_name="MOTOR_OVERLOAD"))
    result = synthesize("电机过载报警", _FIXTURE_002_NO_STEPS, "route_a", provider=provider)

    assert result["diagnosis_results"][0]["confidence"] == "medium"


def test_fixture002_chain_max_confidence_is_medium():
    assert _chain_max_confidence(_FIXTURE_002_NO_STEPS) == "medium"


# ---------------------------------------------------------------------------
# FIXTURE-003: Empty KG — diagnosis_results==[], warnings triggered, no LLM call
# ---------------------------------------------------------------------------

_FIXTURE_003_EMPTY: dict[str, Any] = {
    "items": [],
    "used_sources": [],
    "warnings": [],
}

_FIXTURE_003_MISSING_KEY: dict[str, Any] = {}


def test_fixture003_empty_items_returns_no_results():
    provider = _mock_provider(_make_conclusion_json(confidence="high"))
    result = synthesize("任意查询", _FIXTURE_003_EMPTY, "route_a", provider=provider)

    assert result["diagnosis_results"] == []
    assert result["warnings"], "empty KG must produce at least one warning"
    provider.generate.assert_not_called()


def test_fixture003_missing_items_key_returns_no_results():
    provider = _mock_provider(_make_conclusion_json(confidence="high"))
    result = synthesize("任意查询", _FIXTURE_003_MISSING_KEY, "route_a", provider=provider)

    assert result["diagnosis_results"] == []
    provider.generate.assert_not_called()


def test_fixture003_empty_chain_max_confidence_is_unknown():
    assert _chain_max_confidence(_FIXTURE_003_EMPTY) == "unknown"
    assert _chain_max_confidence(_FIXTURE_003_MISSING_KEY) == "unknown"


# ---------------------------------------------------------------------------
# root_cause derivation — multi-result, sorted by confidence
# ---------------------------------------------------------------------------

def test_root_cause_derived_from_highest_confidence_result():
    """root_cause must equal the possible_cause of the highest-confidence result."""
    llm_output = json.dumps(
        {
            "summary": {"headline": "多原因分析", "user_safe_summary": "两条可能原因"},
            "diagnosis_results": [
                {
                    "title": "原因A（低置信）",
                    "possible_cause": "线路老化",
                    "description": "低置信原因",
                    "confidence": "low",
                    "evidence": [
                        {
                            "evidence_type": "reviewed_mapping",
                            "source_name": "FAULT_X",
                            "source_id": "fault:x",
                            "summary": "x",
                        }
                    ],
                    "actions": [],
                },
                {
                    "title": "原因B（高置信）",
                    "possible_cause": "电机过热",
                    "description": "高置信原因",
                    "confidence": "high",
                    "evidence": [
                        {
                            "evidence_type": "reviewed_mapping",
                            "source_name": "FAN_DRIVE_FAULT",
                            "source_id": "fault:a1b2c3",
                            "summary": "风扇驱动故障",
                        }
                    ],
                    "actions": [{"step": 1, "action": "断电"}, {"step": 2, "action": "更换电机"}],
                },
            ],
            "warnings": [],
            "route_used": "route_a",
        },
        ensure_ascii=False,
    )
    provider = _mock_provider(llm_output)
    result = synthesize("多原因查询", _FIXTURE_001_FULL_CHAIN, "route_a", provider=provider)

    assert result["root_cause"] == "电机过热", (
        f"expected root_cause='电机过热' (from high-confidence result), got '{result['root_cause']}'"
    )


def test_root_cause_defaults_when_no_possible_cause():
    provider = _mock_provider(_make_conclusion_json(confidence="high", possible_cause=None))
    result = synthesize("查询", _FIXTURE_001_FULL_CHAIN, "route_a", provider=provider)

    assert result["root_cause"] == "证据不足，暂无法确认"


# ---------------------------------------------------------------------------
# _apply_confidence_cap unit tests
# ---------------------------------------------------------------------------

def test_apply_confidence_cap_downgrades_high_to_medium():
    results = [{"confidence": "high"}, {"confidence": "low"}]
    _apply_confidence_cap(results, "medium")
    assert results[0]["confidence"] == "medium"
    assert results[1]["confidence"] == "low"  # low stays low


def test_apply_confidence_cap_no_change_when_already_within_cap():
    results = [{"confidence": "medium"}]
    _apply_confidence_cap(results, "medium")
    assert results[0]["confidence"] == "medium"


def test_apply_confidence_cap_unknown_not_upgraded():
    results = [{"confidence": "unknown"}]
    _apply_confidence_cap(results, "high")
    assert results[0]["confidence"] == "unknown"  # cap only downgrades, never upgrades
