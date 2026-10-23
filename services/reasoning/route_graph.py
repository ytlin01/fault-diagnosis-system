"""Minimal LangGraph route skeleton for TASK-012.

The graph is intentionally thin: it orchestrates canonicalization, the
deterministic policy router, branch slots, and one result assembler. Real Route
B/C retrieval and Route A structured execution belong to later tasks.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path 
from typing import Any, Mapping, TypedDict

from services.canonicalization.prekg import canonicalize_query
from services.reasoning.diagnosis_synthesizer import synthesize as _synthesize_conclusion
from services.reasoning.unified_answer_assembler import synthesize_route_output
from services.retrieval.route_a_executor import execute_route_a
from services.retrieval.route_b_executor import execute_route_b_document
from services.retrieval.route_c_executor import execute_route_c
from services.routing.query_router import (
    ASSET_STRUCTURED_QUERY,
    CASE_RETRIEVAL,
    DOCUMENT_EVIDENCE_RETRIEVAL,
    FP_REVIEW_GOVERNANCE,
    INSUFFICIENT_CONTEXT,
    REVIEWED_DIAGNOSTIC_CHAIN,
    UNREVIEWED_DIAGNOSTIC_CHAIN,
    ROUTE_A_STRUCTURED,
    ROUTE_B_DOCUMENT,
    ROUTE_C_CASE_GOVERNANCE,
    ROUTE_FALLBACK,
    STRUCTURED_CATALOG,
    RoutingContext,
    RoutingDecision,
    RoutingRequest,
    route_query,
)


RESULT_CONTRACT_VERSION = "1.0.0-draft"

_DEFAULT_ASSET_INDEX_PATH = Path("data/processed/Y24_C1STN_Di_matched/node_name_index.json")


class LangGraphUnavailableError(RuntimeError):
    """Raised when the LangGraph runtime dependency is not installed."""


class RouteGraphState(TypedDict, total=False):
    diagnosis_request: dict[str, Any]
    canonical_state: dict[str, Any]
    routing_context: RoutingContext
    routing_decision: dict[str, Any]
    route_output: dict[str, Any]
    api_response: dict[str, Any]
    trace: dict[str, Any]


def build_route_graph() -> Any:
    """Build and compile the TASK-012 LangGraph route skeleton."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover - covered by env-dependent test.
        raise LangGraphUnavailableError(
            "LangGraph is required for build_route_graph(). Install requirements/base.txt."
        ) from exc

    graph = StateGraph(RouteGraphState)
    graph.add_node("canonicalize", canonicalize_node)
    graph.add_node("deterministic_route", deterministic_route_node)
    graph.add_node("route_a_structured_slot", route_a_structured_slot)
    graph.add_node("route_b_document_slot", route_b_document_slot)
    graph.add_node("route_c_case_governance_slot", route_c_case_governance_slot)
    graph.add_node("fallback_slot", fallback_slot)
    graph.add_node("assemble_result", assemble_result_node)

    graph.set_entry_point("canonicalize")
    graph.add_edge("canonicalize", "deterministic_route")
    graph.add_conditional_edges(
        "deterministic_route",
        route_dispatch,
        {
            ROUTE_A_STRUCTURED: "route_a_structured_slot",
            ROUTE_B_DOCUMENT: "route_b_document_slot",
            ROUTE_C_CASE_GOVERNANCE: "route_c_case_governance_slot",
            ROUTE_FALLBACK: "fallback_slot",
        },
    )
    graph.add_edge("route_a_structured_slot", "assemble_result")
    graph.add_edge("route_b_document_slot", "assemble_result")
    graph.add_edge("route_c_case_governance_slot", "assemble_result")
    graph.add_edge("fallback_slot", "assemble_result")
    graph.add_edge("assemble_result", END)
    return graph.compile()


def run_route_graph(
    diagnosis_request: Mapping[str, Any],
    *,
    routing_context: RoutingContext | None = None,
) -> dict[str, Any]:
    """Run the compiled LangGraph skeleton for one diagnosis request."""
    initial_state: RouteGraphState = {
        "diagnosis_request": dict(diagnosis_request),
        "trace": _initial_trace(diagnosis_request),
    }
    if routing_context is not None:
        initial_state["routing_context"] = routing_context
    return build_route_graph().invoke(initial_state)


def run_route_graph_dry_run(
    diagnosis_request: Mapping[str, Any],
    *,
    routing_context: RoutingContext | None = None,
) -> dict[str, Any]:
    """Run the same node sequence without LangGraph for local dry-run tests."""
    state: RouteGraphState = {
        "diagnosis_request": dict(diagnosis_request),
        "trace": _initial_trace(diagnosis_request),
    }
    if routing_context is not None:
        state["routing_context"] = routing_context

    state.update(canonicalize_node(state))
    state.update(deterministic_route_node(state))
    branch = route_dispatch(state)
    if branch == ROUTE_A_STRUCTURED:
        state.update(route_a_structured_slot(state))
    elif branch == ROUTE_B_DOCUMENT:
        state.update(route_b_document_slot(state))
    elif branch == ROUTE_C_CASE_GOVERNANCE:
        state.update(route_c_case_governance_slot(state))
    else:
        state.update(fallback_slot(state))
    state.update(assemble_result_node(state))
    return dict(state)


def canonicalize_node(state: RouteGraphState) -> dict[str, Any]:
    request = state.get("diagnosis_request", {})
    asset_index = _load_asset_index(request.get("asset_index_path"))
    canonical_state = canonicalize_query(
        str(request.get("query_text", "")),
        received_at=request.get("received_at"),
        language=str(request.get("language", "zh-CN")),
        asset_index=asset_index,
    )
    return {
        "canonical_state": canonical_state.as_dict(),
        "trace": _append_event(state, "canonicalize"),
    }


def deterministic_route_node(state: RouteGraphState) -> dict[str, Any]:
    request = state.get("diagnosis_request", {})
    routing_request = RoutingRequest(
        query_text=str(request.get("query_text", "")),
        query_type_hint=request.get("query_type_hint"),
        available_sources=tuple(str(source) for source in request.get("available_sources", ())),
        safety_mode=str(request.get("safety_mode", "default")),
    )
    context = state.get("routing_context")
    decision = route_query(routing_request, context if isinstance(context, RoutingContext) else None)
    return {
        "routing_decision": decision.as_dict(),
        "trace": _append_event(state, "deterministic_route"),
    }


def route_dispatch(state: RouteGraphState) -> str:
    decision = state.get("routing_decision", {})
    route_family = decision.get("route_family")
    if route_family in {
        ROUTE_A_STRUCTURED,
        ROUTE_B_DOCUMENT,
        ROUTE_C_CASE_GOVERNANCE,
        ROUTE_FALLBACK,
    }:
        return str(route_family)
    return ROUTE_FALLBACK


def route_a_structured_slot(state: RouteGraphState) -> dict[str, Any]:
    decision = _decision(state)
    request = state.get("diagnosis_request", {})
    output = execute_route_a(
        state.get("canonical_state", {}),
        route=str(decision["route"]),
        allowed_sources=tuple(decision.get("allowed_sources", ())),
    )
    query_text = str(request.get("query_text", ""))
    provider = request.get("_provider")  # injected by CLI; None → synthesizer builds its own
    diagnosis_conclusion = _synthesize_conclusion(query_text, output, "route_a", provider=provider)
    return _slot_output_from_executor(state, output, diagnosis_conclusion=diagnosis_conclusion)


def route_b_document_slot(state: RouteGraphState) -> dict[str, Any]:
    decision = _decision(state)
    request = state.get("diagnosis_request", {})
    top_k = request.get("top_k")
    output = execute_route_b_document(
        str(request.get("query_text", "")),
        allowed_sources=tuple(decision.get("allowed_sources", ())),
        source_dir=request.get("route_b_source_dir", "data/serving_unstructured_vlm"),
        top_k=int(top_k) if top_k is not None else None,
    )
    diagnosis_conclusion = synthesize_route_output(
        str(request.get("query_text", "")),
        str(decision["route"]),
        output,
        provider=request.get("_provider"),
    )
    return _slot_output_from_executor(state, output, diagnosis_conclusion=diagnosis_conclusion)


def route_c_case_governance_slot(state: RouteGraphState) -> dict[str, Any]:
    decision = _decision(state)
    allowed_sources = tuple(decision.get("allowed_sources", ()))
    request = state.get("diagnosis_request", {})
    light_rag_config = request.get("route_c_light_rag", {})
    if not isinstance(light_rag_config, Mapping):
        light_rag_config = {}
    output = execute_route_c(
        str(request.get("query_text", "")),
        route=str(decision["route"]),
        allowed_sources=allowed_sources,
        source_paths=_route_c_source_paths(request),
        top_k=int(request.get("top_k", 3) or 3),
        min_score=float(request.get("route_c_min_score", 0.1) or 0.1),
        enable_light_rag=bool(light_rag_config.get("enabled", False)),
        light_rag_config=light_rag_config,
    )
    diagnosis_conclusion = synthesize_route_output(
        str(request.get("query_text", "")),
        str(decision["route"]),
        output,
        provider=request.get("_provider"),
    )
    return _slot_output_from_executor(state, output, diagnosis_conclusion=diagnosis_conclusion)


def fallback_slot(state: RouteGraphState) -> dict[str, Any]:
    return _slot_output(
        state,
        warnings=("Fallback slot produced no route items because context is insufficient or unsafe.",),
    )


def assemble_result_node(state: RouteGraphState) -> dict[str, Any]:
    decision = _decision(state)
    route_output = state.get("route_output", {})
    canonical_state = state.get("canonical_state", {})
    route = str(decision["route"])

    conclusion = route_output.get("diagnosis_conclusion")
    if isinstance(conclusion, Mapping) and conclusion.get("diagnosis_results"):
        diagnosis_results = _normalize_conclusion_results(conclusion, route)
        summary = _summary_from_conclusion(conclusion) or _summary_for_decision(decision)
    else:
        diagnosis_results = list(route_output.get("items", []))
        summary = _summary_for_decision(decision)
    root_cause = _root_cause_for_route(route, diagnosis_results, conclusion)
    root_cause_actions = [] if _is_non_diagnostic_route(route) else (
        list(diagnosis_results[0].get("actions") or []) if diagnosis_results else []
    )

    api_response = {
        "contract_version": RESULT_CONTRACT_VERSION,
        "query": _public_query(canonical_state.get("query", {})),
        "decision": {
            "route_family": decision["route_family"],
            "route": route,
            "answer_type": _answer_type(route),
            "status": _decision_status(route),
            "requires_review": bool(decision.get("requires_review", False)),
        },
        "entities": _public_entities(canonical_state.get("entities", {})),
        "knowledge_context": {
            "used_sources": deepcopy(route_output.get("used_sources", [])),
        },
        "summary": summary,
        "diagnosis_results": diagnosis_results,
        "root_cause": root_cause,
        "root_cause_actions": root_cause_actions,
    }
    trace = _append_event(state, "assemble_result")
    if trace.get("enabled"):
        api_response["trace"] = {
            "enabled": True,
            "tools_used": [],
            "cypher_executed": [],
            "retrieval_queries": [],
            "router_reason": decision.get("reason"),
            "executor_timings": {},
        }
    return {"api_response": api_response, "trace": trace}


_SOURCE_STATUS: dict[str, str] = {
    REVIEWED_DIAGNOSTIC_CHAIN: "reviewed_supported",
    ASSET_STRUCTURED_QUERY: "reviewed_supported",
    DOCUMENT_EVIDENCE_RETRIEVAL: "evidence_supported",
    CASE_RETRIEVAL: "candidate_supported",
    FP_REVIEW_GOVERNANCE: "candidate_supported",
    STRUCTURED_CATALOG: "candidate_supported",
}

_SOURCE_TYPES: dict[str, str] = {
    REVIEWED_DIAGNOSTIC_CHAIN: "reviewed_structured_chain",
    ASSET_STRUCTURED_QUERY: "reviewed_asset_graph",
    DOCUMENT_EVIDENCE_RETRIEVAL: "serving_document",
    STRUCTURED_CATALOG: "structured_catalog",
    CASE_RETRIEVAL: "structured_case_candidate",
    FP_REVIEW_GOVERNANCE: "governance_candidate",
}


def _normalize_conclusion_results(conclusion: Mapping[str, Any], route: str) -> list[dict[str, Any]]:
    source_status = _SOURCE_STATUS.get(route, "not_available")
    result_type = _answer_type(route)
    status = _decision_status(route)
    reviewed = status == "reviewed"
    normalized = []
    for rank, raw in enumerate(conclusion.get("diagnosis_results") or [], start=1):
        if not isinstance(raw, Mapping):
            continue
        result: dict[str, Any] = {
            "rank": rank,
            "title": str(raw.get("title") or ""),
            "possible_cause": _nullable_text(raw.get("possible_cause")),
            "result_type": result_type,
            "status": status,
            "confidence": _confidence(str(raw.get("confidence") or "unknown")),
            "description": str(raw.get("description") or ""),
            "evidence": _normalize_evidence(raw.get("evidence"), route, reviewed),
        }
        actions = _normalize_actions(raw.get("actions"), source_status)
        if actions:
            result["actions"] = actions
        normalized.append(result)
    return _sort_and_rerank_results(normalized)


def _nullable_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _sort_and_rerank_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    sorted_results = sorted(
        results,
        key=lambda x: (
            priority.get(str(x.get("confidence") or "unknown"), 3),
            -len(x.get("evidence") or []),
            -len(x.get("actions") or []),
            int(x.get("rank") or 9999),
        ),
    )
    for idx, item in enumerate(sorted_results, start=1):
        item["rank"] = idx
    return sorted_results


def _derive_user_root_cause(diagnosis_results: list[dict[str, Any]]) -> str:
    for item in diagnosis_results:
        cause = _nullable_text(item.get("possible_cause"))
        if cause:
            return cause
    return "证据不足，暂无法确认"


def _root_cause_for_route(
    route: str,
    diagnosis_results: list[dict[str, Any]],
    conclusion: Mapping[str, Any] | None,
) -> str:
    if _is_non_diagnostic_route(route):
        if isinstance(conclusion, Mapping):
            root_cause = _nullable_text(conclusion.get("root_cause"))
            if root_cause:
                return root_cause
        if route == DOCUMENT_EVIDENCE_RETRIEVAL:
            return "Route B provides document evidence only; root cause is not determined."
        return "Route C provides candidate references only; root cause is not determined."
    return _derive_user_root_cause(diagnosis_results)


def _is_non_diagnostic_route(route: str) -> bool:
    return route in {
        DOCUMENT_EVIDENCE_RETRIEVAL,
        CASE_RETRIEVAL,
        STRUCTURED_CATALOG,
        FP_REVIEW_GOVERNANCE,
    }


def _normalize_evidence(raw_evidence: Any, route: str, reviewed: bool) -> list[dict[str, Any]]:
    if not isinstance(raw_evidence, list):
        return []
    source_type = _SOURCE_TYPES.get(route, "governance_candidate")
    items = []
    for raw in raw_evidence:
        if not isinstance(raw, Mapping):
            continue
        source_id = str(raw.get("source_id") or "")
        source_name = _safe_source_name(source_id, str(raw.get("source_name") or ""))
        items.append({
            "evidence_type": str(raw.get("evidence_type") or "reviewed_mapping"),
            "source_type": source_type,
            "source_name": source_name,
            "source_id": source_id,
            "anchor": raw.get("anchor") or source_id or None,
            "reviewed": reviewed,
            "serving_safe": True,
            "summary": str(raw.get("summary") or ""),
        })
    return items


_FAULT_CODE_STYLE = re.compile(r"^[A-Z0-9_]+$")


def _safe_source_name(source_id: str, source_name: str) -> str:
    """Avoid exposing raw `fault.name` code-like tokens to users."""
    if source_id.startswith("fault:") and _FAULT_CODE_STYLE.fullmatch(source_name or ""):
        return ""
    return source_name


def _normalize_actions(raw_actions: Any, source_status: str) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list):
        return []
    items = []
    for raw in raw_actions:
        if not isinstance(raw, Mapping):
            continue
        items.append({
            "step": int(raw.get("step") or 1),
            "action": str(raw.get("action") or ""),
            "source_status": source_status,
        })
    return items


def _confidence(value: str) -> str:
    return value if value in {"high", "medium", "low", "unknown"} else "unknown"


def _summary_from_conclusion(conclusion: Mapping[str, Any]) -> dict[str, str] | None:
    raw = conclusion.get("summary")
    if not isinstance(raw, Mapping):
        return None
    headline = str(raw.get("headline") or "")
    if not headline:
        return None
    return {
        "headline": headline,
        "user_safe_summary": str(raw.get("user_safe_summary") or ""),
    }


def _slot_output(
    state: RouteGraphState,
    *,
    used_sources: list[dict[str, Any]] | None = None,
    source_metadata: list[dict[str, Any]] | None = None,
    warnings: tuple[str, ...] = (),
) -> dict[str, Any]:
    route_output: dict[str, Any] = {
        "items": [],
        "used_sources": used_sources or [],
        "warnings": list(warnings),
    }
    if source_metadata:
        route_output["source_metadata"] = source_metadata
    return {
        "route_output": route_output,
        "trace": _append_event(state, "execute_route_slot"),
    }


def _slot_output_from_executor(
    state: RouteGraphState,
    output: Mapping[str, Any],
    *,
    diagnosis_conclusion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # route_output value schema: items/used_sources/warnings from executor +
    # optional diagnosis_conclusion (DiagnosisConclusion dict) from reasoning layer.
    route_output: dict[str, Any] = {
        "items": list(output.get("items", [])),
        "used_sources": list(output.get("used_sources", [])),
        "warnings": list(output.get("warnings", [])),
    }
    source_metadata = output.get("source_metadata")
    if source_metadata:
        route_output["source_metadata"] = list(source_metadata)
    if diagnosis_conclusion is not None:
        route_output["diagnosis_conclusion"] = diagnosis_conclusion
    return {"route_output": route_output, "trace": _append_event(state, "execute_route_slot")}


def _decision(state: RouteGraphState) -> dict[str, Any]:
    decision = state.get("routing_decision")
    if not decision:
        fallback = RoutingDecision(
            route_family=ROUTE_FALLBACK,
            route=INSUFFICIENT_CONTEXT,
            intent="unknown",
            reason="No routing decision was available.",
        )
        return fallback.as_dict()
    return dict(decision)


def _route_c_source_paths(request: Mapping[str, Any]) -> dict[str, Path]:
    raw = request.get("route_c_source_paths", {})
    if not isinstance(raw, Mapping):
        return {}
    return {str(source_id): Path(str(path)) for source_id, path in raw.items()}


def _answer_type(route: str) -> str:
    if route == REVIEWED_DIAGNOSTIC_CHAIN:
        return "confirmed_diagnosis"
    if route == ASSET_STRUCTURED_QUERY:
        return "asset_answer"
    if route == DOCUMENT_EVIDENCE_RETRIEVAL:
        return "document_evidence"
    if route == CASE_RETRIEVAL:
        return "case_reference"
    if route in {STRUCTURED_CATALOG, FP_REVIEW_GOVERNANCE}:
        return "diagnostic_hypothesis"
    return "insufficient_context"


def _decision_status(route: str) -> str:
    if route in {REVIEWED_DIAGNOSTIC_CHAIN, ASSET_STRUCTURED_QUERY}:
        return "reviewed"
    if route == DOCUMENT_EVIDENCE_RETRIEVAL:
        return "evidence_only"
    if route in {STRUCTURED_CATALOG, CASE_RETRIEVAL, FP_REVIEW_GOVERNANCE}:
        return "candidate"
    return "not_available"


def _summary_for_decision(decision: Mapping[str, Any]) -> dict[str, str]:
    route = decision.get("route")
    if route in {REVIEWED_DIAGNOSTIC_CHAIN, ASSET_STRUCTURED_QUERY}:
        return {
            "headline": "已进入 reviewed structured 路径",
            "user_safe_summary": "当前 TASK-012 只验证 Route A 挂接点，真实结构化执行将在 reviewed source 绑定后接入。",
        }
    if route == DOCUMENT_EVIDENCE_RETRIEVAL:
        return {
            "headline": "已进入文档证据路径",
            "user_safe_summary": "当前 TASK-012 只验证 Route B 挂接点，真实 serving-safe 文档检索将在后续 executor 中接入。",
        }
    if route in {STRUCTURED_CATALOG, CASE_RETRIEVAL, FP_REVIEW_GOVERNANCE}:
        return {
            "headline": "当前只能进入候选或治理路径",
            "user_safe_summary": "未使用 reviewed 诊断链；当前主图只完成 Route C 挂接，真实案例或治理执行将在后续 executor 中接入。",
        }
    return {
        "headline": "当前上下文不足",
        "user_safe_summary": str(decision.get("reason") or "当前输入不足以进入可服务诊断路径。"),
    }


def _public_query(query: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "text": str(query.get("text", "")),
        "normalized_text": str(query.get("normalized_text", "")),
        "language": str(query.get("language", "unknown")),
        "received_at": str(query.get("received_at", "")),
    }


def _public_entities(entities: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "asset": {
            "station": _entity_slot(entities, "asset", "station"),
            "module": _entity_slot(entities, "asset", "module"),
            "component": _entity_slot(entities, "asset", "component"),
        },
        "diagnostic": {
            "error_code": _entity_slot(entities, "diagnostic", "error_code"),
            "fault": _entity_slot(entities, "diagnostic", "fault"),
            "cause": _entity_slot(entities, "diagnostic", "cause"),
            "action": _entity_slot(entities, "diagnostic", "action"),
        },
        "observation": {
            "phenomenon_text": _phenomenon_slot(entities, "observation", "phenomenon_text"),
            "time_context": _entity_slot(entities, "observation", "time_context"),
        },
    }


def _entity_slot(entities: Mapping[str, Any], group: str, name: str) -> dict[str, Any]:
    slot = _nested_slot(entities, group, name)
    return {
        "raw": slot.get("raw"),
        "canonical": slot.get("canonical"),
        "confidence": slot.get("confidence", "unknown"),
    }


def _phenomenon_slot(entities: Mapping[str, Any], group: str, name: str) -> dict[str, Any]:
    slot = _entity_slot(entities, group, name)
    source = _nested_slot(entities, group, name)
    if "normalized_tokens" in source:
        slot["normalized_tokens"] = list(source.get("normalized_tokens", []))
    return slot


def _nested_slot(entities: Mapping[str, Any], group: str, name: str) -> Mapping[str, Any]:
    value = entities.get(group, {})
    if not isinstance(value, Mapping):
        return {}
    slot = value.get(name, {})
    return slot if isinstance(slot, Mapping) else {}


def _load_asset_index(index_path: str | Path | None = None) -> dict | None:
    """Load node_name_index.json from the given path or the default location."""
    path = Path(index_path) if index_path else _DEFAULT_ASSET_INDEX_PATH
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _initial_trace(request: Mapping[str, Any]) -> dict[str, Any]:
    return {"enabled": bool(request.get("debug", False)), "node_events": []}


def _append_event(state: RouteGraphState, node_name: str) -> dict[str, Any]:
    trace = dict(state.get("trace", {"enabled": False, "node_events": []}))
    if trace.get("enabled"):
        events = list(trace.get("node_events", []))
        events.append({"node": node_name})
        trace["node_events"] = events
    return trace
