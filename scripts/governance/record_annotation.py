#!/usr/bin/env python3
"""Record a human annotation against an immutable source version."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.annotation_tracker import check_staleness, record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--annotated-by", required=True)
    parser.add_argument("--annotation-type", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--governance-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stale = check_staleness(
        args.source_id,
        args.source_version,
        governance_dir=args.governance_dir,
    )
    row = record(
        source_id=args.source_id,
        source_version=args.source_version,
        annotated_by=args.annotated_by,
        annotation_type=args.annotation_type,
        staleness_warning=stale,
        notes=args.notes,
        dry_run=args.dry_run,
        governance_dir=args.governance_dir,
    )
    print(
        f"Annotation {row['annotation_id']} prepared; "
        f"staleness_warning={row['staleness_warning']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

