"""
Split structured_fp_join_v1_baseline.json into complete-chain and review-queue subsets.

Complete chain criteria: EC + FP + RC (not ["pending"], non-empty) + PA (non-empty) all present.
Output:
  data/processed/diagnostic/diagnostic_complete_chains.json   -- ready for load_diagnostic_triples.py
  data/processed/diagnostic/diagnostic_review_queue.json      -- needs RC/PA before loading
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_INPUT = Path("data/processed/structured/aggregates/structured_fp_join_v1_baseline.json")
DEFAULT_OUTPUT_DIR = Path("data/processed/structured")

PENDING_SENTINELS = {"pending", "待确认", "tbd", "n/a", ""}


def _is_substantive(values: list[str]) -> bool:
    return bool(values) and not all(v.strip().lower() in PENDING_SENTINELS for v in values)


def split(input_path: Path, output_dir: Path) -> None:
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    records = data["records"]
    complete, review = [], []

    for r in records:
        ec = r.get("EC", "").strip()
        fp = r.get("FP", "").strip()
        rc = r.get("RC") or []
        pa = r.get("PA") or [] 

        if ec and fp and _is_substantive(rc) and _is_substantive(pa):
            complete.append(r)
        else:
            review.append(r)

    output_dir.mkdir(parents=True, exist_ok=True)

    base_meta = {k: v for k, v in data.get("metadata", {}).items() if k != "summary"}

    complete_out = {
        "metadata": {
            **base_meta,
            "subset": "complete_chains",
            "split_criteria": "EC + FP + RC(non-pending) + PA all present",
            "record_count": len(complete),
        },
        "records": complete,
    }
    review_out = {
        "metadata": {
            **base_meta,
            "subset": "review_queue",
            "split_criteria": "RC=pending or PA missing",
            "record_count": len(review),
        },
        "records": review,
    }

    complete_path = output_dir / "diagnostic_complete_chains.json"
    review_path = output_dir / "diagnostic_review_queue.json"

    with open(complete_path, "w", encoding="utf-8") as f:
        json.dump(complete_out, f, ensure_ascii=False, indent=2)

    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(review_out, f, ensure_ascii=False, indent=2)

    total = len(records)
    print(f"Input:          {input_path}  ({total} records)")
    print(f"Complete chain: {complete_path}  ({len(complete)} records)")
    print(f"Review queue:   {review_path}  ({len(review)} records)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    split(args.input, args.output_dir)


if __name__ == "__main__":
    main()
