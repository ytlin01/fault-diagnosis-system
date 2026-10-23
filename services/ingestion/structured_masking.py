"""Core structured masking processor.

Handles the full pipeline for structured (Excel/CSV) data:
    1. File discovery (glob patterns)
    2. Sheet selection (index / name / interactive)
    3. Data reading (openpyxl for xlsx, csv module for csv)
    4. Header normalization + alias resolution
    5. Row-level masking for canonical and serving views
    6. JSON output
    7. Manifest + lineage generation

This module is file-format aware but rule-agnostic — all rules come
from masking_rules.yaml via masking_engine.

Raw files are read only from the local workspace. This pipeline does not call
external APIs, and serving outputs are the only view intended for broader use.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl

from services.ingestion.header_normalize import HeaderResolution, normalize_header
from services.ingestion.lineage import LineageWriter
from services.ingestion.manifest import build_manifest, make_run_id, write_manifest
from services.ingestion.name_mapping import (
    apply_content_name_mapping,
    load_name_mapping,
    resolve_name_mapping_path,
)
from services.ingestion.masking_engine import (
    get_source_config,
    mask_row,
    resolve_column_rule,
    resolve_headers,
)

LEGACY_XLS_CONVERSION_HINT = (
    "Legacy .xls workbooks are not read directly by this pipeline. "
    "Convert the file locally to .xlsx first, then rerun inspect/dry-run. "
    "On Windows, use scripts/ingest/convert_xls_to_xlsx.ps1 in the controlled "
    "raw-data environment."
)


# ── File discovery ───────────────────────────────────────────────────────────

def find_source_files(
    file_patterns: list[str],
    raw_dir: Path,
    *,
    require_all_patterns: bool = False,
) -> list[Path]:
    """Glob for source files under raw_dir matching any of the patterns."""
    found: list[Path] = []
    missing_patterns: list[str] = []
    for pattern in file_patterns:
        matches = sorted(raw_dir.glob(pattern))
        if require_all_patterns and not matches:
            missing_patterns.append(pattern)
        found.extend(matches)
    if missing_patterns:
        raise FileNotFoundError(
            f"Missing required file pattern(s) {missing_patterns} in {raw_dir}. "
            "Convert legacy .xls files to .xlsx first if this is a TASK-035 "
            "source family."
        )
    if not found:
        raise FileNotFoundError(
            f"No files found matching {file_patterns} in {raw_dir}"
        )
    return sorted(dict.fromkeys(found))


# ── Sheet selection ──────────────────────────────────────────────────────────

def select_sheets(
    workbook: openpyxl.Workbook,
    sheet_selector: dict | None,
    file_path: Path,
) -> list[str]:
    """Select worksheet name(s) based on the sheet_selector config.

    Returns a list of sheet names (always ≥ 1).

    Modes:
        index    — value: int or list[int], 0-based indices
        name     — value: str or list[str], exact sheet names
        pattern  — value: str, fnmatch glob matched against sheet names
        all      — select every sheet in the workbook
    """
    sheet_selector = sheet_selector or {}
    mode = sheet_selector.get("mode", "index")
    value = sheet_selector.get("value", 0)
    all_names = workbook.sheetnames

    selected: list[str] = []

    if mode == "index":
        indices = value if isinstance(value, list) else [value]
        for idx in indices:
            idx = int(idx)
            if idx >= len(all_names):
                raise IndexError(
                    f"Sheet index {idx} out of range. "
                    f"'{file_path.name}' has {len(all_names)} sheets: {all_names}"
                )
            selected.append(all_names[idx])

    elif mode == "name":
        names = value if isinstance(value, list) else [value]
        # Build stripped lookup: stripped_name → actual_name
        stripped_lookup = {n.strip(): n for n in all_names}
        for name in names:
            # Try exact match first, then stripped match
            if name in all_names:
                selected.append(name)
            elif name.strip() in stripped_lookup:
                actual = stripped_lookup[name.strip()]
                print(f"[SHEET] Fuzzy name match: '{name}' → '{repr(actual)}' "
                      f"(trailing whitespace in sheet name)")
                selected.append(actual)
            else:
                raise KeyError(
                    f"Sheet '{name}' not found in '{file_path.name}'. "
                    f"Available: {all_names}"
                )

    elif mode == "pattern":
        import fnmatch
        pattern_str = str(value)
        for name in all_names:
            # Match against stripped name to handle trailing spaces
            if fnmatch.fnmatch(name.strip(), pattern_str):
                selected.append(name)
        if not selected:
            raise KeyError(
                f"No sheet matching pattern '{pattern_str}' in '{file_path.name}'. "
                f"Available: {all_names}"
            )

    elif mode == "all":
        selected = list(all_names)

    else:
        raise ValueError(
            f"Unknown sheet_selector mode: '{mode}'. "
            f"Supported: index, name, pattern, all"
        )

    print(f"[SHEET] Selected {len(selected)} sheet(s): {selected}")
    return selected


# ── Workbook inspection ──────────────────────────────────────────────────────

def inspect_workbook(
    file_path: Path,
    *,
    header_row: int | None = 0,
    peek_rows: int = 3,
    source_config: dict | None = None,
) -> list[dict]:
    """Inspect an Excel workbook without reading full data.

    Returns a list of per-sheet info dicts and prints a human-readable report.
    Only reads the first few rows of each sheet for header/size estimation.

    Args:
        file_path: Path to .xlsx file.
        header_row: 0-based index of the expected header row, or None for auto.
        peek_rows: How many rows to read for inspection (default: 3).
    """
    if file_path.suffix.lower() == ".xls":
        raise ValueError(f"{LEGACY_XLS_CONVERSION_HINT} File: {file_path.name}")

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    sheet_infos: list[dict] = []

    try:
        print()
        print(f"  File: {file_path.name}")
        print(f"  Sheets ({len(wb.sheetnames)}):")
        print(f"  (header_row is 0-based: 0 = first row, 1 = second row, ...)")
        print()

        for idx, name in enumerate(wb.sheetnames):
            ws = wb[name]
            rows_peeked: list[tuple] = []
            scan_limit = 10 if header_row is None else header_row + peek_rows + 1
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                rows_peeked.append(row)
                if i + 1 >= scan_limit:
                    break

            effective_header_row = (
                _detect_header_row(rows_peeked, source_config=source_config)
                if header_row is None else header_row
            )
            detection_scores = (
                _header_detection_scores(rows_peeked, source_config=source_config)
                if header_row is None else []
            )

            # Estimate dimensions
            total_rows = 0
            for _ in ws.iter_rows(values_only=True):
                total_rows += 1
            num_cols = len(rows_peeked[0]) if rows_peeked else 0

            # Extract header at configured row
            header_vals: list[str] = []
            if len(rows_peeked) > effective_header_row:
                header_vals = [
                    str(h) if h is not None else "(None)"
                    for h in rows_peeked[effective_header_row]
                ]

            # Data rows = total - header_row - 1
            data_rows = max(0, total_rows - effective_header_row - 1)

            info = {
                "index": idx,
                "name": name,
                "total_rows": total_rows,
                "data_rows": data_rows,
                "num_cols": num_cols,
                "header_at_row": effective_header_row,
                "header_values": header_vals,
            }
            if detection_scores:
                info["header_detection_scores"] = detection_scores
            sheet_infos.append(info)

            # Print
            header_preview = header_vals[:6]
            more = f" +{len(header_vals) - 6} more" if len(header_vals) > 6 else ""
            print(f"  [{idx}] {name:<20}  {data_rows:>5} data rows × {num_cols} cols")
            print(f"       header(row={effective_header_row}): {header_preview}{more}")
            if source_config and header_vals:
                header_res = resolve_headers(header_vals, source_config)
                print(
                    "       header matches: "
                    f"matched={len(header_res.matched)}, "
                    f"alias={len(header_res.alias_matched)}, "
                    f"unmatched={len(header_res.unmatched)}, "
                    f"unused_rules={len(header_res.unused_rules)}"
                )
                if header_res.unmatched:
                    print(f"       unmatched headers: {header_res.unmatched}")
                if header_res.unused_rules:
                    print(f"       unused rules: {header_res.unused_rules}")
            if detection_scores:
                compact_scores = [
                    f"r{s['row']}:rules={s['rule_matches']},alias={s['alias_matches']},nonempty={s['nonempty_cells']}"
                    for s in detection_scores
                ]
                print(f"       auto scores: {compact_scores}")

    finally:
        wb.close()

    print()
    return sheet_infos


# ── Data reading ─────────────────────────────────────────────────────────────

def _detect_header_row(
    all_rows: list[tuple],
    max_scan: int = 10,
    source_config: dict | None = None,
) -> int:
    """Auto-detect the header row.

    When source rules are available, prefer the row with the strongest
    header-rule / alias match. If no configured column matches in the scanned
    rows, fall back to the row with the most non-empty cells.

    Returns 0-based row index.
    """
    best_nonempty_row = 0
    best_nonempty_count = 0
    best_rule_row = 0
    best_rule_count = 0

    for i, row in enumerate(all_rows[:max_scan]):
        nonempty_count = sum(1 for v in row if v is not None and str(v).strip())
        if nonempty_count > best_nonempty_count:
            best_nonempty_count = nonempty_count
            best_nonempty_row = i

        if source_config:
            candidate_headers = [
                str(h) if h is not None else f"_unnamed_{idx}"
                for idx, h in enumerate(row)
            ]
            header_res = resolve_headers(candidate_headers, source_config)
            rule_count = len(header_res.mapping)
            # Examples/data rows can be dense; header ties must prefer the
            # earliest matching row instead of the row with more non-empty cells.
            if rule_count > best_rule_count:
                best_rule_count = rule_count
                best_rule_row = i

    if best_rule_count > 0:
        return best_rule_row
    return best_nonempty_row


def _header_detection_scores(
    all_rows: list[tuple],
    max_scan: int = 10,
    source_config: dict | None = None,
) -> list[dict[str, Any]]:
    """Return non-sensitive row-level header detection diagnostics."""
    scores: list[dict[str, Any]] = []
    for i, row in enumerate(all_rows[:max_scan]):
        nonempty_count = sum(1 for v in row if v is not None and str(v).strip())
        rule_count = 0
        alias_count = 0
        if source_config:
            candidate_headers = [
                str(h) if h is not None else f"_unnamed_{idx}"
                for idx, h in enumerate(row)
            ]
            header_res = resolve_headers(candidate_headers, source_config)
            rule_count = len(header_res.mapping)
            alias_count = len(header_res.alias_matched)
        scores.append({
            "row": i,
            "nonempty_cells": nonempty_count,
            "rule_matches": rule_count,
            "alias_matches": alias_count,
        })
    return scores


def _expand_merged_cells(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    all_rows: list[list[Any]],
) -> list[list[Any]]:
    """Fill merged-cell ranges in memory using the top-left anchor value."""
    if not all_rows or not ws.merged_cells.ranges:
        return all_rows

    expanded_rows = [list(row) for row in all_rows]
    max_cols = max((len(row) for row in expanded_rows), default=0)
    for row in expanded_rows:
        if len(row) < max_cols:
            row.extend([None] * (max_cols - len(row)))

    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        anchor_value = expanded_rows[min_row - 1][min_col - 1]
        for row_idx in range(min_row - 1, max_row):
            for col_idx in range(min_col - 1, max_col):
                if expanded_rows[row_idx][col_idx] in (None, ""):
                    expanded_rows[row_idx][col_idx] = anchor_value

    return expanded_rows


def _read_single_sheet(
    wb: openpyxl.Workbook,
    sheet_name: str,
    header_row: int | None,
    skip_rows_after_header: int,
    source_config: dict | None = None,
) -> tuple[list[str], list[dict[str, Any]], int]:
    """Read one sheet from an already-open workbook.

    Args:
        wb: Open workbook.
        sheet_name: Name of the sheet to read.
        header_row: 0-based index of the header row.
            If None, auto-detect by finding the row with most non-None cells.
        skip_rows_after_header: Number of rows to skip after the header
            before data begins (e.g. separator rows, unit rows).

    Returns:
        (raw_headers, row_dicts, actual_header_row)
        row dicts use normalized header keys.
    """
    ws = wb[sheet_name]
    all_rows = _expand_merged_cells(
        ws,
        [list(row) for row in ws.iter_rows(values_only=True)],
    )

    if not all_rows:
        return [], [], 0

    # Auto-detect header row if not specified
    if header_row is None:
        header_row = _detect_header_row(all_rows, source_config=source_config)

    if len(all_rows) <= header_row:
        return [], [], header_row

    # Extract headers
    raw_header_tuple = all_rows[header_row]
    raw_headers = [
        str(h) if h is not None else f"_unnamed_{i}"
        for i, h in enumerate(raw_header_tuple)
    ]
    norm_headers = [normalize_header(h) for h in raw_headers]

    # Data starts after header + skip rows
    data_start = header_row + 1 + skip_rows_after_header
    data_rows_raw = all_rows[data_start:]

    rows: list[dict[str, Any]] = []
    for row_values in data_rows_raw:
        if all(v is None for v in row_values):
            continue
        row_dict: dict[str, Any] = {}
        for col_idx, value in enumerate(row_values):
            if col_idx < len(norm_headers):
                row_dict[norm_headers[col_idx]] = value
        rows.append(row_dict)

    return raw_headers, rows, header_row


def _project_rows_to_target_columns(
    raw_headers: list[str],
    rows: list[dict[str, Any]],
    source_config: dict,
    target_columns: list[str],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Project rows to target columns and fill missing columns with None.

    Matching is resolved via header normalization + alias resolution, so a
    configured target column can be matched through the source rule name or an
    alias. Output headers follow the original target_columns order, while row
    dict keys use normalized target names.
    """
    header_res = resolve_headers(raw_headers, source_config)
    norm_headers = [normalize_header(h) for h in raw_headers]
    target_norms = [normalize_header(c) for c in target_columns]

    target_to_source: dict[str, str] = {}
    for actual_norm in norm_headers:
        rule_name = header_res.mapping.get(actual_norm)
        if rule_name:
            target_to_source.setdefault(normalize_header(rule_name), actual_norm)
        target_to_source.setdefault(actual_norm, actual_norm)

    missing_targets = [
        original
        for original, target_norm in zip(target_columns, target_norms)
        if target_norm not in target_to_source
    ]
    if target_columns and len(missing_targets) == len(target_columns):
        raise ValueError(
            "columns_keep matched 0 configured columns on a selected sheet. "
            "Check the workbook header row with --inspect, then update "
            "header_row or column_aliases before masking."
        )

    projected_rows: list[dict[str, Any]] = []
    for row in rows:
        projected: dict[str, Any] = {}
        for original, target_norm in zip(target_columns, target_norms):
            source_key = target_to_source.get(target_norm)
            projected[target_norm] = row.get(source_key) if source_key else None
        projected_rows.append(projected)

    return list(target_columns), projected_rows, missing_targets



def read_excel_rows(
    file_path: Path,
    sheet_selector: dict | None = None,
    header_row: int | None = 0,
    skip_rows_after_header: int = 0,
    combine_sheets: bool = False,
    source_config: dict | None = None,
    target_columns: list[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]], dict]:
    """Read an Excel file and return (raw_headers, row_dicts, sheet_meta).

    Supports single-sheet and multi-sheet reading with optional combine.

    Args:
        file_path: Path to .xlsx file.
        sheet_selector: Sheet selection config dict.
        header_row: 0-based index of the header row, or None for auto.
        skip_rows_after_header: Rows to skip after header (default: 0).
        combine_sheets: If True and multiple sheets selected, merge rows.
        source_config: Source config block, used when projecting to target
            columns via alias/rule resolution.
        target_columns: Stable output columns to preserve in order. Missing
            columns are filled with None instead of being dropped.

    Returns:
        raw_headers: Header strings from the first (or only) sheet.
        rows: Combined list of row dicts.
        sheet_meta: Dict with per-sheet row counts and combine diagnostics.
    """
    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=False)
    sheet_meta: dict[str, Any] = {"sheets_read": [], "column_reordered": False}

    try:
        selected_names = select_sheets(wb, sheet_selector, file_path)

        if len(selected_names) == 1 or not combine_sheets:
            target = selected_names[0]
            if len(selected_names) > 1 and not combine_sheets:
                print(f"[WARN] {len(selected_names)} sheets selected but "
                      f"combine_sheets=false. Using first: '{target}'")
            raw_headers, rows, actual_hr = _read_single_sheet(
                wb, target, header_row, skip_rows_after_header, source_config
            )
            sheet_meta["sheets_read"].append({
                "name": target,
                "rows": len(rows),
                "header_row_used": actual_hr,
            })
            return raw_headers, rows, sheet_meta

        per_sheet: list[tuple[str, list[str], list[str], list[dict[str, Any]], int]] = []
        for sheet_name in selected_names:
            raw_h, rows, actual_hr = _read_single_sheet(
                wb, sheet_name, header_row, skip_rows_after_header, source_config
            )
            norm_h = [normalize_header(h) for h in raw_h]
            per_sheet.append((sheet_name, raw_h, norm_h, rows, actual_hr))

        if target_columns:
            if source_config is None:
                raise ValueError(
                    "source_config is required when target_columns are used "
                    "for multi-sheet combine"
                )

            combined_rows: list[dict[str, Any]] = []
            missing_by_sheet: dict[str, list[str]] = {}

            for sheet_name, raw_h, norm_h, rows, actual_hr in per_sheet:
                _, projected_rows, missing_targets = _project_rows_to_target_columns(
                    raw_h,
                    rows,
                    source_config,
                    target_columns,
                )
                if missing_targets:
                    missing_by_sheet[sheet_name] = missing_targets
                combined_rows.extend(projected_rows)
                sheet_meta["sheets_read"].append({
                    "name": sheet_name,
                    "rows": len(rows),
                    "header_row_detected": actual_hr,
                    "cols_total": len(norm_h),
                    "cols_non_unnamed": len([
                        c for c in norm_h if not c.startswith("_unnamed_")
                    ]),
                    "missing_target_columns": missing_targets,
                })

            if missing_by_sheet:
                print(f"[INFO] Combining {len(per_sheet)} sheets using target columns. "
                      f"Missing columns are filled with nulls where absent.")
                for sheet_name, missing_cols in missing_by_sheet.items():
                    print(f"       Sheet '{sheet_name}' missing columns: {missing_cols}")

            sheet_meta["combine_mode"] = "target_columns_fill_missing"
            sheet_meta["column_reordered"] = True
            sheet_meta["combine_column_count"] = len(target_columns)
            sheet_meta["combine_column_order"] = [
                normalize_header(c) for c in target_columns
            ]
            if missing_by_sheet:
                sheet_meta["combine_missing_columns_by_sheet"] = missing_by_sheet

            return list(target_columns), combined_rows, sheet_meta

        real_col_sets = []
        for _, _, norm_h, _, _ in per_sheet:
            real_cols = {c for c in norm_h if not c.startswith("_unnamed_")}
            real_col_sets.append(real_cols)

        common_cols = real_col_sets[0]
        for cols in real_col_sets[1:]:
            common_cols = common_cols & cols

        first_norm = per_sheet[0][2]
        canonical_order = [c for c in first_norm if c in common_cols]

        all_cols_union = set()
        for cols in real_col_sets:
            all_cols_union |= cols
        dropped_cols = all_cols_union - common_cols
        if dropped_cols:
            print(f"[INFO] Combining {len(per_sheet)} sheets. "
                  f"Common columns: {len(common_cols)}, "
                  f"dropped (not in all sheets): {dropped_cols}")
            sheet_meta["combine_dropped_columns"] = sorted(dropped_cols)

        first_raw = per_sheet[0][1]
        first_norm_h = per_sheet[0][2]
        raw_headers_out = [
            first_raw[i] for i, c in enumerate(first_norm_h) if c in common_cols
        ]

        combined_rows: list[dict[str, Any]] = []
        for sheet_name, _, norm_h, rows, actual_hr in per_sheet:
            sheet_meta["sheets_read"].append({
                "name": sheet_name,
                "rows": len(rows),
                "header_row_detected": actual_hr,
                "cols_total": len(norm_h),
                "cols_non_unnamed": len([
                    c for c in norm_h if not c.startswith("_unnamed_")
                ]),
            })
            for row in rows:
                projected: dict[str, Any] = {}
                for col in canonical_order:
                    projected[col] = row.get(col)
                combined_rows.append(projected)

        sheet_meta["combine_column_count"] = len(canonical_order)
        sheet_meta["combine_column_order"] = canonical_order
        return raw_headers_out, combined_rows, sheet_meta

    finally:
        wb.close()

def read_csv_rows(
    file_path: Path,
    header_row: int = 0,
    skip_rows_after_header: int = 0,
    encoding: str | None = None,
) -> tuple[list[str], list[dict[str, Any]], dict]:
    """Read a CSV file and return (raw_headers, list_of_row_dicts, meta).

    Auto-detects encoding if not specified: UTF-8 → GBK → Latin-1.
    """
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "gbk", "latin-1"]

    content: str | None = None
    for enc in encodings:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if content is None:
        raise UnicodeError(
            f"Could not decode '{file_path.name}' with any of {encodings}"
        )

    lines = content.splitlines()
    if not lines:
        return [], [], {"sheets_read": []}

    reader = csv.reader(lines)
    all_rows = list(reader)

    if len(all_rows) <= header_row:
        return [], [], {"sheets_read": []}

    raw_headers = all_rows[header_row]
    norm_headers = [normalize_header(h) for h in raw_headers]

    data_start = header_row + 1 + skip_rows_after_header
    rows: list[dict[str, Any]] = []
    for row_values in all_rows[data_start:]:
        if not any(v.strip() for v in row_values if v):
            continue
        row_dict: dict[str, Any] = {}
        for col_idx, value in enumerate(row_values):
            if col_idx < len(norm_headers):
                row_dict[norm_headers[col_idx]] = value if value else None
        rows.append(row_dict)

    meta = {"sheets_read": [{"name": "csv", "rows": len(rows)}]}
    return raw_headers, rows, meta


def read_source_file(
    file_path: Path,
    source_config: dict,
    *,
    columns_override: list[str] | None = None,
    header_row_override: int | None = None,
    sheets_override: list[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]], dict]:
    """Dispatch to Excel or CSV reader, then apply column filtering.

    Returns (raw_headers, row_dicts, sheet_meta).

    Args:
        file_path: Path to data file.
        source_config: Source config block from masking_rules.yaml.
        columns_override: CLI override for columns_keep (if provided).
        header_row_override: CLI override for header_row (if provided).
        sheets_override: CLI override for sheet names (if provided).
    """
    header_row = _resolve_header_row_config(
        header_row_override,
        source_config.get("header_row", 0),
    )
    skip_rows = source_config.get("skip_rows_after_header", 0)
    suffix = file_path.suffix.lower()
    columns_keep = columns_override or source_config.get("columns_keep")
    combine_sheets = source_config.get("combine_sheets", False)
    used_target_projection = False

    sheet_selector = source_config.get("sheet_selector")
    if sheets_override:
        sheet_selector = {"mode": "name", "value": sheets_override}

    if suffix == ".xls":
        raise ValueError(f"{LEGACY_XLS_CONVERSION_HINT} File: {file_path.name}")

    if suffix == ".xlsx":
        requested_target_projection = bool(combine_sheets and columns_keep)
        raw_headers, rows, sheet_meta = read_excel_rows(
            file_path,
            sheet_selector=sheet_selector,
            header_row=header_row,
            skip_rows_after_header=skip_rows,
            combine_sheets=combine_sheets,
            source_config=source_config if requested_target_projection else None,
            target_columns=columns_keep if requested_target_projection else None,
        )
        used_target_projection = sheet_meta.get("combine_mode") == "target_columns_fill_missing"
    elif suffix == ".csv":
        raw_headers, rows, sheet_meta = read_csv_rows(
            file_path,
            header_row=header_row,
            skip_rows_after_header=skip_rows,
            encoding=source_config.get("csv_encoding"),
        )
    else:
        raise ValueError(f"Unsupported file format: '{suffix}' for {file_path}")

    if columns_keep and not used_target_projection:
        raw_headers, rows, sheet_meta = _apply_columns_keep(
            raw_headers, rows, columns_keep, sheet_meta, source_config
        )
    elif columns_keep and used_target_projection:
        sheet_meta["columns_keep_applied"] = True
        sheet_meta["columns_kept"] = len(columns_keep)
        sheet_meta["columns_keep_mode"] = "target_projection"

    raw_headers, rows = _drop_unnamed_columns(raw_headers, rows)
    return raw_headers, rows, sheet_meta


def _resolve_header_row_config(
    header_row_override: int | None,
    configured_header_row: Any,
) -> int | None:
    """Resolve header_row config; None means auto-detect."""
    if header_row_override is not None:
        return header_row_override
    if configured_header_row is None:
        return None
    if isinstance(configured_header_row, str):
        value = configured_header_row.strip().lower()
        if value in {"auto", "detect"}:
            return None
        return int(value)
    return int(configured_header_row)

def _apply_columns_keep(
    raw_headers: list[str],
    rows: list[dict[str, Any]],
    columns_keep: list[str],
    sheet_meta: dict,
    source_config: dict,
) -> tuple[list[str], list[dict], dict]:
    """Project rows to columns_keep in config order and fill missing columns."""
    header_res = resolve_headers(raw_headers, source_config)
    norm_headers = [normalize_header(h) for h in raw_headers]
    target_pairs = [(name, normalize_header(name)) for name in columns_keep]

    target_to_source: dict[str, str] = {}
    for actual_norm in norm_headers:
        rule_name = header_res.mapping.get(actual_norm)
        if rule_name:
            target_to_source.setdefault(normalize_header(rule_name), actual_norm)
        target_to_source.setdefault(actual_norm, actual_norm)

    missing_targets = [
        original for original, target_norm in target_pairs
        if target_norm not in target_to_source
    ]
    matched_targets = len(target_pairs) - len(missing_targets)
    if target_pairs and matched_targets == 0:
        raise ValueError(
            "columns_keep matched 0 configured columns for this file. "
            "This usually means the configured header_row is wrong or the "
            "source headers need column_aliases. Run inspect/dry-run first "
            "and update the source config before formal masking."
        )

    filtered_headers = list(columns_keep)
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        projected: dict[str, Any] = {}
        for original, target_norm in target_pairs:
            source_key = target_to_source.get(target_norm)
            projected[target_norm] = row.get(source_key) if source_key else None
        filtered_rows.append(projected)

    used_source_keys = {
        source_key for _, target_norm in target_pairs
        for source_key in [target_to_source.get(target_norm)]
        if source_key
    }
    dropped_count = len([
        norm for norm in norm_headers
        if not norm.startswith("_unnamed_") and norm not in used_source_keys
    ])

    print(f"[INFO] columns_keep: output {len(filtered_headers)} columns, "
          f"matched {matched_targets}, filled missing {len(missing_targets)}")
    if missing_targets:
        print(f"[INFO] columns_keep: filled missing columns with nulls: {missing_targets}")

    sheet_meta["columns_keep_applied"] = True
    sheet_meta["columns_kept"] = len(filtered_headers)
    sheet_meta["columns_dropped"] = dropped_count
    if missing_targets:
        sheet_meta["columns_filled_with_null"] = missing_targets

    return filtered_headers, filtered_rows, sheet_meta

def _drop_unnamed_columns(
    raw_headers: list[str],
    rows: list[dict[str, Any]],
) -> tuple[list[str], list[dict]]:
    """Remove columns whose normalized name starts with _unnamed_."""
    norm_headers = [normalize_header(h) for h in raw_headers]
    unnamed = {n for n in norm_headers if n.startswith("_unnamed_")}
    if not unnamed:
        return raw_headers, rows

    filtered_headers = [h for h, n in zip(raw_headers, norm_headers)
                        if n not in unnamed]
    filtered_rows: list[dict] = []
    for row in rows:
        filtered_rows.append({k: v for k, v in row.items() if k not in unnamed})

    print(f"[INFO] Dropped {len(unnamed)} unnamed/empty columns")
    return filtered_headers, filtered_rows


# ── Output writing ───────────────────────────────────────────────────────────

def write_json_output(rows: list[dict], output_path: Path) -> None:
    """Write masked rows to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)


def write_json_document(document: Any, output_path: Path) -> None:
    """Write a generic JSON document to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=2, default=str)


SALT_REQUIRED_ACTIONS = {"tokenize", "hash"}


def _collect_columns_requiring_salt(
    raw_headers: list[str],
    *,
    source_config: dict,
    rules: dict,
    header_resolution: HeaderResolution,
) -> list[str]:
    """Return actual columns whose resolved actions require a masking salt."""
    required: list[str] = []
    seen: set[str] = set()

    for col_name in raw_headers:
        norm = normalize_header(col_name)
        rule_name = header_resolution.mapping.get(norm)
        col_rule = resolve_column_rule(
            col_name,
            source_config,
            rules,
            rule_name_override=rule_name,
        )
        actions = {
            col_rule.get("canonical_action", "passthrough"),
            col_rule.get("serving_action", "passthrough"),
        }
        if actions & SALT_REQUIRED_ACTIONS:
            display_name = rule_name or col_name
            if display_name not in seen:
                seen.add(display_name)
                required.append(display_name)

    return required


def _ensure_masking_salt_available(
    source_name: str,
    raw_headers: list[str],
    *,
    source_config: dict,
    rules: dict,
    header_resolution: HeaderResolution,
) -> None:
    """Fail fast when the current source actually needs a masking salt."""
    required_columns = _collect_columns_requiring_salt(
        raw_headers,
        source_config=source_config,
        rules=rules,
        header_resolution=header_resolution,
    )
    if not required_columns:
        return

    salt_env_var = rules.get("tokenizer", {}).get(
        "salt_env_var",
        "FAULTDX_MASKING_SALT",
    )
    if os.environ.get(salt_env_var):
        return

    raise EnvironmentError(
        f"{salt_env_var} is not set. Source '{source_name}' requires it "
        f"because these columns use tokenize/hash: {required_columns}. "
        f"Set it in your .env or shell environment before running dry-run "
        f"or full masking. --inspect does not require it."
    )


# ── Main processing pipeline ────────────────────────────────────────────────


def _apply_name_mapping_to_sheet_meta(
    sheet_meta: dict[str, Any],
    mapping_registry,
) -> dict[str, int]:
    """Apply sheetname-scope mapping to sheet metadata in place."""
    replacements = 0
    sheets_touched = 0

    for sheet_info in sheet_meta.get("sheets_read", []):
        original_name = sheet_info.get("name")
        mapped_name, summary = mapping_registry.apply_text(
            original_name,
            scope="sheetname",
        )
        if not summary["applied"]:
            continue

        sheet_info["name"] = mapped_name
        sheet_info["name_mapping_replacements"] = summary["replacements"]
        replacements += summary["replacements"]
        sheets_touched += 1

    return {
        "sheetname_replacements": replacements,
        "sheetname_sheets_touched": sheets_touched,
    }


def _print_name_mapping_summary(report: dict[str, Any] | None) -> None:
    """Print a concise preprocessing summary when name mapping is enabled."""
    if not report or not report.get("applied"):
        return

    mapping_name = Path(report["mapping_file"]).name
    print(
        f"[INFO] Name mapping enabled: {mapping_name} "
        f"({report['enabled_rules']} enabled rules)"
    )
    print(
        f"       filename replacements={report['filename_replacements']} "
        f"across {report['filename_files_touched']} file(s); "
        f"sheetname replacements={report['sheetname_replacements']} "
        f"across {report['sheetname_sheets_touched']} sheet(s); "
        f"content replacements={report['content_replacements']} "
        f"across {report['content_rows_touched']} row(s)"
    )
    print(
        f"       QPL enriched rows={report['qpl_rows_enriched']} "
        f"with {report['qpl_values_assigned']} assigned value(s)"
    )
    if report.get("content_rule_profile_hits"):
        profile_summary = ", ".join(
            f"{profile} x{count}"
            for profile, count in sorted(
                report["content_rule_profile_hits"].items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        )
        print(f"       content rule profiles={profile_summary}")


def _values_equal_for_filter(left: Any, right: Any) -> bool:
    """Compare filter values with string-safe normalization."""
    if isinstance(left, str) and isinstance(right, str):
        return left.strip().casefold() == right.strip().casefold()
    return left == right


def _build_row_reference(row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Build a compact row reference for governance history output."""
    record_ids: dict[str, Any] = {}
    for candidate in ('??', 'Index', 'index'):
        normalized = normalize_header(candidate)
        if normalized in row and row.get(normalized) not in (None, ''):
            record_ids[candidate] = row.get(normalized)

    return {
        'source_file': context.get('source_file'),
        'source_row_in_file': context.get('source_row_in_file'),
        'record_ids': record_ids,
    }


def _apply_governance(
    rows: list[dict[str, Any]],
    *,
    row_contexts: list[dict[str, Any]],
    source_config: dict,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Apply post-mapping governance rules before masking.

    Name mapping runs first so filters and dedupe operate on canonical local
    labels. Governance history stores compact row references, not raw row dumps.
    """
    governance = source_config.get('governance', {})
    if not governance:
        return rows, row_contexts, None, None

    report: dict[str, Any] = {
        'applied': True,
        'rows_before': len(rows),
        'rows_after_filter': len(rows),
        'rows_after_dedupe': len(rows),
        'rows_filtered_out': 0,
        'rows_deduped': 0,
        'filter_equals': [],
        'dedupe': None,
    }
    history: dict[str, Any] = {
        'filter': {
            'rules': [],
            'removed_rows': [],
        },
        'dedupe': {
            'exclude_columns': [],
            'duplicate_groups': [],
        },
    }

    paired_rows: list[tuple[dict[str, Any], dict[str, Any]]] = list(zip(rows, row_contexts))

    filter_equals = governance.get('filter_equals', {})
    if filter_equals:
        normalized_filters = {
            normalize_header(column_name): expected_value
            for column_name, expected_value in filter_equals.items()
        }
        kept_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for row, context in paired_rows:
            matched = all(
                _values_equal_for_filter(row.get(column_name), expected_value)
                for column_name, expected_value in normalized_filters.items()
            )
            if matched:
                kept_rows.append((row, context))
                continue

            history['filter']['removed_rows'].append({
                'reference': _build_row_reference(row, context),
                'row_excerpt': {
                    column_name: row.get(normalize_header(column_name))
                    for column_name in filter_equals.keys()
                },
            })

        paired_rows = kept_rows
        report['rows_after_filter'] = len(paired_rows)
        report['rows_filtered_out'] = report['rows_before'] - len(paired_rows)
        report['filter_equals'] = [
            {'column': column_name, 'value': expected_value}
            for column_name, expected_value in filter_equals.items()
        ]
        history['filter']['rules'] = report['filter_equals']

    dedupe_config = governance.get('dedupe', {})
    if dedupe_config.get('enabled'):
        exclude_columns = [
            normalize_header(column_name)
            for column_name in dedupe_config.get('exclude_columns', [])
        ]
        seen_keys: dict[tuple[tuple[str, str], ...], tuple[dict[str, Any], dict[str, Any]]] = {}
        deduped_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for row, context in paired_rows:
            key_items = tuple(
                sorted(
                    (column_name, json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
                    for column_name, value in row.items()
                    if column_name not in exclude_columns
                )
            )
            if key_items in seen_keys:
                kept_row, kept_context = seen_keys[key_items]
                history['dedupe']['duplicate_groups'].append({
                    'kept': _build_row_reference(kept_row, kept_context),
                    'dropped': _build_row_reference(row, context),
                })
                continue
            seen_keys[key_items] = (row, context)
            deduped_rows.append((row, context))

        report['rows_after_dedupe'] = len(deduped_rows)
        report['rows_deduped'] = len(paired_rows) - len(deduped_rows)
        report['dedupe'] = {
            'exclude_columns': dedupe_config.get('exclude_columns', []),
            'keep': dedupe_config.get('keep', 'first'),
        }
        history['dedupe']['exclude_columns'] = dedupe_config.get('exclude_columns', [])
        paired_rows = deduped_rows

    processed_rows = [row for row, _ in paired_rows]
    processed_contexts = [context for _, context in paired_rows]
    return processed_rows, processed_contexts, report, history


def _print_governance_summary(report: dict[str, Any] | None) -> None:
    """Print a concise governance summary when filter/dedupe is enabled."""
    if not report or not report.get("applied"):
        return

    print(
        "[INFO] Governance applied: "
        f"rows_before={report['rows_before']}, "
        f"after_filter={report['rows_after_filter']}, "
        f"after_dedupe={report['rows_after_dedupe']}"
    )
    if report.get("rows_filtered_out"):
        print(f"       filtered_out={report['rows_filtered_out']}")
    if report.get("rows_deduped"):
        print(f"       deduped={report['rows_deduped']}")


def _manifest_path_label(path: Path, root: Path) -> str:
    """Return a portable manifest path without a machine-local root."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


class StructuredMaskingResult:
    """Container for the results of a structured masking run."""

    def __init__(self):
        self.run_id: str = ""
        self.source_name: str = ""
        self.input_files: list[Path] = []
        self.input_file_labels: list[str] = []
        self.raw_headers: list[str] = []
        self.header_resolution: HeaderResolution | None = None
        self.input_row_count: int = 0
        self.input_col_count: int = 0
        self.canonical_rows: list[dict] = []
        self.serving_rows: list[dict] = []
        self.canonical_path: Path | None = None
        self.serving_path: Path | None = None
        self.manifest_path: Path | None = None
        self.lineage_path: Path | None = None
        self.review_flag_columns: list[str] = []
        self.sheet_meta: dict = {}
        self.name_mapping_report: dict[str, Any] | None = None
        self.governance_report: dict[str, Any] | None = None
        self.governance_history_path: Path | None = None

    def print_summary(self) -> None:
        """Print a human-readable summary of the masking run."""
        print()
        print("=" * 70)
        print(f"  Structured Masking Complete: {self.source_name}")
        print("=" * 70)
        print(f"  Run ID:           {self.run_id}")
        labels = self.input_file_labels or [p.name for p in self.input_files]
        print(f"  Input files:      {labels}")
        sheets_read = self.sheet_meta.get("sheets_read", [])
        if sheets_read:
            sheet_desc = ", ".join(
                f"'{s['name']}'({s['rows']})" for s in sheets_read
            )
            print(f"  Sheets read:      {sheet_desc}")
            if self.sheet_meta.get("column_reordered"):
                print(f"  Column reorder:   YES (aligned to first sheet order)")
        print(f"  Input rows:       {self.input_row_count}")
        print(f"  Input columns:    {self.input_col_count}")
        print(f"  Canonical rows:   {len(self.canonical_rows)}")
        print(f"  Canonical cols:   {len(self.canonical_rows[0]) if self.canonical_rows else 0}")
        print(f"  Serving rows:     {len(self.serving_rows)}")
        print(f"  Serving cols:     {len(self.serving_rows[0]) if self.serving_rows else 0}")
        if self.review_flag_columns:
            print(f"  Review needed:    {self.review_flag_columns}")
        print(f"  Canonical output: {self.canonical_path}")
        print(f"  Serving output:   {self.serving_path}")
        if self.name_mapping_report and self.name_mapping_report.get("applied"):
            print(
                f"  Name mapping:     {Path(self.name_mapping_report['mapping_file']).name} "
                f"({self.name_mapping_report['enabled_rules']} enabled rules)"
            )
        if self.governance_report and self.governance_report.get("applied"):
            print(
                f"  Governance:       filter->dedupe "
                f"({self.governance_report['rows_before']} -> "
                f"{self.governance_report['rows_after_filter']} -> "
                f"{self.governance_report['rows_after_dedupe']})"
            )
        if self.governance_history_path:
            print(f"  Governance log:   {self.governance_history_path}")
        print(f"  Manifest:         {self.manifest_path}")
        print(f"  Lineage:          {self.lineage_path}")
        print()


def run_structured_masking(
    *,
    source_name: str,
    rules: dict,
    raw_dir: Path,
    output_base: Path,
    dry_run: bool = False,
    preview_rows: int = 5,
    sheets_override: list[str] | None = None,
    columns_override: list[str] | None = None,
    header_row_override: int | None = None,
    file_patterns_override: list[str] | None = None,
    apply_name_mapping: bool = False,
    name_mapping_path: Path | None = None,
    run_id: str | None = None,
) -> StructuredMaskingResult:
    """Execute the full structured masking pipeline for one source.

    The order is deliberate: local name mapping, governance filtering/dedupe,
    then canonical/serving masking. This keeps audit decisions close to the
    source rows while preventing raw values from leaking into serving output.
    """
    source_config = get_source_config(rules, source_name)
    result = StructuredMaskingResult()
    result.run_id = run_id or make_run_id()
    result.source_name = source_name

    mapping_registry = None
    name_mapping_report: dict[str, Any] | None = None
    content_mapping_columns = source_config.get("name_mapping", {}).get(
        "content_columns",
        [],
    )
    if apply_name_mapping:
        resolved_mapping_path = resolve_name_mapping_path(raw_dir, name_mapping_path)
        mapping_registry = load_name_mapping(resolved_mapping_path)
        name_mapping_report = {
            "applied": True,
            "mapping_file": str(resolved_mapping_path),
            "enabled_rules": mapping_registry.rule_count,
            "scopes_available": mapping_registry.scopes,
            "content_columns_configured": list(content_mapping_columns),
            "filename_replacements": 0,
            "filename_files_touched": 0,
            "sheetname_replacements": 0,
            "sheetname_sheets_touched": 0,
            "content_replacements": 0,
            "content_rows_touched": 0,
            "content_cells_touched": 0,
            "content_columns_touched": {},
            "content_rule_profile_hits": {},
            "qpl_rows_enriched": 0,
            "qpl_values_assigned": 0,
        }
        result.name_mapping_report = name_mapping_report

    file_patterns = file_patterns_override or source_config.get("file_patterns", [])
    source_files = find_source_files(
        file_patterns,
        raw_dir,
        require_all_patterns=bool(source_config.get("require_all_file_patterns", False)),
    )
    result.input_files = source_files
    print(f"[INFO] Found {len(source_files)} file(s): "
          f"{[f.name for f in source_files]}")

    all_rows: list[dict[str, Any]] = []
    all_row_contexts: list[dict[str, Any]] = []
    canonical_headers: list[str] | None = None
    input_file_labels: list[str] = []
    combined_sheet_meta: dict[str, Any] = {
        "files_read": [],
        "sheets_read": [],
        "per_file": {},
    }

    for file_path in source_files:
        display_file_name = file_path.name
        if mapping_registry and name_mapping_report:
            display_file_name, file_name_summary = mapping_registry.apply_text(
                file_path.name,
                scope="filename",
            )
            if file_name_summary["applied"]:
                name_mapping_report["filename_replacements"] += file_name_summary["replacements"]
                name_mapping_report["filename_files_touched"] += 1

        file_raw_headers, file_rows, file_sheet_meta = read_source_file(
            file_path,
            source_config,
            columns_override=columns_override,
            header_row_override=header_row_override,
            sheets_override=sheets_override,
        )

        if mapping_registry and name_mapping_report:
            sheet_summary = _apply_name_mapping_to_sheet_meta(
                file_sheet_meta,
                mapping_registry,
            )
            name_mapping_report["sheetname_replacements"] += sheet_summary["sheetname_replacements"]
            name_mapping_report["sheetname_sheets_touched"] += sheet_summary["sheetname_sheets_touched"]

            file_rows, content_summary = apply_content_name_mapping(
                file_rows,
                content_columns=content_mapping_columns,
                registry=mapping_registry,
            )
            name_mapping_report["content_replacements"] += content_summary["content_replacements"]
            name_mapping_report["content_rows_touched"] += content_summary["content_rows_touched"]
            name_mapping_report["content_cells_touched"] += content_summary["content_cells_touched"]
            for profile, count in content_summary["content_rule_profile_hits"].items():
                name_mapping_report["content_rule_profile_hits"][profile] = (
                    name_mapping_report["content_rule_profile_hits"].get(profile, 0)
                    + count
                )
            name_mapping_report["qpl_rows_enriched"] += content_summary["qpl_rows_enriched"]
            name_mapping_report["qpl_values_assigned"] += content_summary["qpl_values_assigned"]
            for column_name, count in content_summary["content_columns_touched"].items():
                name_mapping_report["content_columns_touched"][column_name] = (
                    name_mapping_report["content_columns_touched"].get(column_name, 0)
                    + count
                )

        if canonical_headers is None:
            canonical_headers = list(file_raw_headers)
        else:
            canonical_norm = [normalize_header(h) for h in canonical_headers]
            file_norm = [normalize_header(h) for h in file_raw_headers]
            if file_norm != canonical_norm:
                if columns_override or source_config.get("columns_keep"):
                    aligned_rows: list[dict[str, Any]] = []
                    for row in file_rows:
                        aligned_rows.append({
                            norm_key: row.get(norm_key) for norm_key in canonical_norm
                        })
                    file_rows = aligned_rows
                    file_raw_headers = list(canonical_headers)
                    file_sheet_meta["multi_file_aligned_to_first"] = True
                    file_sheet_meta["multi_file_missing_columns"] = [
                        hdr for hdr in canonical_headers if normalize_header(hdr) not in file_norm
                    ]
                    file_sheet_meta["multi_file_extra_columns"] = [
                        hdr for hdr in file_raw_headers if normalize_header(hdr) not in canonical_norm
                    ]
                else:
                    raise ValueError(
                        f"Schema mismatch across source files for '{source_name}'. "
                        f"First file columns={canonical_headers}, current file "
                        f"columns={file_raw_headers}"
                    )

        all_rows.extend(file_rows)
        all_row_contexts.extend([
            {
                "source_file": display_file_name,
                "source_row_in_file": row_index + 1,
            }
            for row_index, _ in enumerate(file_rows)
        ])
        input_file_labels.append(display_file_name)
        combined_sheet_meta["files_read"].append({
            "name": display_file_name,
            "rows": len(file_rows),
            "columns": len(file_raw_headers),
        })
        per_file_key = display_file_name
        duplicate_index = 2
        while per_file_key in combined_sheet_meta["per_file"]:
            per_file_key = f"{display_file_name}#{duplicate_index}"
            duplicate_index += 1
        combined_sheet_meta["per_file"][per_file_key] = {
            k: v for k, v in file_sheet_meta.items() if k != "sheets_read"
        }
        for sheet_info in file_sheet_meta.get("sheets_read", []):
            sheet_record = dict(sheet_info)
            sheet_record["file"] = display_file_name
            combined_sheet_meta["sheets_read"].append(sheet_record)

    result.raw_headers = canonical_headers or []
    governance_rows, governance_contexts, governance_report, governance_history = _apply_governance(
        all_rows,
        row_contexts=all_row_contexts,
        source_config=source_config,
    )
    all_rows = governance_rows
    all_row_contexts = governance_contexts
    result.input_file_labels = input_file_labels
    result.input_row_count = len(all_rows)
    result.input_col_count = len(result.raw_headers)
    result.sheet_meta = combined_sheet_meta
    result.governance_report = governance_report

    if len(source_files) == 1:
        display_name = input_file_labels[0] if input_file_labels else source_files[0].name
        print(f"[INFO] Read {len(all_rows)} rows, {len(result.raw_headers)} columns "
              f"from {display_name}")
    else:
        print(f"[INFO] Read {len(all_rows)} rows, {len(result.raw_headers)} columns "
              f"from {len(source_files)} file(s)")
        for file_info in combined_sheet_meta["files_read"]:
            print(f"       File '{file_info['name']}': {file_info['rows']} rows")

    for sheet_info in combined_sheet_meta.get("sheets_read", []):
        if "file" in sheet_info:
            print(f"       File '{sheet_info['file']}' / Sheet '{sheet_info['name']}': "
                  f"{sheet_info['rows']} rows")
        else:
            print(f"       Sheet '{sheet_info['name']}': {sheet_info['rows']} rows")

    header_res = resolve_headers(result.raw_headers, source_config)
    result.header_resolution = header_res
    header_res.print_report()

    for col_name in result.raw_headers:
        norm = normalize_header(col_name)
        rule_name = header_res.mapping.get(norm)
        col_rules = source_config.get("column_rules", {})
        if rule_name and rule_name in col_rules:
            if col_rules[rule_name].get("review_flag"):
                result.review_flag_columns.append(rule_name)

    _ensure_masking_salt_available(
        source_name,
        result.raw_headers,
        source_config=source_config,
        rules=rules,
        header_resolution=header_res,
    )

    _print_name_mapping_summary(name_mapping_report)
    _print_governance_summary(governance_report)

    if dry_run:
        _print_dry_run_preview(
            all_rows[:preview_rows],
            source_config=source_config,
            rules=rules,
            header_resolution=header_res,
            raw_value_label=("Preprocessed" if name_mapping_report else "Raw Value"),
        )
        return result

    canonical_rows: list[dict] = []
    serving_rows: list[dict] = []

    output_target = source_config.get("output_target", "processed")
    canonical_dir = output_base / "processed" / "canonical" / "structured" / source_name
    if output_target == "eval":
        serving_dir = output_base / "eval"
    else:
        serving_dir = output_base / "processed" / "serving" / "structured"
    manifest_dir = canonical_dir / "_manifests"
    lineage_dir = canonical_dir / "_lineage"
    governance_dir = canonical_dir / "_governance"

    with LineageWriter(source_name, lineage_dir, run_id=result.run_id) as lw:
        for row_idx, row in enumerate(all_rows):
            c_row, c_log = mask_row(
                row,
                source_config=source_config,
                rules=rules,
                view="canonical",
                header_resolution=header_res,
            )
            canonical_rows.append(c_row)
            for entry in c_log:
                lw.record(
                    row_index=row_idx,
                    column_name=entry["column"],
                    level=entry["level"],
                    action=entry["action"],
                    detail=entry["detail"],
                    view="canonical",
                    review_flag=entry.get("review_flag", False),
                )

            s_row, s_log = mask_row(
                row,
                source_config=source_config,
                rules=rules,
                view="serving",
                header_resolution=header_res,
            )
            serving_rows.append(s_row)
            for entry in s_log:
                lw.record(
                    row_index=row_idx,
                    column_name=entry["column"],
                    level=entry["level"],
                    action=entry["action"],
                    detail=entry["detail"],
                    view="serving",
                    review_flag=entry.get("review_flag", False),
                )

        result.lineage_path = lw.path

    result.canonical_rows = canonical_rows
    result.serving_rows = serving_rows

    if governance_history:
        governance_document = {
            "run_id": result.run_id,
            "source_name": source_name,
            "input_files": result.input_file_labels or [p.name for p in source_files],
            "governance": governance_report,
            "history": governance_history,
        }
        governance_path = governance_dir / f"{source_name}_governance.json"
        write_json_document(governance_document, governance_path)
        result.governance_history_path = governance_path

    canonical_path = canonical_dir / f"{source_name}_canonical.json"
    serving_path = serving_dir / f"{source_name}_serving.json"
    write_json_output(canonical_rows, canonical_path)
    write_json_output(serving_rows, serving_path)
    result.canonical_path = canonical_path
    result.serving_path = serving_path

    manifest_root = output_base.parent
    manifest_extra = {
        "header_normalization": header_res.to_dict(),
        "sheet_meta": combined_sheet_meta,
    }
    governance_ids = source_config.get("governance_ids", {})
    if governance_ids:
        manifest_extra["source_ids"] = dict(governance_ids)
    if name_mapping_report:
        manifest_extra["name_mapping"] = name_mapping_report
    if governance_report:
        manifest_extra["governance"] = governance_report
        if result.governance_history_path:
            manifest_extra["governance_history_path"] = _manifest_path_label(
                result.governance_history_path,
                manifest_root,
            )

    manifest = build_manifest(
        run_id=result.run_id,
        source_name=source_name,
        rules_version=rules.get("version", 0),
        input_files=source_files,
        input_file_labels=result.input_file_labels or None,
        input_row_count=len(all_rows),
        input_col_count=len(result.raw_headers),
        output_canonical_path=_manifest_path_label(
            canonical_path,
            manifest_root,
        ),
        output_serving_path=_manifest_path_label(
            serving_path,
            manifest_root,
        ),
        output_row_count=len(canonical_rows),
        output_col_count_canonical=len(canonical_rows[0]) if canonical_rows else 0,
        output_col_count_serving=len(serving_rows[0]) if serving_rows else 0,
        review_flag_columns=result.review_flag_columns,
        extra=manifest_extra,
    )
    result.manifest_path = write_manifest(manifest, manifest_dir)

    return result

def _print_dry_run_preview(
    rows: list[dict[str, Any]],
    *,
    source_config: dict,
    rules: dict,
    header_resolution: HeaderResolution,
    raw_value_label: str = "Raw Value",
) -> None:
    """Print before/after preview for a few rows."""
    if not rows:
        print("[DRY-RUN] No data rows to preview.")
        return

    print()
    print("=" * 90)
    print("  Data Preview (DRY-RUN)")
    print("=" * 90)

    for row_idx, row in enumerate(rows):
        print(f"\n--- Row {row_idx + 1} ---")
        print(f"{'Column':<26} {'Lv':<4} {raw_value_label:<24} "
              f"{'Canonical':<24} {'Serving':<20}")
        print("-" * 100)

        c_row, c_log = mask_row(
            row,
            source_config=source_config,
            rules=rules,
            view="canonical",
            header_resolution=header_resolution,
        )
        s_row, s_log = mask_row(
            row,
            source_config=source_config,
            rules=rules,
            view="serving",
            header_resolution=header_resolution,
        )

        for entry_c, entry_s in zip(c_log, s_log):
            col = entry_c["column"]
            level = entry_c["level"]
            raw_val = str(row.get(col, ""))[:22]
            c_val = str(c_row.get(entry_c.get("output_column", col), "[DROPPED]"))[:22]
            s_val = str(s_row.get(entry_s.get("output_column", col), "[DROPPED]"))[:18]
            review = " !" if entry_c.get("review_flag") else ""
            print(f"{col:<26} {level:<4} {raw_val:<24} {c_val:<24} {s_val:<20}{review}")

    print()
    print("[DRY-RUN] No files were written. Review above, then run without --dry-run.")
