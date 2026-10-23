"""FaultDx Route A/B/C CLI for unified answer assembly.

Usage examples:
    python scripts/cli_route_abc.py --route a --query "M07 station alarm"
    python scripts/cli_route_abc.py --route b --query "TCP IPv4 IP address settings"
    python scripts/cli_route_abc.py --fixture route_b --fixture-id RB-SAFE-001
    python scripts/cli_route_abc.py --fixture route_c --fixture-id RC-SAFE-001
    python scripts/cli_route_abc.py --list-query-bank route_b
    python scripts/cli_route_abc.py --route b --query-id RB-QB-001 --provider stub --out tmp/b.json
    python scripts/cli_route_abc.py --route b --query-id RB-QB-001 --render-only

This CLI is the official Route A/B/C local smoke/debug harness. It is not a
business-layer dependency for UI/API code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

for _stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

for _var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_var, None)
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from services.providers.llm import build_provider
from services.eval.route_abc_cli_contract import (
    DEFAULT_JSON_OUTPUT_PATH,
    FIXTURE_PATHS,
    QUERY_BANK_PATHS,
    ROUTE_TO_QUERY_BANK,
    route_default_sources,
)
from services.reasoning.route_graph import RESULT_CONTRACT_VERSION, run_route_graph, run_route_graph_dry_run
from services.reasoning.unified_answer_assembler import fixture_route_output, synthesize_route_output
from services.routing.query_router import (
    CASE_RETRIEVAL,
    DOCUMENT_EVIDENCE_RETRIEVAL,
    INTENT_CASE_LIKE,
    INTENT_DOCUMENT_PROCEDURE,
    RoutingContext,
)


OUT_PATH = DEFAULT_JSON_OUTPUT_PATH
FIXTURES = FIXTURE_PATHS
QUERY_BANKS = QUERY_BANK_PATHS


def main() -> None:
    args = _parse_args()
    if args.list_query_bank:
        _list_query_bank(args.list_query_bank)
        return

    provider = build_provider(_provider_config(args))

    if args.fixture:
        result = _run_fixture(args.fixture, args.fixture_id, args.fixture_index, provider)
        _emit_result(result, args)
        return

    if args.query_id:
        result = _run_query_bank(args.route, args.query_id, provider)
        _emit_result(result, args)
        return

    if args.query:
        result = _run_route(args.route, args.query, provider)
        _emit_result(result, args)
        return

    _interactive(provider, args)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FaultDx Route A/B/C unified assembly CLI")
    parser.add_argument("--route", choices=("a", "b", "c"), default="b")
    parser.add_argument("--query", help="Run one query and exit.")
    parser.add_argument("--query-id", help="Run one query-bank case by ID, such as RB-QB-001.")
    parser.add_argument("--list-query-bank", choices=tuple(QUERY_BANKS), help="List query-bank cases and exit.")
    parser.add_argument("--fixture", choices=tuple(FIXTURES), help="Run one serving-safe fixture and exit.")
    parser.add_argument("--fixture-id", help="Fixture ID, such as RB-SAFE-001.")
    parser.add_argument("--fixture-index", type=int, default=0, help="Zero-based fixture index when --fixture-id is omitted.")
    parser.add_argument("--provider", choices=("stub", "ollama", "company_api"), help="Override FAULTDX_PROVIDER_TYPE.")
    parser.add_argument("--model", help="Override FAULTDX_OLLAMA_MODEL for Ollama.")
    parser.add_argument("--endpoint", help="Override FAULTDX_OLLAMA_ENDPOINT for Ollama.")
    parser.add_argument("--out", type=Path, default=OUT_PATH, help="Output JSON path. Defaults to synthesis_out_abc.json.")
    parser.add_argument("--answer-out", type=Path, help="Optional path for rendered answer text.")
    parser.add_argument("--render-only", action="store_true", help="Print rendered answer only; still saves JSON unless --no-save is set.")
    parser.add_argument("--no-save", action="store_true", help="Do not save JSON output.")
    return parser.parse_args()


def _provider_config(args: argparse.Namespace) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if args.provider:
        config["type"] = args.provider
        os.environ["FAULTDX_PROVIDER_TYPE"] = args.provider
    ollama: dict[str, Any] = {}
    if args.model:
        ollama["model"] = args.model
        os.environ["FAULTDX_OLLAMA_MODEL"] = args.model
    if args.endpoint:
        ollama["endpoint"] = args.endpoint
        os.environ["FAULTDX_OLLAMA_ENDPOINT"] = args.endpoint
    if ollama:
        config["ollama"] = ollama
    return config


def _interactive(provider: Any, args: argparse.Namespace) -> None:
    print("FaultDx Route A/B/C CLI. Type exit to quit.")
    print(f"Provider: {getattr(provider, 'provider_type', 'unknown')} / {getattr(provider, 'model', '')}")
    while True:
        route = input("route [a/b/c] > ").strip().lower() or "b"
        if route in {"exit", "quit", "q"}:
            break
        if route not in {"a", "b", "c"}:
            print("Use route a, b, or c.")
            continue
        query = input("query > ").strip()
        if not query:
            continue
        result = _run_route(route, query, provider)
        _emit_result(result, args)


def _run_route(route: str, query: str, provider: Any) -> dict[str, Any]:
    request: dict[str, Any] = {"query_text": query, "_provider": provider}
    routing_context = None
    if route == "a":
        available_sources = route_default_sources("a")
        request["available_sources"] = list(available_sources)
        routing_context = RoutingContext(available_sources=available_sources)
        state = run_route_graph(request, routing_context=routing_context)
        return state.get("api_response", {})
    elif route == "b":
        request["available_sources"] = list(route_default_sources("b"))
        request["query_type_hint"] = INTENT_DOCUMENT_PROCEDURE
    else:
        request["available_sources"] = list(route_default_sources("c"))
        request["query_type_hint"] = INTENT_CASE_LIKE
    state = run_route_graph_dry_run(request, routing_context=routing_context)
    return state.get("api_response", {})


def _run_fixture(
    fixture_name: str,
    fixture_id: str | None,
    fixture_index: int,
    provider: Any,
) -> dict[str, Any]:
    fixture = _load_fixture_case(FIXTURES[fixture_name], fixture_id, fixture_index)
    query = str(fixture.get("input", {}).get("query_text", ""))
    expected = fixture.get("expected", {})
    route = str(expected.get("route") or (
        DOCUMENT_EVIDENCE_RETRIEVAL if fixture_name == "route_b" else CASE_RETRIEVAL
    ))
    route_output = fixture_route_output(fixture)
    conclusion = synthesize_route_output(query, route, route_output, provider=provider)
    return _api_response_from_fixture(query, expected, route_output, conclusion)


def _run_query_bank(route: str, query_id: str, provider: Any) -> dict[str, Any]:
    if route not in ROUTE_TO_QUERY_BANK:
        raise ValueError("--query-id currently supports Route B or Route C only.")
    bank_name = ROUTE_TO_QUERY_BANK[route]
    entry = _load_query_bank_case(QUERY_BANKS[bank_name], query_id)
    entry_route = str(entry.get("route") or "").lower()
    if entry_route and entry_route != route:
        raise ValueError(f"Query {query_id} belongs to route {entry_route}, not route {route}.")

    fixture_name = str(entry.get("fixture") or bank_name)
    fixture_id = str(entry.get("fixture_id") or "")
    fixture = _load_fixture_case(FIXTURES[fixture_name], fixture_id, 0)
    query = str(entry.get("query_text") or fixture.get("input", {}).get("query_text", ""))
    expected = fixture.get("expected", {})
    route_name = str(expected.get("route") or (
        DOCUMENT_EVIDENCE_RETRIEVAL if fixture_name == "route_b" else CASE_RETRIEVAL
    ))
    route_output = fixture_route_output(fixture)
    conclusion = synthesize_route_output(query, route_name, route_output, provider=provider)
    return _api_response_from_fixture(query, expected, route_output, conclusion)


def _load_fixture_case(path: Path, fixture_id: str | None, fixture_index: int) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fixtures = payload.get("fixtures", [])
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError(f"No fixtures found in {path}")
    if fixture_id:
        for item in fixtures:
            if isinstance(item, Mapping) and item.get("fixture_id") == fixture_id:
                return item
        raise ValueError(f"Fixture ID not found: {fixture_id}")
    return fixtures[fixture_index]


def _load_query_bank_case(path: Path, query_id: str) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    queries = payload.get("queries", [])
    if not isinstance(queries, list) or not queries:
        raise ValueError(f"No query-bank cases found in {path}")
    for item in queries:
        if isinstance(item, Mapping) and item.get("query_id") == query_id:
            return item
    raise ValueError(f"Query ID not found: {query_id}")


def _list_query_bank(bank_name: str) -> None:
    path = QUERY_BANKS[bank_name]
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(f"{bank_name}: {path.relative_to(REPO_ROOT)}")
    for item in payload.get("queries", []):
        if not isinstance(item, Mapping):
            continue
        print(
            f"{item.get('query_id')}\t{item.get('scenario')}\t"
            f"{item.get('fixture_id')}\t{item.get('query_text')}"
        )


def _api_response_from_fixture(
    query: str,
    expected: Mapping[str, Any],
    route_output: Mapping[str, Any],
    conclusion: Mapping[str, Any],
) -> dict[str, Any]:
    route_family = str(expected.get("route_family") or "fallback")
    route = str(expected.get("route") or "insufficient_context")
    answer_type = str(expected.get("answer_type") or "insufficient_context")
    status = str(expected.get("status") or "not_available")
    return {
        "contract_version": RESULT_CONTRACT_VERSION,
        "query": {
            "text": query,
            "normalized_text": query,
            "language": "en",
            "received_at": "2026-05-20T00:00:00+08:00",
        },
        "decision": {
            "route_family": route_family,
            "route": route,
            "answer_type": answer_type,
            "status": status,
            "requires_review": False,
        },
        "entities": _empty_entities(query),
        "knowledge_context": {"used_sources": list(route_output.get("used_sources") or [])},
        "summary": dict(conclusion.get("summary") or {}),
        "diagnosis_results": _api_results(conclusion.get("diagnosis_results"), route, answer_type, status),
        "root_cause": str(conclusion.get("root_cause") or ""),
        "root_cause_actions": [],
    }


def _api_results(raw_results: Any, route: str, result_type: str, status: str) -> list[dict[str, Any]]:
    if not isinstance(raw_results, list):
        return []
    items: list[dict[str, Any]] = []
    for rank, raw in enumerate(raw_results, start=1):
        if not isinstance(raw, Mapping):
            continue
        items.append(
            {
                "rank": rank,
                "title": str(raw.get("title") or ""),
                "possible_cause": raw.get("possible_cause"),
                "result_type": result_type,
                "status": status,
                "confidence": _confidence(str(raw.get("confidence") or "unknown")),
                "description": str(raw.get("description") or ""),
                "evidence": _api_evidence(raw.get("evidence"), route),
                "actions": _api_actions(raw.get("actions"), status),
            }
        )
    return items


def _api_evidence(raw_evidence: Any, route: str) -> list[dict[str, Any]]:
    source_type = "serving_document" if route == DOCUMENT_EVIDENCE_RETRIEVAL else "structured_case_candidate"
    evidence_type = "document_snippet" if route == DOCUMENT_EVIDENCE_RETRIEVAL else "related_case"
    if not isinstance(raw_evidence, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in raw_evidence:
        if not isinstance(raw, Mapping):
            continue
        source_id = str(raw.get("source_id") or "")
        items.append(
            {
                "evidence_type": evidence_type,
                "source_type": source_type,
                "source_name": str(raw.get("source_name") or source_type),
                "source_id": source_id,
                "anchor": raw.get("anchor") or source_id or None,
                "reviewed": False,
                "serving_safe": True,
                "summary": str(raw.get("summary") or ""),
            }
        )
    return items


def _api_actions(raw_actions: Any, status: str) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list):
        return []
    source_status = "evidence_supported" if status == "evidence_only" else "candidate_supported"
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_actions, start=1):
        if not isinstance(raw, Mapping):
            continue
        action = str(raw.get("action") or "")
        if not action:
            continue
        items.append({"step": int(raw.get("step") or index), "action": action, "source_status": source_status})
    return items


def _empty_entities(query: str) -> dict[str, Any]:
    slot = {"raw": None, "canonical": None, "confidence": "unknown"}
    return {
        "asset": {"station": dict(slot), "module": dict(slot), "component": dict(slot)},
        "diagnostic": {"error_code": dict(slot), "fault": dict(slot), "cause": dict(slot), "action": dict(slot)},
        "observation": {
            "phenomenon_text": {"raw": query, "canonical": query, "confidence": "low", "normalized_tokens": []},
            "time_context": dict(slot),
        },
    }


def _confidence(value: str) -> str:
    return value if value in {"high", "medium", "low", "unknown"} else "unknown"


def _emit_result(result: Mapping[str, Any], args: argparse.Namespace) -> None:
    rendered = _render_answer(result)
    print(rendered)
    if args.answer_out:
        _save_text(rendered, args.answer_out)
    if not args.render_only:
        print("=" * 72)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.no_save:
        _save(result, args.out)


def _render_answer(result: Mapping[str, Any]) -> str:
    decision = result.get("decision", {})
    summary = result.get("summary", {})
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("FaultDx Route ABC 答案")
    lines.append(f"路由：{decision.get('route_family')} / {decision.get('route')}")
    lines.append(f"类型：{decision.get('answer_type')} / {decision.get('status')}")
    headline = str(summary.get("headline") or "").strip()
    safe_summary = str(summary.get("user_safe_summary") or "").strip()
    if headline:
        lines.append("")
        lines.append(headline)
    if safe_summary:
        lines.append(safe_summary)
    root_cause = str(result.get("root_cause") or "").strip()
    if root_cause:
        lines.append("")
        lines.append(f"根因边界：{root_cause}")

    results = result.get("diagnosis_results", [])
    if not isinstance(results, list) or not results:
        lines.append("")
        lines.append("当前路由未组装到 serving-safe 结果。")
    else:
        lines.append("")
        lines.append("结果")
        lines.append("-" * 72)
        for item in results:
            if not isinstance(item, Mapping):
                continue
            lines.append(
                f"[{item.get('rank')}] {item.get('title')} "
                f"({item.get('result_type')} / {item.get('status')})"
            )
            description = str(item.get("description") or "").strip()
            if description:
                lines.append(description)
            evidence = item.get("evidence", [])
            if isinstance(evidence, list) and evidence:
                lines.append("证据")
                for ev in evidence:
                    if not isinstance(ev, Mapping):
                        continue
                    source_type = ev.get("source_type")
                    source_id = ev.get("source_id")
                    anchor = ev.get("anchor")
                    lines.append(f"- {source_type}: {source_id} 锚点={anchor}")
            actions = item.get("actions", [])
            if isinstance(actions, list) and actions:
                lines.append("动作")
                for act in actions:
                    if not isinstance(act, Mapping):
                        continue
                    lines.append(f"- {act.get('step')}. {act.get('action')} [{act.get('source_status')}]")
            lines.append("-" * 72)
    lines.append("=" * 72)
    return "\n".join(lines)


def _save(result: Mapping[str, Any], out_path: Path) -> None:
    path = out_path if out_path.is_absolute() else REPO_ROOT / out_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {path}")


def _save_text(text: str, out_path: Path) -> None:
    path = out_path if out_path.is_absolute() else REPO_ROOT / out_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    print(f"answer saved: {path}")


if __name__ == "__main__":
    t0 = time.perf_counter()
    try:
        main()
    finally:
        if len(sys.argv) > 1:
            print(f"elapsed: {time.perf_counter() - t0:.1f}s")
