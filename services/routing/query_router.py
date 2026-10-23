from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


ROUTE_A_STRUCTURED = "route_a_structured"
ROUTE_B_DOCUMENT = "route_b_document"
ROUTE_C_CASE_GOVERNANCE = "route_c_case_governance"
ROUTE_FALLBACK = "fallback"

STRUCTURED_CATALOG = "structured_catalog"
REVIEWED_DIAGNOSTIC_CHAIN = "reviewed_diagnostic_chain"
UNREVIEWED_DIAGNOSTIC_CHAIN = "unreviewed_diagnostic_chain"
ASSET_STRUCTURED_QUERY = "asset_structured_query"
DOCUMENT_EVIDENCE_RETRIEVAL = "document_evidence_retrieval"
CASE_RETRIEVAL = "case_retrieval"
FP_REVIEW_GOVERNANCE = "fp_review_governance"
INSUFFICIENT_CONTEXT = "insufficient_context"

SERVING_ALLOWED = "serving_allowed"
REVIEW_ONLY = "review_only"
BLOCKED = "blocked"

INTENT_ERROR_CODE = "error_code"
INTENT_FAULT_PHENOMENON = "fault_phenomenon"
INTENT_ASSET = "asset"
INTENT_DOCUMENT_PROCEDURE = "document_procedure"
INTENT_CASE_LIKE = "case_like"
INTENT_MIXED = "mixed"
INTENT_UNKNOWN = "unknown"

_SUPPORTED_HINTS = {
    INTENT_ERROR_CODE,
    INTENT_FAULT_PHENOMENON,
    INTENT_ASSET,
    INTENT_DOCUMENT_PROCEDURE,
    INTENT_CASE_LIKE,
    INTENT_MIXED,
    INTENT_UNKNOWN,
    # Backward-compatible hints from the first TASK-008 draft.
    "symptom",
    "document", 
}


@dataclass(frozen=True)
class SourcePolicy:
    status: str
    reason: str
    allowed_routes: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlockedSource:
    source: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"source": self.source, "reason": self.reason}


@dataclass(frozen=True)
class RoutingRequest:
    query_text: str
    query_type_hint: str | None = None
    available_sources: tuple[str, ...] = ()
    safety_mode: str = "default"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RoutingRequest":
        sources = payload.get("available_sources") or ()
        return cls(
            query_text=str(payload.get("query_text", "")),
            query_type_hint=payload.get("query_type_hint"),
            available_sources=tuple(str(source) for source in sources),
            safety_mode=str(payload.get("safety_mode", "default")),
        )


@dataclass(frozen=True)
class RoutingContext:
    available_sources: tuple[str, ...] = (
        "error_codes_standardized_serving",
        "rag_fp_case_candidates_v1",
        "data/serving_unstructured_vlm",
    )
    source_registry: Mapping[str, SourcePolicy] = field(default_factory=dict)
    reviewed_diagnostic_chain_available: bool = False
    unreviewed_diagnostic_chain_available: bool = False
    asset_structured_source_available: bool = False


@dataclass(frozen=True)
class RoutingDecision:
    route_family: str
    route: str
    intent: str
    reason: str
    allowed_sources: tuple[str, ...] = ()
    blocked_sources: tuple[BlockedSource, ...] = ()
    requires_review: bool = False
    kg_eligible: bool = False
    confidence: str = "low"

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_family": self.route_family,
            "route": self.route,
            "intent": self.intent,
            "reason": self.reason,
            "allowed_sources": list(self.allowed_sources),
            "blocked_sources": [source.as_dict() for source in self.blocked_sources],
            "requires_review": self.requires_review,
            "kg_eligible": self.kg_eligible,
            "confidence": self.confidence,
        }


DEFAULT_SOURCE_REGISTRY: dict[str, SourcePolicy] = {
    "error_codes_standardized_serving": SourcePolicy(
        status=SERVING_ALLOWED,
        allowed_routes=(STRUCTURED_CATALOG,),
        reason="Serving-safe EC catalog is allowed for structured catalog lookup, not full diagnosis.",
    ),
    "structured_error_code_catalog_v1": SourcePolicy(
        status=BLOCKED,
        reason="Deprecated catalog alias. Use `error_codes_standardized_serving` as the Route C structured catalog source.",
    ),
    "reviewed_diagnostic_chain_v1": SourcePolicy(
        status=SERVING_ALLOWED,
        allowed_routes=(REVIEWED_DIAGNOSTIC_CHAIN,),
        reason="Reviewed EC/FP/RC/RA chain can support confirmed structured diagnosis.",
    ),
    "unreviewed_diagnostic_chain_v1": SourcePolicy(
        status=SERVING_ALLOWED,
        allowed_routes=(UNREVIEWED_DIAGNOSTIC_CHAIN,),
        reason="Unreviewed diagnostic chain (validated=false) is allowed for end-to-end pipeline verification only; responses must carry unreviewed warning.",
    ),
    "asset_kg_v1": SourcePolicy(
        status=SERVING_ALLOWED,
        allowed_routes=(ASSET_STRUCTURED_QUERY,),
        reason="Reviewed asset-layer source can support structured asset lookup.",
    ),
    "data/serving_unstructured_vlm": SourcePolicy(
        status=SERVING_ALLOWED,
        allowed_routes=(DOCUMENT_EVIDENCE_RETRIEVAL,),
        reason="Masked serving view is allowed for document evidence retrieval.",
    ),
    "serving_unstructured_vlm": SourcePolicy(
        status=SERVING_ALLOWED,
        allowed_routes=(DOCUMENT_EVIDENCE_RETRIEVAL,),
        reason="Masked serving view is allowed for document evidence retrieval.",
    ),
    "rag_fp_case_candidates_v1": SourcePolicy(
        status=REVIEW_ONLY,
        allowed_routes=(CASE_RETRIEVAL,),
        reason="RAG case candidates are Route C case-retrieval inputs only and must not be treated as governance or confirmed diagnosis.",
    ),
    "structured_fp_join_v1_baseline": SourcePolicy(
        status=REVIEW_ONLY,
        allowed_routes=(FP_REVIEW_GOVERNANCE,),
        reason="V1 baseline is a review baseline and must not be treated as confirmed diagnosis.",
    ),
    "structured_fp_join_v1_semantic": SourcePolicy(
        status=BLOCKED,
        reason="Intermediate semantic aggregate is not an authoritative Route C source. Use `structured_fp_join_v1_baseline` instead.",
    ),
    "data/processed/unstructured_vlm": SourcePolicy(
        status=BLOCKED,
        reason="VLM-enriched canonical data is internal-only and not serving-safe.",
    ),
    "data/processed/unstructured": SourcePolicy(
        status=BLOCKED,
        reason="Unstructured canonical data is internal-only; use serving output instead.",
    ),
    "data/processed/unstructured_masked_vlm": SourcePolicy(
        status=BLOCKED,
        reason="Masked canonical output is for internal review; use serving output for retrieval.",
    ),
    "raw_data": SourcePolicy(
        status=BLOCKED,
        reason="Raw data must not be routed into user-facing query paths.",
    ),
    "graphrag": SourcePolicy(
        status=BLOCKED,
        reason="GraphRAG is a future executor and is not enabled as a v0 route.",
    ),
    "text2cypher_diagnosis": SourcePolicy(
        status=BLOCKED,
        reason="Text2Cypher diagnosis is a future executor and is not enabled as a v0 route.",
    ),
    "llm_free_form_generation": SourcePolicy(
        status=BLOCKED,
        reason="LLM free-form answer generation is outside the deterministic v0 router.",
    ),
    "automatic_tool_execution": SourcePolicy(
        status=BLOCKED,
        reason="Automatic tool execution is outside the deterministic v0 router.",
    ),
}

_ERROR_CODE_PATTERNS = (
    re.compile(r"\b[A-Z]\d{2}[A-Z][A-Z0-9]+-\d{2}(?:-\d{2})?(?![-\d])", re.IGNORECASE),  # W01RBRT-07-03 / M07LOM1-01-03
    re.compile(r"\b[A-Z]\d{5,6}-\d{2}(?![-\d])", re.IGNORECASE),                          # V020441-01
    re.compile(r"\bEC[-_]?\d+(?![-\d])", re.IGNORECASE),
    re.compile(r"\b[A-Z]{1,4}\d{2,}(?:[-_][A-Z0-9]+)+(?![-\d])", re.IGNORECASE),
)

_DOCUMENT_TERMS = (
    "sop",
    "manual",
    "document",
    "procedure",
    "work instruction",
    "操作手册",
    "手册",
    "文档",
    "文件",
    "规程",
    "sop里",
)

_CASE_TERMS = (
    "case",
    "similar case",
    "history",
    "historical",
    "downtime",
    "类似案例",
    "历史案例",
    "历史记录",
    "停机案例",
    "停机",
)

_FP_TERMS = (
    "fault",
    "failed",
    "failure",
    "fail",
    "alarm",
    "abnormal",
    "enable failed",
    "怎么处理",
    "如何处理",
    "怎么修",
    "维修",
    "故障",
    "异常",
    "报警",
    "失败",
    "失效",
    "使能",
    "无料",
    "卡料",
)

_ASSET_TERMS = (
    "station",
    "module",
    "component",
    "sub-component",
    "subcomponent",
    "工站",
    "模组",
    "模块",
    "部件",
    "组件",
    "子部件",
)

_ASSET_QUERY_TERMS = (
    "where",
    "which",
    "belongs",
    "located",
    "hierarchy",
    "在哪",
    "哪个",
    "属于",
    "层级",
    "位置",
)


def route_query(
    request: RoutingRequest | Mapping[str, Any],
    context: RoutingContext | None = None,
) -> RoutingDecision:
    request = request if isinstance(request, RoutingRequest) else RoutingRequest.from_mapping(request)
    context = context or RoutingContext()
    intent = classify_intent(request)

    if intent == INTENT_ERROR_CODE:
        return _route_error_code(request, context, intent)
    if intent == INTENT_FAULT_PHENOMENON:
        return _route_fault_phenomenon(request, context, intent)
    if intent == INTENT_ASSET:
        return _route_asset_query(request, context, intent)
    if intent == INTENT_DOCUMENT_PROCEDURE:
        return _route_document_query(request, context, intent)
    if intent == INTENT_CASE_LIKE:
        return _route_case_query(request, context, intent)

    return _decision(
        request=request,
        context=context,
        route_family=ROUTE_FALLBACK,
        route=INSUFFICIENT_CONTEXT,
        intent=intent,
        reason="Query is too short, ambiguous, or outside the deterministic v0 routing policy.",
        confidence="low",
    )


def classify_intent(request: RoutingRequest) -> str:
    hint = (request.query_type_hint or "").strip().lower()
    if hint in _SUPPORTED_HINTS:
        if hint == "symptom":
            return INTENT_FAULT_PHENOMENON
        if hint == "document":
            return INTENT_DOCUMENT_PROCEDURE
        return hint

    query = _normalize_query(request.query_text)
    if not query:
        return INTENT_UNKNOWN

    if _looks_like_error_code(query):
        return INTENT_ERROR_CODE
    if _contains_any(query, _DOCUMENT_TERMS):
        return INTENT_DOCUMENT_PROCEDURE
    if _contains_any(query, _CASE_TERMS):
        return INTENT_CASE_LIKE
    if _contains_any(query, _FP_TERMS):
        return INTENT_FAULT_PHENOMENON
    if _contains_any(query, _ASSET_TERMS) and _contains_any(query, _ASSET_QUERY_TERMS):
        return INTENT_ASSET
    if len(query) < 4:
        return INTENT_UNKNOWN
    return INTENT_UNKNOWN


def _route_error_code(request: RoutingRequest, context: RoutingContext, intent: str) -> RoutingDecision:
    if _reviewed_chain_available(request, context):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_A_STRUCTURED,
            route=REVIEWED_DIAGNOSTIC_CHAIN,
            intent=intent,
            reason="Error-code query can use a reviewed EC/FP/RC/RA diagnostic chain.",
            kg_eligible=True,
            confidence="high",
        )
    if _unreviewed_chain_available(request, context):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_A_STRUCTURED,
            route=UNREVIEWED_DIAGNOSTIC_CHAIN,
            intent=intent,
            reason="Error-code query using unreviewed diagnostic chain (validated=false). Results require human confirmation.",
            requires_review=True,
            kg_eligible=True,
            confidence="medium",
        )
    return _decision(
        request=request,
        context=context,
        route_family=ROUTE_C_CASE_GOVERNANCE,
        route=STRUCTURED_CATALOG,
        intent=intent,
        reason=(
            "Error-code-like query can use catalog fallback, but no reviewed EC/FP/RC/RA "
            "diagnostic chain is available; keep it outside Route A diagnosis."
        ),
        confidence="medium",
    )


def _route_fault_phenomenon(request: RoutingRequest, context: RoutingContext, intent: str) -> RoutingDecision:
    if _reviewed_chain_available(request, context):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_A_STRUCTURED,
            route=REVIEWED_DIAGNOSTIC_CHAIN,
            intent=intent,
            reason="FP query can use a reviewed FP/EC/RC/RA diagnostic chain.",
            kg_eligible=True,
            confidence="high",
        )

    if _has_allowed_source(request, context, CASE_RETRIEVAL):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_C_CASE_GOVERNANCE,
            route=CASE_RETRIEVAL,
            intent=intent,
            reason="FP query prefers Route A, but no reviewed chain is available; related field cases may be useful.",
            requires_review=False,
            confidence="low",
        )

    if _has_allowed_source(request, context, FP_REVIEW_GOVERNANCE):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_C_CASE_GOVERNANCE,
            route=FP_REVIEW_GOVERNANCE,
            intent=intent,
            reason="FP query prefers Route A, but only review-only candidate sources are available.",
            requires_review=True,
            confidence="low",
        )

    return _decision(
        request=request,
        context=context,
        route_family=ROUTE_FALLBACK,
        route=INSUFFICIENT_CONTEXT,
        intent=intent,
        reason="FP query needs a reviewed chain, related cases, or review candidates; none are available.",
        confidence="low",
    )


def _route_asset_query(request: RoutingRequest, context: RoutingContext, intent: str) -> RoutingDecision:
    if context.asset_structured_source_available or _has_allowed_source(request, context, ASSET_STRUCTURED_QUERY):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_A_STRUCTURED,
            route=ASSET_STRUCTURED_QUERY,
            intent=intent,
            reason="Asset query can use a reviewed structured asset-layer source.",
            confidence="medium",
        )
    return _decision(
        request=request,
        context=context,
        route_family=ROUTE_FALLBACK,
        route=INSUFFICIENT_CONTEXT,
        intent=intent,
        reason="Asset query was detected, but no reviewed asset-layer source is available.",
        confidence="low",
    )


def _route_document_query(request: RoutingRequest, context: RoutingContext, intent: str) -> RoutingDecision:
    if _has_allowed_source(request, context, DOCUMENT_EVIDENCE_RETRIEVAL):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_B_DOCUMENT,
            route=DOCUMENT_EVIDENCE_RETRIEVAL,
            intent=intent,
            reason="Document/SOP query can use masked serving-safe document evidence.",
            confidence="medium",
        )
    return _decision(
        request=request,
        context=context,
        route_family=ROUTE_FALLBACK,
        route=INSUFFICIENT_CONTEXT,
        intent=intent,
        reason="Document/SOP query was detected, but no serving-safe document source is available.",
        confidence="low",
    )


def _route_case_query(request: RoutingRequest, context: RoutingContext, intent: str) -> RoutingDecision:
    if _has_allowed_source(request, context, CASE_RETRIEVAL):
        return _decision(
            request=request,
            context=context,
            route_family=ROUTE_C_CASE_GOVERNANCE,
            route=CASE_RETRIEVAL,
            intent=intent,
            reason="Case-like query can use related field case candidates without treating them as confirmed diagnosis.",
            confidence="medium",
        )
    return _decision(
        request=request,
        context=context,
        route_family=ROUTE_FALLBACK,
        route=INSUFFICIENT_CONTEXT,
        intent=intent,
        reason="Case-like query was detected, but no related-case source is available.",
        confidence="low",
    )


def _decision(
    *,
    request: RoutingRequest,
    context: RoutingContext,
    route_family: str,
    route: str,
    intent: str,
    reason: str,
    requires_review: bool = False,
    kg_eligible: bool = False,
    confidence: str = "low",
) -> RoutingDecision:
    allowed_sources, blocked_sources = _classify_sources_for_route(request, context, route)
    return RoutingDecision(
        route_family=route_family,
        route=route,
        intent=intent,
        reason=reason,
        allowed_sources=tuple(allowed_sources),
        blocked_sources=tuple(blocked_sources),
        requires_review=requires_review,
        kg_eligible=kg_eligible,
        confidence=confidence,
    )


def _classify_sources_for_route(
    request: RoutingRequest,
    context: RoutingContext,
    route: str,
) -> tuple[list[str], list[BlockedSource]]:
    registry = _source_registry(context)
    allowed: list[str] = []
    blocked: list[BlockedSource] = []

    for source in _available_sources(request, context):
        policy = _policy_for_source(source, registry)
        if policy.status == BLOCKED:
            blocked.append(BlockedSource(source=source, reason=policy.reason))
            continue
        if route in policy.allowed_routes:
            allowed.append(source)
            continue
        if policy.status == REVIEW_ONLY:
            blocked.append(
                BlockedSource(
                    source=source,
                    reason=f"{policy.reason} It is not allowed for route `{route}`.",
                )
            )
        else:
            blocked.append(
                BlockedSource(
                    source=source,
                    reason=f"Source is not registered as allowed for route `{route}`.",
                )
            )

    return allowed, blocked


def _has_allowed_source(request: RoutingRequest, context: RoutingContext, route: str) -> bool:
    allowed, _ = _classify_sources_for_route(request, context, route)
    return bool(allowed)


def _reviewed_chain_available(request: RoutingRequest, context: RoutingContext) -> bool:
    return context.reviewed_diagnostic_chain_available or _has_allowed_source(
        request,
        context,
        REVIEWED_DIAGNOSTIC_CHAIN,
    )


def _unreviewed_chain_available(request: RoutingRequest, context: RoutingContext) -> bool:
    return context.unreviewed_diagnostic_chain_available or _has_allowed_source(
        request,
        context,
        UNREVIEWED_DIAGNOSTIC_CHAIN,
    )


def _available_sources(request: RoutingRequest, context: RoutingContext) -> tuple[str, ...]:
    return request.available_sources or context.available_sources


def _source_registry(context: RoutingContext) -> dict[str, SourcePolicy]:
    registry = dict(DEFAULT_SOURCE_REGISTRY)
    registry.update(context.source_registry)
    return registry


def _policy_for_source(source: str, registry: Mapping[str, SourcePolicy]) -> SourcePolicy:
    if source in registry:
        return registry[source]

    normalized = source.replace("\\", "/").lower()
    if normalized.startswith("data/raw"):
        return SourcePolicy(status=BLOCKED, reason="Raw data must not be routed into user-facing query paths.")
    if normalized.startswith("data/processed/unstructured_vlm"):
        return SourcePolicy(status=BLOCKED, reason="VLM-enriched canonical data is internal-only and not serving-safe.")
    if "response_text" in normalized or "raw_response" in normalized:
        return SourcePolicy(status=BLOCKED, reason="Raw VLM response content must not directly enter retrieval answers.")
    if normalized.startswith("data/processed/"):
        return SourcePolicy(status=BLOCKED, reason="Processed canonical source is not serving-safe unless explicitly registered.")
    return SourcePolicy(status=BLOCKED, reason="Unknown source is not allowed by the v0 source safety registry.")


def _normalize_query(query_text: str) -> str:
    return " ".join(query_text.strip().lower().split())


def _looks_like_error_code(query: str) -> bool:
    return any(pattern.search(query) for pattern in _ERROR_CODE_PATTERNS)


def _contains_any(query: str, terms: tuple[str, ...]) -> bool:
    return any(term in query for term in terms)
