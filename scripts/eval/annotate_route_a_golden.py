"""Interactive CLI for expert annotation of graph-independent Route A gold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_golden_annotation import GoldenAnnotationInputError, create_review_record, queue_case, validate_annotation_queue


def _prompt(label: str, *, required: bool = True) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("A value is required.")


def _choice(label: str, options: set[str]) -> str:
    while True:
        value = _prompt(f"{label} ({', '.join(sorted(options))})")
        if value in options:
            return value
        print(f"Choose one of: {', '.join(sorted(options))}")


def _selected_values(label: str, available: list[tuple[str, str]]) -> list[str]:
    if available:
        print(label + ":")
        for identifier, display in available:
            print(f"  {identifier} — {display}")
    raw = _prompt("Selected IDs (comma-separated; blank for none)", required=False)
    return [value.strip() for value in raw.split(",") if value.strip()]


def _anchors() -> list[dict[str, str]]:
    anchors = []
    print("Enter at least one governed source anchor. Do not paste raw source content.")
    while True:
        anchors.append({
            "source_id": _prompt("Source ID"),
            "anchor": _prompt("Anchor/location"),
            "source_review_state": _choice("Source review state", {"pending", "reviewed", "adjudicated"}),
            "allowed_use": _choice("Allowed use", {"annotation_only", "evaluation_only", "annotation_and_evaluation"}),
        })
        if _prompt("Add another source anchor? [y/N]", required=False).lower() != "y":
            return anchors


def _read_queue(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _choose_case(queue: dict[str, Any], requested: str | None, allow_blind: bool) -> dict[str, Any]:
    if requested:
        return dict(queue_case(queue, requested, allow_blind=allow_blind))
    print("Available cases:")
    for item in queue["cases"]:
        if item["partition"] == "blind" and not allow_blind:
            continue
        print(f"  {item['case_id']} [{item['partition']}] {item['scenario_id']}")
    return dict(queue_case(queue, _prompt("Case ID"), allow_blind=allow_blind))


def run_interactive(queue: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    case = _choose_case(queue, args.case_id, args.allow_blind)
    print(f"\nCase {case['case_id']} ({case['scenario_id']}, {case['partition']})")
    print(f"Query: {case['query']}")
    print("No KG ranking or graph result is displayed by this tool.")
    context = case.get("source_context")
    if isinstance(context, dict):
        print("\nMasked source context — SOURCE-SUGGESTED ONLY, not gold:")
        print(f"  Code: {context.get('code', '')}")
        print(f"  Local alarm code: {context.get('local_alarm_code', '')}")
        print(f"  Category: {context.get('category', '')}")
        print(f"  Description: {context.get('error_description', '')}")
        print(f"  Chinese description: {context.get('error_description_zh', '')}")
        print(
            "  Suggested repair: "
            f"{context.get('source_suggested_repair_action', '')}"
        )
    causes = _selected_values("Controlled cause vocabulary", [(item["cause_id"], item["display_name"]) for item in queue.get("cause_catalog", [])])
    pair_options = [(f"{item['cause_id']}|{item['action_id']}", item["display_name"]) for item in queue.get("cause_action_pair_catalog", [])]
    raw_pairs = _selected_values("Controlled cause/action pairs", pair_options)
    pairs = [{"cause_id": value.split("|", 1)[0], "action_id": value.split("|", 1)[1]} for value in raw_pairs if "|" in value]
    if len(pairs) != len(raw_pairs):
        raise GoldenAnnotationInputError("cause/action selections must use cause_id|action_id")
    return create_review_record(
        queue,
        case_id=case["case_id"],
        reviewer_id=args.reviewer_id,
        role=args.role,
        decision=_choice("Decision", {"accept", "reject", "replace", "abstain"}),
        label_maturity=_choice("Label maturity", {"assumed_label_provisional", "provisional", "reviewed", "adjudicated"}),
        abstention=_choice("Abstention expectation", {"required", "allowed", "not_expected"}),
        cause_ids=causes,
        cause_action_pairs=pairs,
        source_anchors=_anchors(),
        rationale_anchor=_prompt("Rationale anchor"),
        allow_blind=args.allow_blind,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Annotate a Route A golden case without exposing KG results.")
    parser.add_argument("--queue", type=Path, required=True, help="Governed annotation-queue JSON; use approved/masked content only.")
    parser.add_argument("--output", type=Path, required=True, help="Append-only JSONL review-log destination.")
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--role", choices=["annotator", "domain_reviewer", "adjudicator"], required=True)
    parser.add_argument("--case-id", help="Case to annotate; omit to choose interactively.")
    parser.add_argument("--allow-blind", action="store_true", help="Explicitly authorize access to a blind label case.")
    args = parser.parse_args(argv)
    try:
        queue = _read_queue(args.queue)
        validate_annotation_queue(queue)
        record = run_interactive(queue, args)
    except (OSError, json.JSONDecodeError, GoldenAnnotationInputError) as exc:
        print(f"annotation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"Review record appended to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
