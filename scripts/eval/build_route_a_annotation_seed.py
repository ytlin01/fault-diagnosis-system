"""Build the V2-TASK001 C1STN provisional annotation seed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_golden_annotation import validate_annotation_queue
from services.evaluation.route_a_golden_seed import build_annotation_seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic provisional Route A annotation seed."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--masking-log-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=15)
    args = parser.parse_args(argv)

    rows = json.loads(args.input.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        parser.error("--input must contain a JSON array")
    queue = build_annotation_seed(
        rows,
        source_path=args.input,
        source_id=args.source_id,
        manifest_path=args.manifest_path,
        masking_log_id=args.masking_log_id,
        count=args.count,
    )
    validate_annotation_queue(queue)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(queue['cases'])} provisional development cases "
        f"to {args.output}"
    )
    print(
        "No accepted causes or cause/action pairs were generated; "
        "domain review is required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
