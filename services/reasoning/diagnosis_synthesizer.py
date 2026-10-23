"""Diagnosis synthesizer for Route A (TASK-021)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from services.providers.llm import BaseProvider, ProviderRequest, build_provider

_PROMPT_PATH = Path(__file__).parent / "prompts" / "diagnosis_synthesis.txt"
_CONFIDENCE_VALUES = frozenset({"high", "medium", "low", "unknown"})
_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
_DEFAULT_ROOT_CAUSE = "证据不足，暂无法确认"

_SCHEMA_HINT = """{
  "summary": {
    "headline": "<中文诊断标题>",
    "user_safe_summary": "<1-3句中文摘要>"
  },
  "diagnosis_results": [
    {
      "title": "<结果标题>",
      "possible_cause": "<该条对应 cause.description 原文；无对应 cause 时为 null>",
      "description": "<该条诊断描述>",
      "confidence": "high | medium | low | unknown",
      "evidence": [
        {
          "evidence_type": "reviewed_mapping",
          "source_name": "<可展示名称>",
          "source_id": "<真实 KG 节点 ID>",
          "summary": "<证据中文摘要>"
        }
      ],
      "actions": [
        {"step": 1, "action": "<KG 步骤动作>"}
      ]
    }
  ],
  "root_cause": "<单一用户展示根因；必须等于排序后第一条非空 possible_cause；若全为空则为“证据不足，暂无法确认”>",
  "warnings": ["<缺口说明>"],
  "route_used": "route_a"
}"""


def synthesize(
    query: str,
    kg_facts: Mapping[str, Any],
    route: str,
    *,
    provider: BaseProvider | None = None,
) -> dict[str, Any]:
    if provider is None:
        provider = build_provider()

    items = list(kg_facts.get("items") or [])
    if not items:
        return _empty_conclusion(query, route, reason="KG facts 为空或无可用诊断证据")

    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return _empty_conclusion(query, route, reason=f"Prompt 读取失败: {exc}")

    kg_facts_json = json.dumps({"items": items}, ensure_ascii=False, indent=2)
    prompt = template.format(
        query=query,
        kg_facts_json=kg_facts_json,
        schema_hint=_SCHEMA_HINT,
    )

    try:
        response = provider.generate(ProviderRequest(prompt=prompt))
        raw_text = response.text
    except Exception as exc:
        return _empty_conclusion(query, route, reason=f"LLM 调用失败: {exc}")

    try:
        return _parse_conclusion(raw_text, query, route, kg_facts)
    except Exception as exc:
        return _empty_conclusion(query, route, reason=f"LLM 输出解析失败: {exc}")


def _parse_conclusion(
    text: str,
    query: str,
    route: str,
    kg_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        raise ValueError("LLM 输出中未找到 JSON 对象")

    data = json.loads(json_match.group())

    raw_summary = data.get("summary") or {}
    summary = {
        "headline": str(raw_summary.get("headline") or ""),
        "user_safe_summary": str(raw_summary.get("user_safe_summary") or ""),
    }

    raw_results = list(data.get("diagnosis_results") or [])
    diagnosis_results = []
    for raw in raw_results:
        if not isinstance(raw, Mapping):
            continue
        confidence = str(raw.get("confidence") or "unknown")
        if confidence not in _CONFIDENCE_VALUES:
            confidence = "unknown"
        diagnosis_results.append(
            {
                "title": str(raw.get("title") or ""),
                "possible_cause": _nullable_text(raw.get("possible_cause")),
                "description": str(raw.get("description") or ""),
                "confidence": confidence,
                "evidence": list(raw.get("evidence") or []),
                "actions": list(raw.get("actions") or []),
            }
        )

    if kg_facts is not None:
        cap = _chain_max_confidence(kg_facts)
        _apply_confidence_cap(diagnosis_results, cap)

    root_cause = _derive_root_cause(diagnosis_results)

    return {
        "query": query,
        "summary": summary,
        "diagnosis_results": diagnosis_results,
        "root_cause": root_cause,
        "warnings": list(data.get("warnings") or []),
        "route_used": str(data.get("route_used") or route),
    }


def _derive_root_cause(diagnosis_results: list[dict[str, Any]]) -> str:
    for result in _sort_results(diagnosis_results):
        possible_cause = _nullable_text(result.get("possible_cause"))
        if possible_cause:
            return possible_cause
    return _DEFAULT_ROOT_CAUSE


def _sort_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    return sorted(
        results,
        key=lambda item: (
            priority.get(str(item.get("confidence") or "unknown"), 3),
            -len(item.get("evidence") or []),
            -len(item.get("actions") or []),
        ),
    )


def _nullable_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _chain_max_confidence(kg_facts: Mapping[str, Any]) -> str:
    """Return the maximum confidence level warranted by KG chain completeness.

    Fault + Cause + Action + Steps in any item → high allowed.
    (error_code is the query entry point, not a chain quality indicator.)
    Cause + Action present but no Steps in any item → medium cap.
    Otherwise → low cap.
    """
    items = list(kg_facts.get("items") or [])
    if not items:
        return "unknown"
    for item in items:
        if (
            item.get("fault")
            and item.get("cause")
            and item.get("action")
            and item.get("steps")
        ):
            return "high"
    for item in items:
        if item.get("cause") and item.get("action"):
            return "medium"
    return "low"


def _apply_confidence_cap(diagnosis_results: list[dict[str, Any]], max_confidence: str) -> None:
    """Cap each result's confidence so it does not exceed max_confidence."""
    max_ord = _CONFIDENCE_ORDER.get(max_confidence, 3)
    for dr in diagnosis_results:
        current_ord = _CONFIDENCE_ORDER.get(dr.get("confidence", "unknown"), 3)
        if current_ord < max_ord:
            dr["confidence"] = max_confidence


def _empty_conclusion(query: str, route: str, *, reason: str) -> dict[str, Any]:
    return {
        "query": query,
        "summary": {"headline": "", "user_safe_summary": ""},
        "diagnosis_results": [],
        "root_cause": _DEFAULT_ROOT_CAUSE,
        "warnings": [reason],
        "route_used": route,
    }
