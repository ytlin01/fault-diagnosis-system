#!/usr/bin/env python3
"""Export canonical governance CSV/JSONL files to a review XLSX workbook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.governance.excel_sync import ExcelSync
from services.governance.schema import SHEET_HEADERS
from services.governance.storage import (
    DEFAULT_GOVERNANCE_DIR,
    OPERATION_LOGS,
    SOURCE_INVENTORY,
    read_csv_rows,
    read_jsonl_rows,
    table_path,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "data_governance.xlsx"


def export(governance_dir: Path, output_path: Path, *, overwrite: bool = False) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"{output_path} already exists; pass --overwrite")

    sync = ExcelSync(output_path)
    sync.initialize(overwrite=True)

    inventory_path = table_path(SOURCE_INVENTORY, governance_dir)
    for row in read_csv_rows(inventory_path, SHEET_HEADERS[SOURCE_INVENTORY]):
        sync.append_row(SOURCE_INVENTORY, row)

    for table_name in sorted(OPERATION_LOGS):
        path = table_path(table_name, governance_dir)
        for row in read_jsonl_rows(path):
            sync.append_row(table_name, row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--governance-dir", type=Path, default=DEFAULT_GOVERNANCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export(args.governance_dir, args.output, overwrite=args.overwrite)
    print(f"[governance] Exported review workbook: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
