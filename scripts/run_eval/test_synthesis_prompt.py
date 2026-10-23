"""Quick end-to-end test for diagnosis_synthesis.txt prompt.

Loads the kg_facts sample, calls synthesize() with the real Ollama provider,
and prints the result. Use this to iterate on the prompt.

Usage:
    python scripts/test_synthesis_prompt.py
"""

import json
import os
import sys
from pathlib import Path

# Bypass system proxy before any imports that open HTTP connections.
for _var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_var, None)
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.reasoning.diagnosis_synthesizer import synthesize
from services.providers.llm import build_provider

KG_FACTS_PATH = Path(__file__).parent.parent / "data/eval/text2cypher/kg_facts_sample_full_chain.json"
QUERY = "M03CVMA-02-03 报警是什么意思？怎么处理？"


def main() -> None:
    kg_facts = json.loads(KG_FACTS_PATH.read_text(encoding="utf-8"))
    provider = build_provider()
    print(f"Provider: {provider.provider_type}  model: {getattr(provider, 'model', '-')}\n")
    print(f"Query: {QUERY}\n")
    print("Calling synthesize()...\n")

    result = synthesize(QUERY, kg_facts, "route_a", provider=provider)

    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 60)

    warnings = result.get("warnings", [])
    if warnings:
        print(f"\nWarnings: {warnings}")
    dr = result.get("diagnosis_results", [])
    if dr:
        print(f"\ndiagnosis_results: {len(dr)} item(s), confidence={dr[0].get('confidence')}")
    else:
        print("\ndiagnosis_results: empty — check warnings above")


if __name__ == "__main__":
    main()
