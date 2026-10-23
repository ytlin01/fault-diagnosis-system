"""Evaluate a Route A expert-ranking input and write the frozen-policy report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_expert_ranking import (
    ExpertRankingInputError,
    evaluate_expert_ranking,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate candidate cause/action rankings against governed gold "
            "labels under the frozen route_a_expert_ranking_metrics_v1 policy."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
    try:
        report = evaluate_expert_ranking(payload)
    except ExpertRankingInputError as error:
        print(f"input rejected: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    primary = report["primary_metric"]
    failures = len(report["abstention_safety_gate_failures"])
    print(
        f"wrote {args.output} cases={report['case_count']} "
        f"eligible={report['domain_correctness_case_count']} "
        f"primary={primary['name']}={primary['value']} "
        f"abstention_failures={failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
