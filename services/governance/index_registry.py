"""Bind each index build to the source serving snapshot used to create it."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.governance._operation_log import append_record, require_nonblank


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def snapshot_id(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def record(
    *,
    index_name: str,
    source_id: str,
    serving_snapshot_id: str,
    build_script: str,
    index_type: str,
    notes: str = "",
    build_timestamp: str | None = None,
    dry_run: bool = False,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "index_name": index_name,
        "source_id": source_id,
        "build_timestamp": build_timestamp or _now_timestamp(),
        "serving_snapshot_id": serving_snapshot_id,
        "build_script": build_script,
        "index_type": index_type,
        "notes": notes,
    }
    require_nonblank(
        row,
        (
            "index_name",
            "source_id",
            "build_timestamp",
            "serving_snapshot_id",
            "build_script",
            "index_type",
        ),
    )
    return append_record(
        sheet_name="index_registry",
        row=row,
        unique_column=None,
        dry_run=dry_run,
        excel_path=excel_path,
        governance_dir=governance_dir,
    )
