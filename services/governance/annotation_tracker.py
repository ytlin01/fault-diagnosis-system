"""Record human annotations and detect source-version staleness."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.governance._operation_log import (
    append_record,
    make_record_id,
    read_records,
    require_nonblank,
)


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(
    *,
    source_id: str,
    source_version: str,
    annotated_by: str,
    annotation_type: str,
    staleness_warning: bool = False,
    notes: str = "",
    annotation_id: str | None = None,
    annotated_at: str | None = None,
    dry_run: bool = False,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> dict[str, Any]:
    timestamp = annotated_at or _now_timestamp()
    row: dict[str, Any] = {
        "annotation_id": annotation_id or make_record_id("annotation", timestamp),
        "source_id": source_id,
        "source_version": source_version,
        "annotated_by": annotated_by,
        "annotated_at": timestamp,
        "annotation_type": annotation_type,
        "staleness_warning": "yes" if staleness_warning else "no",
        "notes": notes,
    }
    require_nonblank(
        row,
        (
            "annotation_id",
            "source_id",
            "source_version",
            "annotated_by",
            "annotated_at",
            "annotation_type",
        ),
    )
    return append_record(
        sheet_name="annotation_log",
        row=row,
        unique_column="annotation_id",
        dry_run=dry_run,
        excel_path=excel_path,
        governance_dir=governance_dir,
    )


def check_staleness(
    source_id: str,
    current_source_version: str,
    *,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> bool:
    rows = read_records(
        "annotation_log",
        governance_dir=governance_dir,
        excel_path=excel_path,
    )
    matching = [row for row in rows if row.get("source_id") == source_id]
    if not matching:
        return False
    return matching[-1].get("source_version") != current_source_version
