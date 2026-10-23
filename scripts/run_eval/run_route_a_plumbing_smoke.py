from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.reasoning.route_graph import route_a_structured_slot, run_route_graph_dry_run
from services.routing.query_router import (
    FP_REVIEW_GOVERNANCE,
    REVIEWED_DIAGNOSTIC_CHAIN,
    ROUTE_A_STRUCTURED,
    ROUTE_C_CASE_GOVERNANCE,
    STRUCTURED_CATALOG,
    RoutingContext,
)


@dataclass(frozen=True)
class SmokeResult:
    case_id: str
    passed: bool
    errors: tuple[str, ...]
    observed: dict[str, Any]


def evaluate_cases() -> list[SmokeResult]:
    return [
        _case_guard_blocks_forced_route_a_without_allowed_source(),
        _case_reviewed_source_reaches_route_a_executor(),
        _case_catalog_fallback_does_not_enter_route_a(),
        _case_review_candidate_does_not_enter_route_a(),
    ]


def summarize(results: list[SmokeResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
    }


def _case_guard_blocks_forced_route_a_without_allowed_source() -> SmokeResult:
    output = route_a_structured_slot(
        {
            "routing_decision": {
                "route_family": ROUTE_A_STRUCTURED,
                "route": REVIEWED_DIAGNOSTIC_CHAIN,
                "intent": "fault_phenomenon",
                "reason": "route-a plumbing smoke forced guarded slot",
                "allowed_sources": [],
                "blocked_sources": [],
                "requires_review": False,
                "kg_eligible": True,
                "confidence": "high",
            },
            "trace": {"enabled": False, "node_events": []},
        }
    )
    route_output = output["route_output"]
    observed = {
        "items": len(route_output.get("items", [])),
        "used_sources": route_output.get("used_sources", []),
        "warnings": route_output.get("warnings", []),
    }
    return _check(
        "guard_blocks_forced_route_a_without_allowed_source",
        observed,
        (
            lambda: _expect_equal(observed["items"], 0, "items"),
            lambda: _expect_equal(observed["used_sources"], [], "used_sources"),
            lambda: _expect_contains(observed["warnings"], "guarded", "warnings"),
        ),
    )


def _case_reviewed_source_reaches_route_a_executor() -> SmokeResult:
    state = run_route_graph_dry_run(
        {
            "query_text": "What does M07LOM1-01-03 mean?",
            "available_sources": ["reviewed_diagnostic_chain_v1"],
        },
        routing_context=RoutingContext(reviewed_diagnostic_chain_available=True),
    )
    decision = state["api_response"]["decision"]
    route_output = state["route_output"]
    observed = {
        "route_family": decision.get("route_family"),
        "route": decision.get("route"),
        "status": decision.get("status"),
        "requires_review": decision.get("requires_review"),
        "diagnosis_results": len(state["api_response"].get("diagnosis_results", [])),
        "used_sources_type": type(
            state["api_response"]["knowledge_context"].get("used_sources")
        ).__name__,
        "warnings": route_output.get("warnings", []),
    }
    return _check(
        "reviewed_source_reaches_route_a_executor",
        observed,
        (
            lambda: _expect_equal(observed["route_family"], ROUTE_A_STRUCTURED, "route_family"),
            lambda: _expect_equal(observed["route"], REVIEWED_DIAGNOSTIC_CHAIN, "route"),
            lambda: _expect_equal(observed["status"], "reviewed", "status"),
            lambda: _expect_equal(observed["requires_review"], False, "requires_review"),
            lambda: _expect_equal(observed["diagnosis_results"], 0, "diagnosis_results"),
            lambda: _expect_equal(observed["used_sources_type"], "list", "used_sources"),
            lambda: _expect_truthy(observed["warnings"], "warnings"),
            lambda: _expect_not_contains(observed["warnings"], "deferred", "warnings"),
        ),
    )


def _case_catalog_fallback_does_not_enter_route_a() -> SmokeResult:
    state = run_route_graph_dry_run(
        {
            "query_text": "What does M07LOM1-01-03 mean?",
            "available_sources": ["error_codes_standardized_serving"],
        }
    )
    decision = state["api_response"]["decision"]
    observed = {
        "route_family": decision.get("route_family"),
        "route": decision.get("route"),
        "status": decision.get("status"),
        "requires_review": decision.get("requires_review"),
    }
    return _check(
        "catalog_fallback_does_not_enter_route_a",
        observed,
        (
            lambda: _expect_equal(observed["route_family"], ROUTE_C_CASE_GOVERNANCE, "route_family"),
            lambda: _expect_equal(observed["route"], STRUCTURED_CATALOG, "route"),
            lambda: _expect_equal(observed["status"], "candidate", "status"),
            lambda: _expect_equal(observed["requires_review"], False, "requires_review"),
        ),
    )


def _case_review_candidate_does_not_enter_route_a() -> SmokeResult:
    state = run_route_graph_dry_run(
        {
            "query_text": "feeder z axis enable failed",
            "available_sources": ["structured_fp_join_v1_baseline"],
        }
    )
    decision = state["api_response"]["decision"]
    observed = {
        "route_family": decision.get("route_family"),
        "route": decision.get("route"),
        "status": decision.get("status"),
        "requires_review": decision.get("requires_review"),
    }
    return _check(
        "review_candidate_does_not_enter_route_a",
        observed,
        (
            lambda: _expect_equal(observed["route_family"], ROUTE_C_CASE_GOVERNANCE, "route_family"),
            lambda: _expect_equal(observed["route"], FP_REVIEW_GOVERNANCE, "route"),
            lambda: _expect_equal(observed["status"], "candidate", "status"),
            lambda: _expect_equal(observed["requires_review"], True, "requires_review"),
        ),
    )


def _check(
    case_id: str,
    observed: dict[str, Any],
    checks: tuple[Callable[[], str | None], ...],
) -> SmokeResult:
    errors = tuple(error for check in checks if (error := check()))
    return SmokeResult(case_id=case_id, passed=not errors, errors=errors, observed=observed)


def _expect_equal(actual: Any, expected: Any, field: str) -> str | None:
    if actual == expected:
        return None
    return f"{field}: expected {expected!r}, got {actual!r}"


def _expect_truthy(actual: Any, field: str) -> str | None:
    if actual:
        return None
    return f"{field}: expected a non-empty value"


def _expect_contains(actual: Any, expected_text: str, field: str) -> str | None:
    text = json.dumps(actual, ensure_ascii=False)
    if expected_text in text:
        return None
    return f"{field}: expected to contain {expected_text!r}, got {actual!r}"


def _expect_not_contains(actual: Any, unexpected_text: str, field: str) -> str | None:
    text = json.dumps(actual, ensure_ascii=False)
    if unexpected_text not in text:
        return None
    return f"{field}: expected not to contain {unexpected_text!r}, got {actual!r}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Route A plumbing smoke checks without claiming diagnosis accuracy."
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    results = evaluate_cases()
    summary = summarize(results)
    failures = [
        {
            "case_id": result.case_id,
            "errors": list(result.errors),
            "observed": result.observed,
        }
        for result in results
        if not result.passed
    ]

    if args.json:
        payload = {
            "schema_version": "route_a_plumbing_smoke_v0",
            "summary": summary,
            "failures": failures,
            "results": [
                {
                    "case_id": result.case_id,
                    "passed": result.passed,
                    "errors": list(result.errors),
                    "observed": result.observed,
                }
                for result in results
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Route A plumbing smoke: {summary['passed']}/{summary['total']} passed")
        for failure in failures:
            print(f"\n{failure['case_id']}")
            for error in failure["errors"]:
                print(f"  - {error}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
