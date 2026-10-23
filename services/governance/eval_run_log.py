"""Append completed evaluation runs to eval_run_log."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.governance._operation_log import (
    append_record,
    compact_json,
    make_record_id,
    require_nonblank,
)


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(
    *,
    eval_set: str,
    model: str,
    route: str,
    score_summary: Any,
    notes: str = "",
    run_id: str | None = None,
    run_timestamp: str | None = None,
    dry_run: bool = False,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> dict[str, Any]:
    timestamp = run_timestamp or _now_timestamp()
    row: dict[str, Any] = {
        "run_id": run_id or make_record_id("eval", timestamp),
        "eval_set": eval_set,
        "run_timestamp": timestamp,
        "model": model,
        "route": route,
        "score_summary": compact_json(score_summary),
        "notes": notes,
    }
    require_nonblank(
        row,
        ("run_id", "eval_set", "run_timestamp", "model", "route", "score_summary"),
    )
    return append_record(
        sheet_name="eval_run_log",
        row=row,
        unique_column="run_id",
        dry_run=dry_run,
        excel_path=excel_path,
        governance_dir=governance_dir,
    )
