"""Compare two BZ EC sheets with the same header shape.

Examples:
    python scripts/aggregate/compare_bz_ec_sheet_rows.py ^
      --left-file path/to/BZ.xlsx --left-sheet c1stn1 ^
      --right-file path/to/BZ.xlsx --right-sheet c1stn2 ^
      --key-columns "error code"

    python scripts/aggregate/compare_bz_ec_sheet_rows.py ^
      --left-file path/to/c1stn1.xlsx --right-file path/to/c1stn2.xlsx ^
      --key-columns "error code" "设备现有error code"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.aggregation.bz_ec_sheet_compare import (  # noqa: E402
    compare_sheet_rows,
    load_sheet_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare row differences between two BZ EC sheets with shared headers."
    )
    parser.add_argument("--left-file", required=True, help="Left workbook path.")
    parser.add_argument("--right-file", required=True, help="Right workbook path.")
    parser.add_argument("--left-sheet", help="Left sheet name. Defaults to the first sheet.")
    parser.add_argument("--right-sheet", help="Right sheet name. Defaults to the first sheet.")
    parser.add_argument(
        "--header-row",
        type=int,
        default=1,
        help="1-based header row number for both sheets.",
    )
    parser.add_argument(
        "--key-columns",
        nargs="*",
        default=None,
        help="Optional business key columns. If omitted, compare full rows only.",
    )
    parser.add_argument(
        "--ignore-columns",
        nargs="*",
        default=None,
        help="Optional columns to ignore during comparison.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "processed" / "compare"),
        help="Directory for local comparison outputs.",
    )
    parser.add_argument(
        "--output-prefix",
        default="bz_ec_compare",
        help="Prefix for output files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary only without writing output files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    left_sheet = load_sheet_rows(
        Path(args.left_file),
        sheet_name=args.left_sheet,
        header_row=args.header_row,
    )
    right_sheet = load_sheet_rows(
        Path(args.right_file),
        sheet_name=args.right_sheet,
        header_row=args.header_row,
    )
    result = compare_sheet_rows(
        left_sheet,
        right_sheet,
        key_columns=args.key_columns,
        ignore_columns=args.ignore_columns,
    )

    _print_summary(result)
    if args.dry_run:
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.output_prefix

    json_path = output_dir / f"{prefix}_summary.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    comparison = result["comparison"]
    _write_rows_csv(output_dir / f"{prefix}_left_only.csv", comparison.get("left_only_rows", []))
    _write_rows_csv(output_dir / f"{prefix}_right_only.csv", comparison.get("right_only_rows", []))
    _write_changed_csv(output_dir / f"{prefix}_changed.csv", comparison.get("changed_rows", []))
    _write_rows_csv(output_dir / f"{prefix}_duplicate_keys.csv", comparison.get("duplicate_keys", []))

    print(f"Wrote summary JSON: {json_path}")
    print(f"Wrote left-only CSV: {output_dir / f'{prefix}_left_only.csv'}")
    print(f"Wrote right-only CSV: {output_dir / f'{prefix}_right_only.csv'}")
    print(f"Wrote changed CSV: {output_dir / f'{prefix}_changed.csv'}")
    print(f"Wrote duplicate-keys CSV: {output_dir / f'{prefix}_duplicate_keys.csv'}")


def _print_summary(result: dict[str, Any]) -> None:
    print("BZ EC sheet comparison")
    print(f"  left:  {result['left']['workbook_path']} :: {result['left']['sheet_name']}")
    print(f"  right: {result['right']['workbook_path']} :: {result['right']['sheet_name']}")
    header_diff = result["header_diff"]
    print(f"  shared headers: {len(header_diff['shared_headers'])}")
    print(f"  left-only headers: {len(header_diff['left_only_headers'])}")
    print(f"  right-only headers: {len(header_diff['right_only_headers'])}")

    comparison = result["comparison"]
    print(f"  comparison mode: {comparison['mode']}")
    for key, value in comparison["row_count_summary"].items():
        print(f"  {key}: {value}")


def _write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(_collect_fieldnames(rows))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_flatten_row(row, fieldnames))


def _write_changed_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    flattened: list[dict[str, str]] = []
    for row in rows:
        base = {
            "key": json.dumps(row.get("key", {}), ensure_ascii=False),
            "left_row_number": str(row.get("left_row_number", "")),
            "right_row_number": str(row.get("right_row_number", "")),
        }
        diffs = row.get("diffs", [])
        if not diffs:
            flattened.append(base)
            continue
        for diff in diffs:
            item = dict(base)
            item["column"] = str(diff.get("column", ""))
            item["left"] = str(diff.get("left", ""))
            item["right"] = str(diff.get("right", ""))
            flattened.append(item)
    _write_rows_csv(path, flattened)


def _collect_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    return fieldnames


def _flatten_row(row: dict[str, Any], fieldnames: list[str]) -> dict[str, str]:
    flat: dict[str, str] = {}
    for field in fieldnames:
        value = row.get(field, "")
        if isinstance(value, (dict, list)):
            flat[field] = json.dumps(value, ensure_ascii=False)
        else:
            flat[field] = str(value)
    return flat


if __name__ == "__main__":
    main()
