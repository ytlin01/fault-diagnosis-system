"""Source artifact inventory backed by data/governance/source_inventory.csv."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.governance.schema import SHEET_HEADERS
from services.governance.storage import (
    SOURCE_INVENTORY,
    ensure_table,
    read_csv_rows,
    resolve_governance_dir,
    write_csv_rows,
)

_KEY_COL = "source_id"
_HEADERS = SHEET_HEADERS[SOURCE_INVENTORY]


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _inventory_path(
    *,
    governance_dir: Path | None = None,
    excel_path: Path | None = None,
) -> Path:
    directory = resolve_governance_dir(governance_dir, excel_path=excel_path)
    return ensure_table(SOURCE_INVENTORY, directory)


def record(
    *,
    source_id: str,
    file_path: str,
    zone: str,
    source_type: str,
    route_eligibility: str = "unknown",
    serving_safe: str = "unknown",
    masking_status: str = "pending",
    reviewed_status: str = "pending",
    notes: str = "",
    date_added: str | None = None,
    dry_run: bool = False,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> dict[str, Any]:
    """Register or update a source artifact in source_inventory.csv."""
    row: dict[str, Any] = {
        "source_id": source_id,
        "file_path": file_path,
        "zone": zone,
        "source_type": source_type,
        "route_eligibility": route_eligibility,
        "serving_safe": serving_safe,
        "masking_status": masking_status,
        "reviewed_status": reviewed_status,
        "date_added": date_added or _today_iso(),
        "notes": notes,
    }

    if dry_run:
        print(f"[inventory DRY-RUN] Would record: {row}")
        return row

    path = _inventory_path(governance_dir=governance_dir, excel_path=excel_path)
    rows = read_csv_rows(path, _HEADERS)
    for index, existing in enumerate(rows):
        if existing.get(_KEY_COL) == source_id:
            rows[index] = {header: row.get(header, "") for header in _HEADERS}
            write_csv_rows(path, _HEADERS, rows)
            print(f"[inventory] Updated: {source_id}")
            return row

    rows.append({header: row.get(header, "") for header in _HEADERS})
    write_csv_rows(path, _HEADERS, rows)
    print(f"[inventory] Registered: {source_id}")
    return row


def get(
    source_id: str,
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> dict[str, str] | None:
    """Return the inventory row for source_id, or None if not found."""
    path = _inventory_path(governance_dir=governance_dir, excel_path=excel_path)
    for row in read_csv_rows(path, _HEADERS):
        if row.get(_KEY_COL) == source_id:
            return row
    return None


def list_all(
    excel_path: Path | None = None,
    governance_dir: Path | None = None,
) -> list[dict[str, str]]:
    """Return all rows in source_inventory.csv."""
    path = _inventory_path(governance_dir=governance_dir, excel_path=excel_path)
    return read_csv_rows(path, _HEADERS)
