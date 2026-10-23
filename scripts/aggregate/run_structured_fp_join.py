"""CLI entry point for TASK-005 structured FP join aggregation.

Builds local processed aggregate artifacts only; it does not read raw data or
promote review candidates into confirmed diagnosis chains by itself.

Examples:
    python scripts/aggregate/run_structured_fp_join.py --dry-run
    python scripts/aggregate/run_structured_fp_join.py
    python scripts/aggregate/run_structured_fp_join.py --output-file structured_fp_join_v0.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.aggregation.structured_fp_join import (  # noqa: E402
    DEFAULT_MIN_CONTAINS_LENGTH,
    build_review_decisions_template,
    build_review_report,
    build_review_summary,
    build_structured_fp_join,
    build_summary,
    load_inputs,
    load_review_decisions,
    load_rules,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build TASK-005 EC/FP/RC/PA join table from processed canonical data."
    )
    parser.add_argument(
        "--processed-dir",
        default=str(PROJECT_ROOT / "data" / "processed"),
        help="Directory containing processed canonical and governance files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "processed" / "aggregates"),
        help="Directory for aggregate outputs.",
    )
    parser.add_argument(
        "--output-file",
        default="structured_fp_join_v0.json",
        help="Join output filename.",
    )
    parser.add_argument(
        "--summary-file",
        default="structured_fp_join_v0_summary.json",
        help="Summary output filename.",
    )
    parser.add_argument(
        "--rules",
        default=str(PROJECT_ROOT / "configs" / "fp_join_rules.yaml"),
        help="Path to FP join rules YAML used for review report generation.",
    )
    parser.add_argument(
        "--review-file",
        default="structured_fp_join_v0_review.json",
        help="Review report output filename.",
    )
    parser.add_argument(
        "--review-summary-file",
        default="structured_fp_join_v0_review_summary.json",
        help="Review report summary output filename.",
    )
    parser.add_argument(
        "--review-decisions-file",
        default="structured_fp_join_v0_review_decisions.json",
        help="Human review decisions input filename. Relative paths are resolved inside output-dir.",
    )
    parser.add_argument(
        "--min-contains-length",
        type=int,
        default=DEFAULT_MIN_CONTAINS_LENGTH,
        help="Minimum normalized FP length for contains_candidate matches.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print summary without writing files.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_dir = Path(args.processed_dir)
    output_dir = Path(args.output_dir)

    error_codes, downtime, error_gov, downtime_gov = load_inputs(processed_dir)
    rules = load_rules(Path(args.rules))
    review_decisions_path = Path(args.review_decisions_file)
    if not review_decisions_path.is_absolute():
        review_decisions_path = output_dir / review_decisions_path
    review_decisions = load_review_decisions(review_decisions_path)

    payload = build_structured_fp_join(
        error_codes,
        downtime,
        error_code_governance=error_gov,
        downtime_governance=downtime_gov,
        min_contains_length=args.min_contains_length,
        rules=rules,
        review_decisions=review_decisions,
    )
    summary = build_summary(payload)
    review_report = build_review_report(error_codes, downtime, rules, review_decisions=review_decisions)
    review_summary = build_review_summary(review_report)

    print("TASK-005 structured FP join summary")
    for key, value in summary["summary"].items():
        print(f"  {key}: {value}")
    print("TASK-005 FP review summary")
    for key, value in review_summary["summary"].items():
        print(f"  {key}: {value}")
    review_decision_summary = review_summary.get("review_decisions") or {}
    print("TASK-005 FP review decisions")
    print(f"  decision_count: {review_decision_summary.get('decision_count', 0)}")
    print(f"  applied_count: {review_decision_summary.get('applied_count', 0)}")
    print(f"  ignored_count: {review_decision_summary.get('ignored_count', 0)}")

    if args.dry_run:
        return

    pretty = not args.compact
    output_path = output_dir / args.output_file
    summary_path = output_dir / args.summary_file
    review_path = output_dir / args.review_file
    review_summary_path = output_dir / args.review_summary_file
    if not review_decisions_path.exists():
        write_json(review_decisions_path, build_review_decisions_template(), pretty=True)
        print(f"Wrote review decisions template: {review_decisions_path}")
    write_json(output_path, payload, pretty=pretty)
    write_json(summary_path, summary, pretty=True)
    write_json(review_path, review_report, pretty=pretty)
    write_json(review_summary_path, review_summary, pretty=True)
    print(f"Wrote join output: {output_path}")
    print(f"Wrote summary: {summary_path}")
    print(f"Wrote review report: {review_path}")
    print(f"Wrote review summary: {review_summary_path}")


if __name__ == "__main__":
    main()

