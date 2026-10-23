"""
Smoke test for LLM providers used in FaultDx.

Verifies:
  [Ollama]     qwen2.5:7b  — always runs
  [Anthropic]  claude-haiku-4-5-20251001 — runs only if ANTHROPIC_API_KEY is set

Usage:
    python scripts/smoke_test_llm.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Bypass system proxy for localhost Ollama calls (proxy cannot reach loopback).
for _var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_var, None)
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

PROMPT = "请用一句话回答：什么是故障诊断？"
OLLAMA_MODEL = "qwen2.5:7b"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def _make_ollama_client():
    """Return an ollama.Client with a no-proxy httpx transport.

    Windows system proxy (e.g. Clash/V2Ray on 127.0.0.1:7897) intercepts
    localhost traffic and returns 502. kwargs on ollama.Client pass through
    to httpx.Client, so we inject a proxy-free transport directly.
    """
    import httpx
    import ollama

    host = os.environ.get("FAULTDX_OLLAMA_ENDPOINT", "http://localhost:11434")
    transport = httpx.HTTPTransport(proxy=None)
    return ollama.Client(host=host, transport=transport, timeout=60)


def test_ollama() -> None:
    client = _make_ollama_client()

    print(f"[Ollama] model={OLLAMA_MODEL}")
    print(f"[Ollama] prompt: {PROMPT}")
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": PROMPT}],
    )
    content = response["message"]["content"]
    print(f"[Ollama] response: {content}")
    print("[Ollama] PASS")


def test_anthropic() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your_anthropic_api_key_here":
        print("[Anthropic] ANTHROPIC_API_KEY not set — skipping (expected in dev)")
        return

    import anthropic

    print(f"[Anthropic] model={ANTHROPIC_MODEL}")
    print(f"[Anthropic] prompt: {PROMPT}")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": PROMPT}],
    )
    content = message.content[0].text
    print(f"[Anthropic] response: {content}")
    print("[Anthropic] PASS")


if __name__ == "__main__":
    errors = []

    try:
        test_ollama()
    except Exception as exc:
        print(f"[Ollama] FAIL: {exc}", file=sys.stderr)
        errors.append("ollama")

    print()

    try:
        test_anthropic()
    except Exception as exc:
        print(f"[Anthropic] FAIL: {exc}", file=sys.stderr)
        errors.append("anthropic")

    if errors:
        sys.exit(1)
