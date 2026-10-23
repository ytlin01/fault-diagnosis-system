"""Unified answer assembly helpers for Route B and Route C.

The module consumes already-governed route outputs. It does not retrieve data,
open raw sources, or promote evidence-only/candidate material into reviewed
diagnosis.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from services.providers.llm import BaseProvider, ProviderRequest
from services.routing.query_router import (
    CASE_RETRIEVAL,
    DOCUMENT_EVIDENCE_RETRIEVAL,
    FP_REVIEW_GOVERNANCE,
    STRUCTURED_CATALOG,
)


_PROMPT_DIR = Path(__file__).parent / "prompts"
_PROMPT_BY_ROUTE = {
    DOCUMENT_EVIDENCE_RETRIEVAL: _PROMPT_DIR / "route_b_document_evidence_synthesis.txt",
    CASE_RETRIEVAL: _PROMPT_DIR / "route_c_case_reference_synthesis.txt",
    FP_REVIEW_GOVERNANCE: _PROMPT_DIR / "route_c_case_reference_synthesis.txt",
    STRUCTURED_CATALOG: _PROMPT_DIR / "route_c_case_reference_synthesis.txt",
}
_CONFIDENCE_VALUES = frozenset({"medium", "low", "unknown"})


_SCHEMA_HINT = """{
  "summary": {
    "headline": "<short user-facing title>",
    "user_safe_summary": "<1-3 sentence safe summary>"
  },
  "diagnosis_results": [
    {
      "title": "<result title>",
      "possible_cause": null,
      "description": "<safe description grounded only in route output>",
      "confidence": "medium | low | unknown",
      "evidence": [
        {
          "evidence_type": "document_snippet | related_case | structured_catalog",
          "source_name": "<source name from input>",
          "source_id": "<source id from input>",
          "anchor": "<anchor from input>",
          "summary": "<evidence summary from input>"
        }
      ],
      "actions": []
    }
  ],
  "root_cause": "<route-specific non-confirmation placeholder>",
  "root_cause_actions": [],
  "warnings": ["<route boundary or missing evidence warning>"],
  "route_used": "route_b | route_c"
}"""
_LANGUAGE_REQUIREMENT = (
    "输出语言要求：JSON 字段名必须保持 schema_hint 不变；所有面向用户的自然语言字段，"
    "包括 summary、title、description、root_cause、warnings 和 actions[].action，必须使用简体中文。"
)


def synthesize_route_output(
    query: str,
    route: str,
    route_output: Mapping[str, Any],
    *,
    provider: BaseProvider | None = None,
) -> dict[str, Any]:
    """Return a DiagnosisConclusion-like payload for Route B/C assembly.

    If a non-stub provider is supplied, it is used with the route-specific
    prompt. The returned text is treated as advisory: sources, statuses, and
    actions are still re-projected from the serving-safe route output.
    """

    route_key = str(route)
    if route_key == DOCUMENT_EVIDENCE_RETRIEVAL:
        config = _route_b_config()
    elif route_key in {CASE_RETRIEVAL, FP_REVIEW_GOVERNANCE, STRUCTURED_CATALOG}:
        config = _route_c_config(route_key)
    else:
        return _empty_conclusion(
            query,
            route_used="unknown",
            root_cause="统一 Route B/C 组装暂不支持该路由输出。",
            warning=f"统一组装暂不支持该路由：{route_key}",
        )

    items = _route_items(route_output)
    warnings = _route_warnings(route_output)
    if not items:
        return _empty_conclusion(
            query,
            route_used=config["route_used"],
            root_cause=config["root_cause"],
            warning=config["empty_warning"],
            extra_warnings=warnings,
        )

    llm_payload = _try_llm_synthesis(query, route_key, route_output, provider=provider)
    summary = _summary_from_llm(llm_payload) or _deterministic_summary(config, len(items), warnings)
    llm_results = _llm_results(llm_payload)
    results = [
        _safe_result_from_item(
            raw,
            config,
            llm_result=llm_results[index] if index < len(llm_results) else None,
        )
        for index, raw in enumerate(items)
        if isinstance(raw, Mapping)
    ]

    return {
        "query": query,
        "summary": summary,
        "diagnosis_results": results,
        "root_cause": config["root_cause"],
        "root_cause_actions": [],
        "warnings": _dedupe_warnings(warnings + _llm_warnings(llm_payload) + [config["boundary_warning"]]),
        "route_used": config["route_used"],
    }


def fixture_route_output(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Project one serving-safe fixture case into a route_output-shaped object."""

    expected = fixture.get("expected", {})
    if not isinstance(expected, Mapping):
        return {"items": [], "used_sources": [], "warnings": ["Fixture expected payload 无效。"]}

    route_family = str(expected.get("route_family") or "")
    if route_family == "route_b_document":
        return _route_b_fixture_output(expected)
    if route_family == "route_c_case_governance":
        return _route_c_fixture_output(expected)
    return {"items": [], "used_sources": [], "warnings": [f"不支持的 fixture route_family：{route_family}"]}


def _try_llm_synthesis(
    query: str,
    route: str,
    route_output: Mapping[str, Any],
    *,
    provider: BaseProvider | None,
) -> Mapping[str, Any] | None:
    if provider is None or getattr(provider, "provider_type", "") == "stub":
        return None
    prompt_path = _PROMPT_BY_ROUTE.get(route)
    if prompt_path is None:
        return None
    try:
        template = prompt_path.read_text(encoding="utf-8")
        prompt = template.format(
            query=query,
            schema_hint=_SCHEMA_HINT,
            output_language_requirement=_LANGUAGE_REQUIREMENT,
            route_b_evidence_json=json.dumps(_prompt_projection(route_output), ensure_ascii=False, indent=2),
            route_c_candidates_json=json.dumps(_prompt_projection(route_output), ensure_ascii=False, indent=2),
        )
        response = provider.generate(ProviderRequest(prompt=prompt, metadata={"route": route}))
        return _parse_json_object(response.text)
    except Exception:
        return None


def _prompt_projection(route_output: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "items": list(route_output.get("items") or []),
        "used_sources": list(route_output.get("used_sources") or []),
        "warnings": list(route_output.get("warnings") or []),
    }


def _parse_json_object(text: str) -> Mapping[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    payload = json.loads(match.group())
    return payload if isinstance(payload, Mapping) else None


def _safe_result_from_item(
    raw: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    llm_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    title = _text((llm_result or {}).get("title")) or _text(raw.get("title")) or config["default_title"]
    description = _text((llm_result or {}).get("description")) or _text(raw.get("description"))
    if not description:
        description = config["default_description"]
    confidence = _confidence(_text((llm_result or {}).get("confidence")) or _text(raw.get("confidence")))
    result: dict[str, Any] = {
        "title": title,
        "possible_cause": _allowed_possible_cause(raw, config),
        "description": description,
        "confidence": confidence,
        "evidence": _safe_evidence(raw.get("evidence"), config),
        "actions": _safe_actions(raw.get("actions"), config),
    }
    return result


def _safe_evidence(raw_evidence: Any, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw_evidence, list):
        return []
    evidence_items: list[dict[str, Any]] = []
    for raw in raw_evidence:
        if not isinstance(raw, Mapping):
            continue
        source_id = _text(raw.get("source_id"))
        source_name = _text(raw.get("source_name")) or _text(raw.get("source_type")) or config["source_name"]
        evidence_items.append(
            {
                "evidence_type": config["evidence_type"],
                "source_name": source_name,
                "source_id": source_id,
                "anchor": raw.get("anchor") or source_id or None,
                "summary": _text(raw.get("summary")) or _text(raw.get("description")),
            }
        )
    return evidence_items


def _safe_actions(raw_actions: Any, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list):
        return []
    actions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_actions, start=1):
        if not isinstance(raw, Mapping):
            continue
        action = _text(raw.get("action"))
        if not action:
            continue
        actions.append(
            {
                "step": int(raw.get("step") or index),
                "action": action,
                "source_status": config["action_source_status"],
            }
        )
    return actions


def _allowed_possible_cause(raw: Mapping[str, Any], config: Mapping[str, Any]) -> str | None:
    if not config["allow_possible_cause"]:
        return None
    return _nullable_text(raw.get("possible_cause"))


def _empty_conclusion(
    query: str,
    *,
    route_used: str,
    root_cause: str,
    warning: str,
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings = _dedupe_warnings([warning] + list(extra_warnings or []))
    return {
        "query": query,
        "summary": {
            "headline": "未组装到可服务的安全证据。",
            "user_safe_summary": warning,
        },
        "diagnosis_results": [],
        "root_cause": root_cause,
        "root_cause_actions": [],
        "warnings": warnings,
        "route_used": route_used,
    }


def _route_b_config() -> dict[str, Any]:
    return {
        "route_used": "route_b",
        "result_type": "document_evidence",
        "status": "evidence_only",
        "evidence_type": "document_snippet",
        "source_type": "serving_document",
        "source_name": "serving_document",
        "action_source_status": "evidence_supported",
        "root_cause": "Route B 仅提供文档证据，不确认根因。",
        "default_title": "文档证据参考",
        "default_description": "Route B 返回了 serving-safe 文档证据。",
        "summary_headline": "Route B 仅返回文档证据。",
        "summary_text": "本次组装仅限于 serving-safe 文档证据，不形成诊断结论。",
        "empty_warning": "Route B 未返回可服务的文档证据。",
        "boundary_warning": "Route B 是 evidence_only，不能当作诊断结论。",
        "allow_possible_cause": False,
    }


def _route_c_config(route: str) -> dict[str, Any]:
    return {
        "route_used": "route_c",
        "result_type": "case_reference",
        "status": "candidate",
        "evidence_type": "structured_catalog" if route == STRUCTURED_CATALOG else "related_case",
        "source_type": "structured_catalog" if route == STRUCTURED_CATALOG else "structured_case_candidate",
        "source_name": "structured_case_candidate",
        "action_source_status": "candidate_supported",
        "root_cause": "Route C 仅提供相似案例候选参考，不确认根因。",
        "default_title": "候选案例参考",
        "default_description": "Route C 返回了治理安全的候选参考。",
        "summary_headline": "Route C 仅返回候选案例参考。",
        "summary_text": "本次组装仅限于候选案例参考，不形成诊断结论。",
        "empty_warning": "Route C 未返回治理安全的候选参考。",
        "boundary_warning": "Route C 是 candidate-only，不能当作 reviewed 结果。",
        "allow_possible_cause": False,
    }


def _deterministic_summary(
    config: Mapping[str, Any],
    count: int,
    warnings: list[str],
) -> dict[str, str]:
    suffix = f" 已保留 {len(warnings)} 条警告。" if warnings else ""
    return {
        "headline": str(config["summary_headline"]),
        "user_safe_summary": f"{config['summary_text']} 本次组装 {count} 条结果。{suffix}",
    }


def _summary_from_llm(payload: Mapping[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get("summary")
    if not isinstance(raw, Mapping):
        return None
    headline = _text(raw.get("headline"))
    if not headline:
        return None
    return {
        "headline": headline,
        "user_safe_summary": _text(raw.get("user_safe_summary")),
    }


def _llm_results(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("diagnosis_results"), list):
        return []
    return [item for item in payload["diagnosis_results"] if isinstance(item, Mapping)]


def _llm_warnings(payload: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("warnings"), list):
        return []
    return [_text(item) for item in payload["warnings"] if _text(item)]


def _route_items(route_output: Mapping[str, Any]) -> list[Any]:
    value = route_output.get("items")
    return list(value) if isinstance(value, list) else []


def _route_warnings(route_output: Mapping[str, Any]) -> list[str]:
    value = route_output.get("warnings")
    return [_text(item) for item in value] if isinstance(value, list) else []


def _confidence(value: str) -> str:
    return value if value in _CONFIDENCE_VALUES else "unknown"


def _nullable_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for warning in warnings:
        text = _text(warning)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _route_b_fixture_output(expected: Mapping[str, Any]) -> dict[str, Any]:
    if expected.get("no_hit"):
        return {
            "items": [],
            "used_sources": [{"source_type": "serving_document", "source_id": "data/serving_unstructured_vlm", "snapshot_id": None, "updated_at": None}],
            "warnings": ["Fixture 预期 Route B 无命中或证据不足。"],
        }
    block_ids = list(expected.get("acceptable_block_ids") or [])
    block_id = _text(block_ids[0] if block_ids else "")
    doc_id = _text(expected.get("doc_id")) or "data/serving_unstructured_vlm"
    summary = f"Fixture 文档证据锚点：{block_id or doc_id}"
    return {
        "items": [
            {
                "rank": 1,
                "title": "文档证据 fixture",
                "result_type": "document_evidence",
                "status": "evidence_only",
                "confidence": "medium",
                "description": summary,
                "evidence": [
                    {
                        "evidence_type": "document_snippet",
                        "source_type": "serving_document",
                        "source_name": doc_id,
                        "source_id": block_id or doc_id,
                        "anchor": block_id or doc_id,
                        "reviewed": False,
                        "serving_safe": True,
                        "summary": summary,
                    }
                ],
            }
        ],
        "used_sources": [{"source_type": "serving_document", "source_id": "data/serving_unstructured_vlm", "snapshot_id": None, "updated_at": None}],
        "warnings": [],
    }


def _route_c_fixture_output(expected: Mapping[str, Any]) -> dict[str, Any]:
    if expected.get("no_hit"):
        return {
            "items": [],
            "used_sources": [{"source_type": "structured_case_candidate", "source_id": "rag_fp_case_candidates_v1", "snapshot_id": None, "updated_at": None}],
            "warnings": ["Fixture 预期 Route C 无命中。"],
        }
    candidate_ids = list(expected.get("acceptable_candidate_ids") or [])
    candidate_id = _text(candidate_ids[0] if candidate_ids else "")
    source_id = f"rag_fp_case_candidates_v1:{candidate_id}" if candidate_id else "rag_fp_case_candidates_v1"
    summary = f"Fixture 候选案例锚点：{candidate_id or source_id}"
    return {
        "items": [
            {
                "rank": 1,
                "title": "候选案例参考 fixture",
                "result_type": "case_reference",
                "status": "candidate",
                "confidence": "medium",
                "description": summary,
                "evidence": [
                    {
                        "evidence_type": "related_case",
                        "source_type": "structured_case_candidate",
                        "source_name": "rag_fp_case_candidates_v1",
                        "source_id": source_id,
                        "anchor": source_id,
                        "reviewed": False,
                        "serving_safe": True,
                        "summary": summary,
                    }
                ],
            }
        ],
        "used_sources": [{"source_type": "structured_case_candidate", "source_id": "rag_fp_case_candidates_v1", "snapshot_id": None, "updated_at": None}],
        "warnings": [],
    }
