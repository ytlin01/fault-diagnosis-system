"""Canonical CSV/JSONL storage for data governance records."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from services.governance.schema import SHEET_HEADERS


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOVERNANCE_DIR = REPO_ROOT / "data" / "governance"

SOURCE_INVENTORY = "source_inventory"
OPERATION_LOGS = {
    "masking_log",
    "annotation_log",
    "index_registry",
    "eval_run_log",
}


def resolve_governance_dir(
    governance_dir: Path | None = None,
    *,
    excel_path: Path | None = None,
) -> Path:
    """Return canonical governance directory.

    ``excel_path`` is accepted as a backwards-compatible testing alias. It no
    longer points operational writes at an XLSX workbook.
    """
    if governance_dir is not None:
        return governance_dir
    if excel_path is not None:
        return excel_path.parent / "governance"
    return DEFAULT_GOVERNANCE_DIR


def table_path(table_name: str, governance_dir: Path | None = None) -> Path:
    directory = resolve_governance_dir(governance_dir)
    suffix = ".csv" if table_name == SOURCE_INVENTORY else ".jsonl"
    return directory / f"{table_name}{suffix}"


def ensure_table(table_name: str, governance_dir: Path | None = None) -> Path:
    if table_name not in SHEET_HEADERS:
        raise ValueError(f"Unknown governance table: {table_name}")
    path = table_path(table_name, governance_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    if table_name == SOURCE_INVENTORY:
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=SHEET_HEADERS[table_name]).writeheader()
    else:
        path.write_text("", encoding="utf-8")
    return path


def read_csv_rows(path: Path, headers: Iterable[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({header: str(row.get(header) or "") for header in headers})
        return rows


def write_csv_rows(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: "" if row.get(header) is None else row.get(header, "") for header in headers})


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    # ``utf-8-sig`` accepts both ordinary UTF-8 and a legacy BOM on the first
    # line without altering the append-only file.
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def append_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
