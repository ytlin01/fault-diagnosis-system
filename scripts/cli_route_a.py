"""Route A CLI — full pipeline: QueryRouter → text2cypher → Neo4j → synthesize → assemble.

Usage:
    python scripts/cli_route_a.py

Type 'exit' or press Ctrl-C to quit.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding before any output.
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# Bypass system proxy for localhost Ollama calls.
for _var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_var, None)
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from services.providers.llm import build_provider
from services.reasoning.route_graph import run_route_graph
from services.routing.query_router import RoutingContext, REVIEWED_DIAGNOSTIC_CHAIN

# ---------------------------------------------------------------------------
# Static KG facts mode (kept for isolated synthesizer testing without Neo4j)
#
# from services.reasoning.diagnosis_synthesizer import synthesize
#
# _DEFAULT_KG = Path(__file__).resolve().parent.parent / "data/eval/text2cypher/kg_facts_sample_full_chain.json"
#
# def _run_static(query: str, kg_facts: dict, provider) -> dict:
#     return synthesize(query, kg_facts, "route_a", provider=provider)
#
# Usage: load kg_facts from file, call _run_static(query, kg_facts, provider)
# ---------------------------------------------------------------------------

_ROUTING_CONTEXT = RoutingContext(
    available_sources=("reviewed_diagnostic_chain_v1",),
)

_OUT_PATH = Path(__file__).resolve().parent.parent / "synthesis_out.json"

_W = 62  # display width


def _hr(char: str = "─") -> str:
    return char * _W


def _render(result: dict) -> str:
    lines: list[str] = []

    # ── Summary ──────────────────────────────────────────────
    summary = result.get("summary", {})
    headline = summary.get("headline", "")
    user_summary = summary.get("user_safe_summary", "")

    lines.append(_hr("═"))
    if headline:
        lines.append(f"  {headline}")
    if user_summary:
        lines.append(f"  {user_summary}")

    root_cause_top = result.get("root_cause", "")
    if root_cause_top:
        lines.append("")
        lines.append(f"  根本原因：{root_cause_top}")

    root_cause_actions = result.get("root_cause_actions", [])
    if root_cause_actions:
        lines.append("")
        lines.append("  修复步骤：")
        for act in root_cause_actions:
            lines.append(f"    {act.get('step', '?')}. {act.get('action', '')}")

    lines.append(_hr("═"))

    # ── Diagnosis results ─────────────────────────────────────
    results = result.get("diagnosis_results", [])
    total = len(results)

    if not results:
        lines.append("  无诊断结论（KG 数据不足或 LLM 调用失败）")
    else:
        for i, dr in enumerate(results, 1):
            title = dr.get("title", "")
            lines.append("")
            lines.append(f"  [{i}/{total}]  {title}")
            lines.append(_hr())

            possible_cause = dr.get("possible_cause")
            if possible_cause:
                lines.append(f"  可能原因：{possible_cause}")
                lines.append("")

            description = dr.get("description", "")
            if description:
                lines.append(f"  {description}")
                lines.append("")

            evidence = dr.get("evidence", [])
            if evidence:
                lines.append("  证据来源：")
                for ev in evidence:
                    name = ev.get("source_name", "")
                    sid = ev.get("source_id", "")
                    lines.append(f"    · {name}  ({sid})")

    # ── Warnings ──────────────────────────────────────────────
    warnings = result.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append(_hr())
        for w in warnings:
            lines.append(f"  ⚠  {w}")

    lines.append("")
    return "\n".join(lines)


def _run(query: str, provider) -> dict:
    state = run_route_graph(
        {"query_text": query, "_provider": provider},
        routing_context=_ROUTING_CONTEXT,
    )
    return state.get("api_response", {})


def _save(result: dict) -> None:
    _OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [saved → {_OUT_PATH.name}]")


def main() -> None:
    provider = build_provider()

    print(_hr("═"))
    print("  FaultDx Route A CLI  （全链路：QueryRouter → Neo4j → LLM）")
    print(f"  模型：{getattr(provider, 'model', provider.provider_type)}")
    print(_hr("═"))
    print("  输入诊断问题，回车提交。输入 exit 退出。")
    print()

    while True:
        try:
            query = input("  问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  再见。")
            break

        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            print("  再见。")
            break

        print()
        print("  正在推理中……")
        print()

        _t0 = time.perf_counter()
        try:
            result = _run(query, provider)
        except Exception as exc:
            print(f"  [ERROR] {exc}", file=sys.stderr)
            continue
        _elapsed = time.perf_counter() - _t0

        print(_render(result))
        print(f"  推理耗时：{_elapsed:.1f}s")

        print(_hr("─"))
        print("  结构化输出（JSON）")
        print(_hr("─"))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()

        _save(result)


if __name__ == "__main__":
    main()
