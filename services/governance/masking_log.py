"""Append successful structured and unstructured masking runs to masking_log."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.governance._operation_log import (
    append_record,
    default_operator,
    make_record_id,
    require_nonblank,
)


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(
    *,
    source_id: str,
    run_id: str | None = None,
    masking_source_name: str = "",
    input_source_id: str = "",
    canonical_source_id: str = "",
    serving_source_id: str = "",
    rules_version: str | int,
    masking_action: str,
    input_path: str,
    output_canonical_path: str,
    output_serving_path: str = "",
    manifest_path: str = "",
    lineage_path: str = "",
    operator: str | None = None,
    log_id: str | None = None,
    run_timestamp: str | None = None,
    dry_run: bool = False,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> dict[str, Any]:
    timestamp = run_timestamp or _now_timestamp()
    resolved_input_source_id = input_source_id or source_id
    row: dict[str, Any] = {
        "log_id": log_id or make_record_id("mask", timestamp),
        "run_id": run_id or make_record_id("maskrun", timestamp),
        # Compatibility alias for older consumers. New joins should use the
        # explicit input/canonical/serving source identifiers.
        "source_id": resolved_input_source_id,
        "masking_source_name": masking_source_name,
        "input_source_id": resolved_input_source_id,
        "canonical_source_id": canonical_source_id,
        "serving_source_id": serving_source_id,
        "run_timestamp": timestamp,
        "rules_version": rules_version,
        "masking_action": masking_action,
        "input_path": input_path,
        "output_canonical_path": output_canonical_path,
        "output_serving_path": output_serving_path,
        "manifest_path": manifest_path,
        "lineage_path": lineage_path,
        "operator": operator or default_operator(),
    }
    require_nonblank(
        row,
        (
            "log_id",
            "run_id",
            "source_id",
            "input_source_id",
            "run_timestamp",
            "rules_version",
            "masking_action",
            "input_path",
            "output_canonical_path",
            "operator",
        ),
    )
    return append_record(
        sheet_name="masking_log",
        row=row,
        unique_column="log_id",
        dry_run=dry_run,
        excel_path=excel_path,
        governance_dir=governance_dir,
    )
