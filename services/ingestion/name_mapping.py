"""Local name-mapping preprocessing for ingestion.

This module applies a user-maintained local mapping workbook *before* masking.
It is intended for sensitive name normalization such as customer/vendor/station
aliases that must not live in Git-tracked config files.
The workbook is resolved locally and should stay outside shared generated
artifacts unless a later governance task defines a sanitized source.

Supported scopes:
    - filename
    - sheetname
    - content

Supported match modes:
    - exact
    - contains

Matching behavior:
    - raw_name matching is case-insensitive for both exact and contains
    - matched values are always replaced with mapped_name as-is
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl

from services.ingestion.header_normalize import normalize_header


ALLOWED_SCOPES = {"filename", "sheetname", "content"}
ALLOWED_MATCH_MODES = {"exact", "contains"}
REQUIRED_HEADERS = {"raw_name", "mapped_name", "scope", "match_mode", "enabled"}

TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}
FALSEY_VALUES = {"0", "false", "no", "n", "off", ""}
NAME_MAPPING_ENV_VAR = "FAULTDX_NAME_MAPPING_FILE"


@dataclass(frozen=True)
class NameMappingRule:
    """One enabled mapping rule loaded from the local workbook."""

    raw_name: str
    mapped_name: str
    scopes: tuple[str, ...]
    match_mode: str
    enabled: bool
    note: str = ""
    qpl_values: tuple[int, ...] = ()
    index: int | None = None
    row_number: int = 0


class NameMappingRegistry:
    """In-memory registry of enabled name-mapping rules."""

    def __init__(self, *, path: Path, rules: list[NameMappingRule]):
        self.path = path
        self.rules = [rule for rule in rules if rule.enabled]
        self.rules_by_scope: dict[str, list[NameMappingRule]] = {
            scope: [rule for rule in self.rules if scope in rule.scopes]
            for scope in ALLOWED_SCOPES
        }

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    @property
    def scopes(self) -> list[str]:
        available = [
            scope for scope in sorted(ALLOWED_SCOPES)
            if self.rules_by_scope.get(scope)
        ]
        return available

    def apply_text(self, value: Any, *, scope: str) -> tuple[Any, dict[str, Any]]:
        """Apply rules for one scope to a single string-like value."""
        if scope not in ALLOWED_SCOPES:
            raise ValueError(
                f"Unsupported scope '{scope}'. Allowed: {sorted(ALLOWED_SCOPES)}"
            )

        summary = {
            "applied": False,
            "replacements": 0,
            "rules": [],
            "qpl_values": [],
            "rule_profiles": [],
        }
        if value is None or not isinstance(value, str) or not value:
            return value, summary

        current = value
        for rule in self.rules_by_scope.get(scope, []):
            if rule.match_mode == "exact":
                if current.casefold() == rule.raw_name.casefold():
                    current = rule.mapped_name
                    summary["applied"] = True
                    summary["replacements"] += 1
                    summary["rules"].append(rule.raw_name)
                    _append_rule_profile(summary, rule)
                    _extend_qpl_values(summary, rule)
                    break
            elif rule.match_mode == "contains":
                pattern = re.compile(re.escape(rule.raw_name), flags=re.IGNORECASE)
                current, count = pattern.subn(rule.mapped_name, current)
                if count:
                    summary["applied"] = True
                    summary["replacements"] += count
                    summary["rules"].append(rule.raw_name)
                    _append_rule_profile(summary, rule)
                    _extend_qpl_values(summary, rule)

        return current, summary


def resolve_name_mapping_path(
    raw_dir: Path,
    mapping_path: Path | None = None,
) -> Path:
    """Resolve the local mapping workbook path."""
    if mapping_path is not None:
        return mapping_path

    env_path = os.environ.get(NAME_MAPPING_ENV_VAR)
    if env_path:
        return Path(env_path)

    candidates = _default_name_mapping_candidates(raw_dir)
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def load_name_mapping(mapping_path: Path) -> NameMappingRegistry:
    """Load and validate the local mapping workbook."""
    if not mapping_path.exists():
        searched_paths = _format_candidate_paths(mapping_path)
        raise FileNotFoundError(
            "name mapping workbook not found. "
            f"Resolved path: {mapping_path}. "
            f"Searched: {searched_paths}. "
            f"Use --name-mapping-file or set {NAME_MAPPING_ENV_VAR}."
        )

    wb = openpyxl.load_workbook(mapping_path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header_row = next(rows, None)
        if not header_row:
            raise ValueError(
                f"name mapping workbook is empty: {mapping_path}"
            )

        header_map = _build_header_map(header_row)
        missing = REQUIRED_HEADERS - set(header_map.keys())
        if missing:
            raise ValueError(
                "name mapping workbook missing required columns: "
                f"{sorted(missing)}"
            )

        rules: list[NameMappingRule] = []
        for row_number, row in enumerate(rows, start=2):
            raw_name = _get_cell_value(row, header_map.get("raw_name"))
            mapped_name = _get_cell_value(row, header_map.get("mapped_name"))
            scope_text = _get_cell_value(row, header_map.get("scope"))
            match_mode = _get_cell_value(row, header_map.get("match_mode")).lower()
            enabled_text = _get_cell_value(row, header_map.get("enabled"))
            note = _get_cell_value(row, header_map.get("note"))
            qpl_text = _get_cell_value(row, header_map.get("qpl"))
            index_text = _get_cell_value(row, header_map.get("index"))

            if not any([
                raw_name, mapped_name, scope_text, match_mode, enabled_text, note
            ]):
                continue

            if not raw_name:
                raise ValueError(
                    f"name mapping row {row_number}: raw_name is required"
                )
            if not mapped_name:
                raise ValueError(
                    f"name mapping row {row_number}: mapped_name is required"
                )

            scopes = _parse_scopes(scope_text, row_number)
            parsed_match_mode = _parse_match_mode(match_mode, row_number)
            enabled = _parse_enabled(enabled_text, row_number)
            qpl_values = _parse_qpl_values(qpl_text, row_number)
            index_value = _parse_optional_index(index_text, row_number)

            rules.append(NameMappingRule(
                raw_name=raw_name,
                mapped_name=mapped_name,
                scopes=scopes,
                match_mode=parsed_match_mode,
                enabled=enabled,
                note=note,
                qpl_values=qpl_values,
                index=index_value,
                row_number=row_number,
            ))
    finally:
        wb.close()

    sorted_rules = sorted(
        rules,
        key=lambda rule: (
            rule.index is None,
            rule.index if rule.index is not None else rule.row_number,
            rule.row_number,
        ),
    )
    return NameMappingRegistry(path=mapping_path, rules=sorted_rules)


def apply_content_name_mapping(
    rows: list[dict[str, Any]],
    *,
    content_columns: list[str],
    registry: NameMappingRegistry,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply content-scope mapping to configured structured columns only."""
    normalized_columns = [normalize_header(col) for col in content_columns]
    report = {
        "content_columns_configured": list(content_columns),
        "content_rows_touched": 0,
        "content_cells_touched": 0,
        "content_replacements": 0,
        "content_columns_touched": {},
        "content_rule_profile_hits": {},
        "qpl_rows_enriched": 0,
        "qpl_values_assigned": 0,
    }
    if not normalized_columns:
        return rows, report

    mapped_rows: list[dict[str, Any]] = []
    for row in rows:
        mapped_row = dict(row)
        row_touched = False
        row_qpl_values: set[int] = set(_coerce_existing_qpl_values(mapped_row.get("QPL")))
        for column_name in normalized_columns:
            if column_name not in mapped_row:
                continue
            mapped_value, summary = registry.apply_text(
                mapped_row[column_name],
                scope="content",
            )
            if not summary["applied"]:
                continue

            mapped_row[column_name] = mapped_value
            row_touched = True
            report["content_cells_touched"] += 1
            report["content_replacements"] += summary["replacements"]
            report["content_columns_touched"][column_name] = (
                report["content_columns_touched"].get(column_name, 0)
                + summary["replacements"]
            )
            for profile in summary["rule_profiles"]:
                report["content_rule_profile_hits"][profile] = (
                    report["content_rule_profile_hits"].get(profile, 0)
                    + 1
                )
            row_qpl_values.update(summary["qpl_values"])

        if row_touched:
            report["content_rows_touched"] += 1
        if row_qpl_values:
            mapped_row["QPL"] = sorted(row_qpl_values)
            report["qpl_rows_enriched"] += 1
            report["qpl_values_assigned"] += len(row_qpl_values)
        mapped_rows.append(mapped_row)

    return mapped_rows, report


def _build_header_map(header_row: tuple[Any, ...]) -> dict[str, int]:
    header_map: dict[str, int] = {}
    for idx, cell_value in enumerate(header_row):
        header = str(cell_value).strip().lower() if cell_value is not None else ""
        if header:
            header_map[header] = idx
    return header_map


def _get_cell_value(row: tuple[Any, ...], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    value = row[index]
    return str(value).strip() if value is not None else ""


def _parse_scopes(scope_text: str, row_number: int) -> tuple[str, ...]:
    scopes = tuple(
        scope.strip().lower()
        for scope in scope_text.split(",")
        if scope.strip()
    )
    if not scopes:
        raise ValueError(
            f"name mapping row {row_number}: scope is required"
        )
    invalid = sorted(set(scopes) - ALLOWED_SCOPES)
    if invalid:
        raise ValueError(
            f"name mapping row {row_number}: invalid scope(s) {invalid}; "
            f"allowed={sorted(ALLOWED_SCOPES)}"
        )
    return tuple(dict.fromkeys(scopes))


def _parse_match_mode(match_mode: str, row_number: int) -> str:
    if match_mode not in ALLOWED_MATCH_MODES:
        raise ValueError(
            f"name mapping row {row_number}: invalid match_mode '{match_mode}'; "
            f"allowed={sorted(ALLOWED_MATCH_MODES)}"
        )
    return match_mode


def _parse_enabled(enabled_text: str, row_number: int) -> bool:
    lowered = enabled_text.strip().lower()
    if lowered in TRUTHY_VALUES:
        return True
    if lowered in FALSEY_VALUES:
        return False
    raise ValueError(
        f"name mapping row {row_number}: invalid enabled value "
        f"'{enabled_text}'"
    )


def _parse_optional_index(index_text: str, row_number: int) -> int | None:
    if not index_text:
        return None
    try:
        return int(float(index_text))
    except ValueError as exc:
        raise ValueError(
            f"name mapping row {row_number}: invalid index '{index_text}'"
        ) from exc



def _parse_qpl_values(qpl_text: str, row_number: int) -> tuple[int, ...]:
    if not qpl_text:
        return ()

    values: list[int] = []
    for chunk in qpl_text.split(","):
        raw = chunk.strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(
                f"name mapping row {row_number}: invalid QPL value '{raw}'"
            ) from exc
        if value not in values:
            values.append(value)
    return tuple(values)


def _extend_qpl_values(summary: dict[str, Any], rule: NameMappingRule) -> None:
    if rule.note.strip().casefold() != "station" or not rule.qpl_values:
        return
    for value in rule.qpl_values:
        if value not in summary["qpl_values"]:
            summary["qpl_values"].append(value)


def _append_rule_profile(summary: dict[str, Any], rule: NameMappingRule) -> None:
    profile = _format_rule_profile(rule)
    if profile not in summary["rule_profiles"]:
        summary["rule_profiles"].append(profile)


def _format_rule_profile(rule: NameMappingRule) -> str:
    note_value = rule.note.strip() or "(blank)"
    qpl_value = (
        ",".join(str(value) for value in rule.qpl_values)
        if rule.qpl_values else "(none)"
    )
    return f"note={note_value};QPL={qpl_value}"


def _coerce_existing_qpl_values(value: Any) -> tuple[int, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, list):
        coerced: list[int] = []
        for item in value:
            try:
                int_value = int(item)
            except (TypeError, ValueError):
                continue
            if int_value not in coerced:
                coerced.append(int_value)
        return tuple(coerced)
    return ()

def _default_name_mapping_candidates(raw_dir: Path) -> list[Path]:
    raw_dir = raw_dir.resolve()
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        raw_dir / "name_mapping.xlsx",
        raw_dir.parent / "name_mapping.xlsx",
        project_root / "name_mapping.xlsx",
    ]
    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _format_candidate_paths(mapping_path: Path) -> str:
    raw_dir = mapping_path.parent
    candidates = _default_name_mapping_candidates(raw_dir)
    resolved_mapping_path = mapping_path.resolve()
    if resolved_mapping_path not in candidates:
        candidates.insert(0, resolved_mapping_path)
    return ", ".join(str(path) for path in candidates)

