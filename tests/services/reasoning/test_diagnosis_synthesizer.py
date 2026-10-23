"""Tests for services.reasoning.diagnosis_synthesizer (TASK-021)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.providers.llm import ProviderResponse
from services.reasoning.diagnosis_synthesizer import synthesize, _empty_conclusion, _parse_conclusion


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


def _valid_conclusion_json(
    *,
    confidence: str = "high",
    route_used: str = "route_a",
) -> str:
    data = {
        "summary": {
            "headline": "B02模块风扇驱动故障：电机过热引发",
            "user_safe_summary": "B02模块上报风扇驱动故障，根本原因为电机过热，建议更换风扇电机。",
        },
        "diagnosis_results": [
            {
                "title": "风扇驱动故障 — 电机过热",
                "description": "电机持续高温导致热保护触发，风扇驱动失效。",
                "confidence": confidence,
                "evidence": [
                    {
                        "evidence_type": "reviewed_mapping",
                        "source_name": "FAN_DRIVE_FAULT",
                        "source_id": "neo4j-fault-001",
                        "summary": "风扇驱动故障节点",
                    }
                ],
                "actions": [
                    {"step": 1, "action": "断电"},
                    {"step": 2, "action": "拆卸风扇"},
                    {"step": 3, "action": "更换电机"},
                    {"step": 4, "action": "重新接线"},
                ],
            }
        ],
        "warnings": [],
        "route_used": route_used,
    }
    return json.dumps(data, ensure_ascii=False)


_SAMPLE_KG_FACTS: dict[str, Any] = {
    "items": [
        {
            "fault": {"id": "neo4j-fault-001", "name": "FAN_DRIVE_FAULT"},
            "cause": {"id": "neo4j-cause-001", "name": "MOTOR_OVERHEAT"},
            "action": {"id": "neo4j-act-001", "name": "REPLACE_MOTOR"},
            "steps": [
                {"description": "断电"},
                {"description": "拆卸风扇"},
            ],
        }
    ],
    "used_sources": [{"source_id": "neo4j_cad_kg_v3_2"}],
    "warnings": [],
}


# ---------------------------------------------------------------------------
# Normal path
# ---------------------------------------------------------------------------

def test_synthesize_returns_valid_conclusion():
    provider = _mock_provider(_valid_conclusion_json())
    result = synthesize("风扇驱动故障原因", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert isinstance(result["summary"], dict)
    assert "headline" in result["summary"]
    assert result["route_used"] == "route_a"
    assert isinstance(result["diagnosis_results"], list)
    assert isinstance(result["warnings"], list)


def test_synthesize_evidence_list_nonempty_on_high_confidence():
    provider = _mock_provider(_valid_conclusion_json(confidence="high"))
    result = synthesize("查询", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert len(result["diagnosis_results"]) > 0
    dr = result["diagnosis_results"][0]
    assert dr["confidence"] == "high"
    assert len(dr["evidence"]) > 0


def test_synthesize_route_used_field_preserved():
    provider = _mock_provider(_valid_conclusion_json(route_used="route_a"))
    result = synthesize("查询", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert result["route_used"] == "route_a"


def test_synthesize_summary_fields_are_strings():
    provider = _mock_provider(_valid_conclusion_json())
    result = synthesize("查询", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert isinstance(result["summary"]["headline"], str)
    assert isinstance(result["summary"]["user_safe_summary"], str)


# ---------------------------------------------------------------------------
# Empty KG facts → empty diagnosis_results, no LLM call
# ---------------------------------------------------------------------------

def test_synthesize_empty_items_returns_no_diagnosis_results():
    provider = _mock_provider(_valid_conclusion_json())
    empty_facts = {"items": [], "used_sources": [], "warnings": []}

    result = synthesize("查询", empty_facts, "route_a", provider=provider)

    assert result["diagnosis_results"] == []
    assert len(result["warnings"]) > 0
    provider.generate.assert_not_called()


def test_synthesize_missing_items_key_returns_no_diagnosis_results():
    provider = _mock_provider(_valid_conclusion_json())
    result = synthesize("查询", {}, "route_a", provider=provider)

    assert result["diagnosis_results"] == []
    provider.generate.assert_not_called()


# ---------------------------------------------------------------------------
# LLM failure → empty diagnosis_results, no exception propagated
# ---------------------------------------------------------------------------

def test_synthesize_llm_exception_returns_no_diagnosis_results():
    provider = MagicMock()
    provider.generate.side_effect = RuntimeError("connection refused")

    result = synthesize("查询", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert result["diagnosis_results"] == []
    assert any("LLM" in w for w in result["warnings"])


def test_synthesize_llm_malformed_json_returns_no_diagnosis_results():
    provider = _mock_provider("这不是JSON，随机文字输出。")
    result = synthesize("查询", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert result["diagnosis_results"] == []
    assert len(result["warnings"]) > 0


def test_synthesize_llm_invalid_confidence_value_normalized():
    bad_json = json.dumps({
        "summary": {"headline": "h", "user_safe_summary": "s"},
        "diagnosis_results": [
            {
                "title": "t",
                "description": "d",
                "confidence": "VERY_HIGH",  # not in allowed set → normalized to "unknown"
                "evidence": [],
                "actions": [],
            }
        ],
        "warnings": [],
        "route_used": "route_a",
    })
    provider = _mock_provider(bad_json)
    result = synthesize("查询", _SAMPLE_KG_FACTS, "route_a", provider=provider)

    assert result["diagnosis_results"][0]["confidence"] in {"high", "medium", "low", "unknown"}


# ---------------------------------------------------------------------------
# _parse_conclusion unit tests
# ---------------------------------------------------------------------------

def test_parse_conclusion_extracts_json_from_prose():
    prose = "根据分析，诊断结论如下：\n" + _valid_conclusion_json() + "\n以上。"
    result = _parse_conclusion(prose, "q", "route_a")

    assert isinstance(result["diagnosis_results"], list)
    assert len(result["diagnosis_results"]) > 0
    assert result["diagnosis_results"][0]["confidence"] in {"high", "medium", "low", "unknown"}


def test_parse_conclusion_raises_on_no_json():
    with pytest.raises(ValueError, match="JSON"):
        _parse_conclusion("纯文字，没有花括号", "q", "route_a")


# ---------------------------------------------------------------------------
# _empty_conclusion helper
# ---------------------------------------------------------------------------

def test_empty_conclusion_schema_completeness():
    result = _empty_conclusion("q", "route_a", reason="test reason")

    required_keys = {"query", "summary", "diagnosis_results", "warnings", "route_used"}
    assert required_keys.issubset(result.keys())
    assert result["diagnosis_results"] == []
    assert result["route_used"] == "route_a"
    assert "test reason" in result["warnings"]
    assert isinstance(result["summary"], dict)
