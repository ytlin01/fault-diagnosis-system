"""Route A E2E smoke — requires live Neo4j connection.

Three executor-level cases (no LLM) + one full-pipeline case (1 LLM call).

Usage:
    python scripts/run_eval/run_route_a_e2e_smoke.py
    python scripts/run_eval/run_route_a_e2e_smoke.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

for _var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_var, None)
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

from dotenv import load_dotenv

load_dotenv()

from services.canonicalization.prekg import canonicalize_query
from services.reasoning.route_graph import run_route_graph
from services.retrieval.route_a_executor import execute_route_a
from services.routing.query_router import (
    REVIEWED_DIAGNOSTIC_CHAIN,
    ROUTE_A_STRUCTURED,
    RoutingContext,
)

_ROUTING_CONTEXT = RoutingContext(
    available_sources=("reviewed_diagnostic_chain_v1",),
)

# Known-good EC with a full Fault→Cause→Action→Step chain in the KG.
_EC_HIT = "M03CVMA-02-03"
# EC that matches the EC regex but does not exist in the KG.
_EC_NO_HIT = "Z99XXXXX-99-99"

_API_REQUIRED_KEYS = frozenset({
    "contract_version", "query", "decision", "entities",
    "knowledge_context", "summary", "diagnosis_results", "root_cause",
})


@dataclass(frozen=True)
class SmokeResult:
    case_id: str
    passed: bool
    errors: tuple[str, ...]
    observed: dict[str, Any]


# ── Executor helpers ──────────────────────────────────────────────────────────

def _executor_output(ec_query: str) -> dict[str, Any]:
    canonical = canonicalize_query(ec_query).as_dict()
    return execute_route_a(
        canonical,
        route=REVIEWED_DIAGNOSTIC_CHAIN,
        allowed_sources=["reviewed_diagnostic_chain_v1"],
    )


# ── Executor-level cases (Neo4j only, no LLM) ────────────────────────────────

def _case_executor_ec_hit_returns_items() -> SmokeResult:
    output = _executor_output(f"{_EC_HIT} 报警是什么意思？")
    observed = {
        "items_count": len(output.get("items", [])),
        "warnings": output.get("warnings", []),
    }
    return _check(
        "executor_ec_hit_returns_items",
        observed,
        (
            lambda: _expect_gt(observed["items_count"], 0, "items_count"),
            lambda: _expect_equal(observed["warnings"], [], "warnings"),
        ),
    )


def _case_executor_ec_no_hit_warning() -> SmokeResult:
    output = _executor_output(f"{_EC_NO_HIT} 是什么意思？")
    observed = {
        "items_count": len(output.get("items", [])),
        "warnings_count": len(output.get("warnings", [])),
    }
    return _check(
        "executor_ec_no_hit_warning",
        observed,
        (
            lambda: _expect_equal(observed["items_count"], 0, "items_count"),
            lambda: _expect_gt(observed["warnings_count"], 0, "warnings_count"),
        ),
    )


def _case_executor_chain_completeness() -> SmokeResult:
    """At least one KG item for the hit EC must carry fault+cause+action+steps."""
    output = _executor_output(f"{_EC_HIT} 报警是什么意思？")
    items = output.get("items", [])
    has_full_chain = any(
        item.get("fault") and item.get("cause") and item.get("action") and item.get("steps")
        for item in items
    )
    observed = {
        "items_count": len(items),
        "has_full_chain": has_full_chain,
        "first_item_keys": sorted(items[0].keys()) if items else [],
    }
    return _check(
        "executor_chain_completeness",
        observed,
        (
            lambda: _expect_gt(observed["items_count"], 0, "items_count"),
            lambda: _expect_truthy(observed["has_full_chain"], "has_full_chain (fault+cause+action+steps)"),
        ),
    )


# ── Full-pipeline case (1 LLM call) ──────────────────────────────────────────

def _case_pipeline_full() -> SmokeResult:
    """Route dispatch + API schema + synthesizer graceful — one LLM call."""
    state = run_route_graph(
        {"query_text": f"{_EC_HIT} 报警是什么意思？"},
        routing_context=_ROUTING_CONTEXT,
    )
    api = state.get("api_response", {})
    decision = api.get("decision", {})
    ec_canonical = (
        api.get("entities", {})
        .get("diagnostic", {})
        .get("error_code", {})
        .get("canonical")
    )
    route_output = state.get("route_output", {})
    conclusion = route_output.get("diagnosis_conclusion")
    missing_keys = sorted(_API_REQUIRED_KEYS - set(api.keys()))

    observed = {
        "route_family": decision.get("route_family"),
        "route": decision.get("route"),
        "ec_canonical": ec_canonical,
        "missing_api_keys": missing_keys,
        "conclusion_type": type(conclusion).__name__,
        "conclusion_has_warnings_key": isinstance(conclusion, dict) and "warnings" in conclusion,
    }
    return _check(
        "pipeline_full",
        observed,
        (
            lambda: _expect_equal(observed["route_family"], ROUTE_A_STRUCTURED, "route_family"),
            lambda: _expect_equal(observed["route"], REVIEWED_DIAGNOSTIC_CHAIN, "route"),
            lambda: _expect_equal(observed["ec_canonical"], _EC_HIT, "ec_canonical"),
            lambda: _expect_equal(observed["missing_api_keys"], [], "missing_api_keys"),
            lambda: _expect_equal(observed["conclusion_type"], "dict", "conclusion_type"),
            lambda: _expect_truthy(observed["conclusion_has_warnings_key"], "conclusion_has_warnings_key"),
        ),
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def evaluate_cases() -> list[SmokeResult]:
    return [
        _case_executor_ec_hit_returns_items(),
        _case_executor_ec_no_hit_warning(),
        _case_executor_chain_completeness(),
        _case_pipeline_full(),
    ]


def summarize(results: list[SmokeResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
    }


# ── Assertion helpers ─────────────────────────────────────────────────────────

def _check(
    case_id: str,
    observed: dict[str, Any],
    checks: tuple[Callable[[], str | None], ...],
) -> SmokeResult:
    errors = tuple(e for check in checks if (e := check()))
    return SmokeResult(case_id=case_id, passed=not errors, errors=errors, observed=observed)


def _expect_equal(actual: Any, expected: Any, field: str) -> str | None:
    return None if actual == expected else f"{field}: expected {expected!r}, got {actual!r}"


def _expect_gt(actual: Any, threshold: Any, field: str) -> str | None:
    return None if actual > threshold else f"{field}: expected > {threshold}, got {actual!r}"


def _expect_truthy(actual: Any, field: str) -> str | None:
    return None if actual else f"{field}: expected truthy, got {actual!r}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Route A E2E smoke — requires live Neo4j and Ollama."
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    args = parser.parse_args(argv)

    results = evaluate_cases()
    summary = summarize(results)
    failures = [
        {"case_id": r.case_id, "errors": list(r.errors), "observed": r.observed}
        for r in results
        if not r.passed
    ]

    if args.json:
        payload = {
            "schema_version": "route_a_e2e_smoke_v0",
            "summary": summary,
            "failures": failures,
            "results": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "errors": list(r.errors),
                    "observed": r.observed,
                }
                for r in results
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Route A E2E smoke: {summary['passed']}/{summary['total']} passed")
        for failure in failures:
            print(f"\n  FAIL  {failure['case_id']}")
            for error in failure["errors"]:
                print(f"    - {error}")
        if summary["failed"] == 0:
            print("  All cases passed.")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
