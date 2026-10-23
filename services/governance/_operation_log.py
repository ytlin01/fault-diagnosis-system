"""Shared helpers for append-only operational governance logs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.governance.storage import (
    append_jsonl_row,
    ensure_table,
    read_jsonl_rows,
    resolve_governance_dir,
)


DEFAULT_GOVERNANCE_DIR = Path(__file__).resolve().parents[2] / "data" / "governance"


def make_record_id(prefix: str, timestamp: str) -> str:
    compact_timestamp = timestamp.replace("+00:00", "Z").replace("-", "").replace(":", "")
    return f"{prefix}_{compact_timestamp}_{uuid4().hex[:8]}"


def default_operator() -> str:
    return (
        os.getenv("FAULTDX_OPERATOR")
        or os.getenv("USERNAME")
        or os.getenv("USER")
        or "local_pipeline"
    )


def safe_repo_path(path: str | Path | None, repo_root: Path) -> str:
    """Return a repository-relative path without leaking local absolute paths."""
    if path is None or str(path).strip() == "":
        return ""
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return candidate.name


def compact_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def require_nonblank(row: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if str(row.get(field, "")).strip() == ""]
    if missing:
        raise ValueError(f"Missing required operational log fields: {', '.join(missing)}")


def append_record(
    *,
    sheet_name: str,
    row: dict[str, Any],
    unique_column: str | None,
    dry_run: bool,
    excel_path: Path | None,
    governance_dir: Path | None = None,
) -> dict[str, Any]:
    if dry_run:
        print(f"[{sheet_name} DRY-RUN] Would append: {row}")
        return row

    directory = resolve_governance_dir(governance_dir, excel_path=excel_path)
    path = ensure_table(sheet_name, directory)
    if unique_column is not None:
        unique_value = str(row[unique_column])
        if any(str(existing.get(unique_column, "")) == unique_value for existing in read_jsonl_rows(path)):
            raise ValueError(
                f"Duplicate {sheet_name} record: {unique_column}={unique_value}"
            )
    append_jsonl_row(path, row)
    identifier = row.get(unique_column, "") if unique_column else row.get("index_name", "")
    print(f"[{sheet_name}] Recorded: {identifier}")
    return row


def read_records(
    sheet_name: str,
    *,
    governance_dir: Path | None = None,
    excel_path: Path | None = None,
) -> list[dict[str, Any]]:
    directory = resolve_governance_dir(governance_dir, excel_path=excel_path)
    path = ensure_table(sheet_name, directory)
    return read_jsonl_rows(path)
