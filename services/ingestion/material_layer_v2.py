"""Governed Schema 4.2 replacement-list parser primitives (V2-TASK017).

This module is pure stdlib: it never imports openpyxl or yaml, never reads
files, and never touches a graph. The candidate-builder CLI owns all file
I/O, XLSX reading, and manifest creation.

It implements the reduced surface recorded in the task brief on 2026-08-27:
the single governed BOM04 replacement-list input (L_ReplacementList),
``ReplacementPart`` nodes only (no edges: the BOM03 path, topology endpoint
resolution, and ``REPLACEMENT_FOR`` were removed with the data-owner scope
decision), consumable station usage as review-queue candidates (never
edges, never document exclusions), and no fault-text mention scanning.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, Mapping, Sequence

CONFIG_SCHEMA_VERSION = "material-extract-v2.0-draft"
IDENTITY_RULE_VERSION = "material_identity_v1"
AUDIT_SCHEMA_VERSION = "material-layer-v2-audit-v1"
LEAK_REPORT_SCHEMA_VERSION = "material-layer-v2-leak-report-v1"
MANIFEST_ARTIFACTS = ("candidate", "exclusions", "lineage", "audit")

# Closed schema exclusion vocabulary (Schema 4.2 $defs/exclusion).
SCHEMA_EXCLUSION_REASONS = frozenset({
    "missing_stable_native_id",
    "duplicate_canonical_id",
    "missing_parent",
    "multiple_parents",
    "self_parent",
    "cycle",
    "parent_mismatch",
    "cross_namespace_without_merge",
    "invalid_type",
    "other",
})

# Closed task review vocabulary. Entries whose reason maps to a schema
# exclusion become document exclusions; the rest stay review-queue-only.
MATERIAL_REVIEW_REASONS = frozenset({
    "consumable_station_usage_unsupported",
    "ambiguous_spec_merge",
})

REVIEW_TO_SCHEMA_REASON = {
    "ambiguous_spec_merge": "duplicate_canonical_id",
}

_REQUIRED_SECTIONS = (
    "schema_version", "identity", "canonicalization",
    "bom04", "detection", "leakage", "audit", "candidate",
)

_WS = re.compile(r"\s+")

_CONFIG_SECTIONS = ("bom04",)


def canonical_json_bytes(value: Any) -> bytes:
    """Deterministic compact JSON bytes (shared with the CLI write path)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonicalize_text(value: Any) -> str:
    """NFKC + collapse internal whitespace + strip; no case or script change."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return _WS.sub(" ", text).strip()


def match_key(value: Any) -> str:
    """Case-folded canonical form for header/label matching only."""
    return canonicalize_text(value).casefold()


# ── configuration ────────────────────────────────────────────────────────────

def _nonblank_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")
    return value


def _validate_bom_section(cfg: Mapping[str, Any], name: str) -> None:
    section = cfg[name]
    if not isinstance(section, Mapping):
        raise ValueError(f"material config section {name} must be a mapping")
    _nonblank_str(section.get("source_id"), f"{name}.source_id")
    _nonblank_str(section.get("sheet"), f"{name}.sheet")
    for key in ("header_row", "data_offset"):
        value = section.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name}.{key} must be a non-negative integer")
    if not isinstance(section.get("data_offset"), int) or section["data_offset"] < 1:
        raise ValueError(f"{name}.data_offset must be a positive integer")
    _nonblank_str(section.get("name_col"), f"{name}.name_col")
    _nonblank_str(section.get("spec_col"), f"{name}.spec_col")
    aliases = section.get("header_aliases", {})
    if not isinstance(aliases, Mapping):
        raise ValueError(f"{name}.header_aliases must be a mapping of column to alias list")
    for column, alias_list in aliases.items():
        _nonblank_str(column, f"{name}.header_aliases key")
        if not isinstance(alias_list, list):
            raise ValueError(f"{name}.header_aliases[{column!r}] must be a list of strings")
        for alias in alias_list:
            _nonblank_str(alias, f"{name}.header_aliases[{column!r}] item")
    sensitive = section.get("sensitive_columns", [])
    if not isinstance(sensitive, list):
        raise ValueError(f"{name}.sensitive_columns must be a list of strings")
    for column in sensitive:
        _nonblank_str(column, f"{name}.sensitive_columns item")
    protected = {section.get("name_col"), section.get("spec_col")}
    for column in sensitive:
        if column in protected:
            raise ValueError(
                f"{name}.sensitive_columns must not contain the name or spec column"
            )
    station_cols = section.get("station_cols", [])
    if not isinstance(station_cols, list):
        raise ValueError("bom04.station_cols must be a list of strings")
    for column in station_cols:
        _nonblank_str(column, "bom04.station_cols item")
    if section.get("equipment_col") is not None:
        _nonblank_str(section.get("equipment_col"), "bom04.equipment_col")


def validate_config(config: Any) -> dict[str, Any]:
    """Validate the material-extract v2 configuration; raise ValueError."""
    if not isinstance(config, Mapping):
        raise ValueError("material config must be a mapping")
    missing = [key for key in _REQUIRED_SECTIONS if key not in config]
    if missing:
        raise ValueError(f"material config missing sections: {', '.join(sorted(missing))}")
    if config["schema_version"] != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {CONFIG_SCHEMA_VERSION!r}, got {config['schema_version']!r}"
        )

    identity = config["identity"]
    if not isinstance(identity, Mapping):
        raise ValueError("material config section identity must be a mapping")
    _nonblank_str(identity.get("salt_env"), "identity.salt_env")
    _nonblank_str(identity.get("identity_rule_version"), "identity.identity_rule_version")
    if identity.get("id_prefix") != "RP_":
        raise ValueError("identity.id_prefix must be 'RP_' (Schema 4.2 ReplacementPart ids)")
    if not isinstance(identity.get("spec_in_id"), bool):
        raise ValueError("identity.spec_in_id must be a boolean")
    if not isinstance(identity.get("spec_missing_token", ""), str):
        raise ValueError("identity.spec_missing_token must be a string")

    canonicalization = config["canonicalization"]
    if not isinstance(canonicalization, Mapping):
        raise ValueError("material config section canonicalization must be a mapping")
    if canonicalization.get("unicode_normalization") != "NFKC":
        raise ValueError("canonicalization.unicode_normalization must be 'NFKC'")
    if canonicalization.get("collapse_whitespace") is not True:
        raise ValueError("canonicalization.collapse_whitespace must be true")
    if canonicalization.get("identity_casefold") is not False:
        raise ValueError(
            "canonicalization.identity_casefold must be false (identity is case-preserving)"
        )
    if not isinstance(canonicalization.get("match_casefold"), bool):
        raise ValueError("canonicalization.match_casefold must be a boolean")

    for name in _CONFIG_SECTIONS:
        _validate_bom_section(config, name)

    detection = config["detection"]
    if not isinstance(detection, Mapping):
        raise ValueError("material config section detection must be a mapping")
    search_rows = detection.get("search_rows")
    if not isinstance(search_rows, int) or isinstance(search_rows, bool) or search_rows < 1:
        raise ValueError("detection.search_rows must be a positive integer")

    leakage = config["leakage"]
    if not isinstance(leakage, Mapping):
        raise ValueError("material config section leakage must be a mapping")
    min_length = leakage.get("min_value_length")
    if not isinstance(min_length, int) or isinstance(min_length, bool) or min_length < 1:
        raise ValueError("leakage.min_value_length must be a positive integer")
    if not isinstance(leakage.get("skip_purely_numeric"), bool):
        raise ValueError("leakage.skip_purely_numeric must be a boolean")
    try:
        re.compile(leakage.get("numeric_pattern", ""))
    except re.error as exc:
        raise ValueError(f"leakage.numeric_pattern is not a valid regex: {exc}") from exc

    audit = config["audit"]
    if not isinstance(audit, Mapping):
        raise ValueError("material config section audit must be a mapping")
    warn_rate = audit.get("spec_missing_rate_warn")
    if not isinstance(warn_rate, (int, float)) or isinstance(warn_rate, bool) or not 0 <= warn_rate <= 1:
        raise ValueError("audit.spec_missing_rate_warn must be a number between 0 and 1")

    candidate = config["candidate"]
    if not isinstance(candidate, Mapping):
        raise ValueError("material config section candidate must be a mapping")
    if candidate.get("schema_version") != "4.2":
        raise ValueError("candidate.schema_version must be '4.2'")
    if candidate.get("payload_kind") != "diagnostic":
        raise ValueError("candidate.payload_kind must be 'diagnostic'")
    return dict(config)


# ── sheet location, headers, row extraction ─────────────────────────────────

@dataclass(frozen=True)
class SheetLocation:
    sheet: str
    header_row_index: int          # 0-based
    data_start_index: int          # 0-based
    fell_back: bool                # configured sheet absent, auto-picked
    header_detected: bool          # header found by detection vs config default


def _alias_lookup(bom_cfg: Mapping[str, Any]) -> dict[str, str]:
    """match_key(header cell) -> canonical column name."""
    canonical_columns: list[str] = [bom_cfg["name_col"], bom_cfg["spec_col"]]
    canonical_columns.extend(bom_cfg.get("station_cols", []))
    if bom_cfg.get("equipment_col"):
        canonical_columns.append(bom_cfg["equipment_col"])
    canonical_columns.extend(bom_cfg.get("sensitive_columns", []))
    lookup: dict[str, str] = {}
    for column in canonical_columns:
        if column is not None:
            lookup[match_key(column)] = column
    for column, aliases in bom_cfg.get("header_aliases", {}).items():
        for alias in aliases:
            lookup.setdefault(match_key(alias), column)
    return lookup


def resolve_headers(header_row: Sequence[Any], bom_cfg: Mapping[str, Any]) -> dict[int, str]:
    """Map column index -> canonical column name via alias resolution."""
    lookup = _alias_lookup(bom_cfg)
    resolved: dict[int, str] = {}
    for index, cell in enumerate(header_row):
        key = match_key(cell)
        if not key:
            continue
        column = lookup.get(key)
        if column is not None and column not in resolved.values():
            resolved[index] = column
    return resolved


def _sheet_contains_name_column(
    rows: Sequence[Sequence[Any]], bom_cfg: Mapping[str, Any], *, search_rows: int
) -> bool:
    name_keys = {match_key(bom_cfg["name_col"])}
    for alias in bom_cfg.get("header_aliases", {}).get(bom_cfg["name_col"], []):
        name_keys.add(match_key(alias))
    for row in rows[:search_rows]:
        if any(match_key(cell) in name_keys for cell in row):
            return True
    return False


def locate_sheet_and_header(
    sheets: Mapping[str, Sequence[Sequence[Any]]],
    bom_cfg: Mapping[str, Any],
    *,
    search_rows: int,
) -> SheetLocation:
    """Pick the sheet and header row, falling back within the search window."""
    if not sheets:
        raise ValueError("workbook has no sheets")
    configured = bom_cfg["sheet"]
    if configured in sheets:
        sheet, fell_back = configured, False
    elif len(sheets) == 1:
        sheet, fell_back = next(iter(sheets)), True
    else:
        sheet = None
        for name, rows in sheets.items():  # workbook order preserved by the caller
            if _sheet_contains_name_column(rows, bom_cfg, search_rows=search_rows):
                sheet = name
                break
        if sheet is None:
            raise ValueError(
                f"no sheet contains the name column {bom_cfg['name_col']!r} within the top "
                f"{search_rows} rows and the configured sheet {configured!r} is absent"
            )
        fell_back = True

    rows = sheets[sheet]
    lookup = _alias_lookup(bom_cfg)
    name_keys = {match_key(bom_cfg["name_col"])}
    for alias in bom_cfg.get("header_aliases", {}).get(bom_cfg["name_col"], []):
        name_keys.add(match_key(alias))
    header_index = None
    for index, row in enumerate(rows[:search_rows]):
        if any(match_key(cell) in name_keys for cell in row):
            header_index = index
            break
    if header_index is None:
        header_index = int(bom_cfg["header_row"])
        header_detected = False
    else:
        header_detected = True
    return SheetLocation(
        sheet=sheet,
        header_row_index=header_index,
        data_start_index=header_index + int(bom_cfg["data_offset"]),
        fell_back=fell_back,
        header_detected=header_detected,
    )


@dataclass(frozen=True)
class MaterialRow:
    source_id: str
    sheet: str
    row_number: int                 # Excel 1-based
    name: str                       # canonical
    spec: str                       # canonical, "" when absent
    station: str                    # canonical, "" when absent
    source_anchor: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "sheet": self.sheet,
            "row_number": self.row_number,
            "name": self.name,
            "spec": self.spec,
            "station": self.station,
            "source_anchor": self.source_anchor,
        }


@dataclass(frozen=True)
class RowExtraction:
    rows: tuple[MaterialRow, ...]
    audit: dict[str, Any]
    raw_names: dict[str, str] = dataclass_field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"rows": [row.as_dict() for row in self.rows], "audit": self.audit}


def _cell(row: Sequence[Any], index: int | None) -> Any:
    if index is None or index >= len(row):
        return None
    return row[index]


def extract_rows(
    rows: Sequence[Sequence[Any]],
    bom_cfg: Mapping[str, Any],
    location: SheetLocation,
) -> RowExtraction:
    """Extract canonicalized material rows; empty and blank-name rows are skipped."""
    headers = resolve_headers(rows[location.header_row_index], bom_cfg)
    column_index = {column: index for index, column in headers.items()}
    source_id = bom_cfg["source_id"]

    def col(name: str) -> int | None:
        return column_index.get(name)

    extracted: list[MaterialRow] = []
    raw_names: dict[str, str] = {}
    skipped_empty = 0
    skipped_name_blank = 0
    station_cols = list(bom_cfg.get("station_cols", []))

    for index in range(location.data_start_index, len(rows)):
        row = rows[index]
        if not any(canonicalize_text(cell) for cell in row):
            skipped_empty += 1
            continue
        name = canonicalize_text(_cell(row, col(bom_cfg["name_col"])))
        if not name:
            skipped_name_blank += 1
            continue
        spec = canonicalize_text(_cell(row, col(bom_cfg["spec_col"])))
        station = ""
        for station_col in station_cols:
            station = canonicalize_text(_cell(row, col(station_col)))
            if station:
                break
        extracted.append(MaterialRow(
            source_id=source_id,
            sheet=location.sheet,
            row_number=index + 1,
            name=name,
            spec=spec,
            station=station,
            source_anchor=f"{source_id}#{location.sheet}!r{index + 1}",
        ))
        raw_name_cell = _cell(row, col(bom_cfg["name_col"]))
        raw_names[f"{source_id}#{location.sheet}!r{index + 1}"] = (
            "" if raw_name_cell is None else str(raw_name_cell)
        )

    audit = {
        "source_id": source_id,
        "sheet": location.sheet,
        "header_row_excel": location.header_row_index + 1,
        "data_start_excel": location.data_start_index + 1,
        "fell_back": location.fell_back,
        "header_detected": location.header_detected,
        "resolved_columns": sorted(headers.values()),
        "missing_columns": sorted(
            set(
                [bom_cfg["name_col"], bom_cfg["spec_col"]]
                + station_cols
                + ([bom_cfg["equipment_col"]] if bom_cfg.get("equipment_col") else [])
            ) - set(headers.values())
        ),
        "rows_used": len(extracted),
        "skipped_empty": skipped_empty,
        "skipped_name_blank": skipped_name_blank,
    }
    return RowExtraction(rows=tuple(extracted), audit=audit, raw_names=raw_names)


# ── node stage ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NodeBuildResult:
    nodes: tuple[dict[str, Any], ...]
    merge_audit: tuple[dict[str, Any], ...]
    review_entries: tuple[dict[str, Any], ...]
    anchor_to_node_id: dict[str, str]
    counts: dict[str, int]


def _identity_key(row: MaterialRow, *, spec_in_id: bool) -> str:
    return f"{row.name}|{row.spec}" if spec_in_id else row.name


def build_material_nodes(
    rows: Sequence[MaterialRow],
    raw_names: Mapping[str, str],
    *,
    salt: str,
    config: Mapping[str, Any],
) -> NodeBuildResult:
    """Group rows into salted ReplacementPart nodes with a merge/collision audit.

    ``raw_names`` maps each row's source anchor to its raw (pre-canonicalization)
    name cell value, used for collision detection and alias preservation.
    """
    if not salt:
        raise ValueError("salt must be a non-empty string (identity is salted, fail-closed)")
    identity_cfg = config["identity"]
    spec_in_id = identity_cfg["spec_in_id"]
    rule_version = identity_cfg["identity_rule_version"]

    groups: dict[str, list[MaterialRow]] = {}
    for row in rows:
        groups.setdefault(_identity_key(row, spec_in_id=spec_in_id), []).append(row)

    id_to_key: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    merge_audit: list[dict[str, Any]] = []
    review_entries: list[dict[str, Any]] = []
    anchor_to_node_id: dict[str, str] = {}
    collision_nodes = 0
    spec_missing_rows = 0

    for key in sorted(groups):
        group = groups[key]
        node_id = f"RP_{hashlib.sha256((salt + key).encode('utf-8')).hexdigest()}"
        if node_id in id_to_key and id_to_key[node_id] != key:
            raise ValueError(
                f"sha256 identity collision between {id_to_key[node_id]!r} and {key!r}"
            )
        id_to_key[node_id] = key
        canonical_name = group[0].name
        specs = sorted({row.spec for row in group if row.spec})
        if spec_in_id:
            specification = group[0].spec or None
        else:
            specification = specs[0] if specs else None
            if len(specs) > 1:
                review_entries.append({
                    "source_anchor": min(row.source_anchor for row in group),
                    "reason_code": "ambiguous_spec_merge",
                    "detail": (
                        f"name-only identity merges {len(specs)} distinct specifications "
                        f"for {canonical_name!r}"
                    ),
                })
        spec_missing_rows += sum(1 for row in group if not row.spec)
        raw_forms = sorted({raw_names.get(row.source_anchor, row.name) for row in group})
        aliases = sorted({form for form in raw_forms if form != canonical_name})
        if len(raw_forms) > 1:
            collision_nodes += 1
        properties: dict[str, Any] = {
            "replacement_part_id": node_id,
            "canonical_name": canonical_name,
            "specification": specification,
            "replacement_policy": None,
            "identity_rule_version": rule_version,
        }
        if aliases:
            properties["aliases"] = aliases
        nodes.append({"label": "ReplacementPart", "id": node_id, "properties": properties})
        anchors = sorted(row.source_anchor for row in group)
        merge_audit.append({
            "replacement_part_id": node_id,
            "canonical_name": canonical_name,
            "specification": specification,
            "distinct_raw_forms": raw_forms,
            "source_rows": anchors,
            "collision": len(raw_forms) > 1,
        })
        for row in group:
            anchor_to_node_id[row.source_anchor] = node_id

    nodes.sort(key=lambda node: node["id"])
    merge_audit.sort(key=lambda entry: entry["replacement_part_id"])
    counts = {
        "nodes": len(nodes),
        "merged_groups": len(groups),
        "collision_nodes": collision_nodes,
        "spec_missing_rows": spec_missing_rows,
    }
    return NodeBuildResult(
        nodes=tuple(nodes),
        merge_audit=tuple(merge_audit),
        review_entries=tuple(sorted(
            review_entries, key=lambda entry: (entry["source_anchor"], entry["reason_code"])
        )),
        anchor_to_node_id=anchor_to_node_id,
        counts=counts,
    )


# ── review and lineage stages ────────────────────────────────────────────────

def build_consumable_station_review(
    bom04_rows: Sequence[MaterialRow],
    nodes_result: NodeBuildResult,
    *,
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Queue BOM04 station-usage linkages: no Schema 4.2 surface exists for them."""
    entries = []
    for row in bom04_rows:
        if not row.station:
            continue
        node_id = nodes_result.anchor_to_node_id.get(row.source_anchor)
        if node_id is None:  # pragma: no cover - defensive
            raise ValueError(f"row {row.source_anchor} has no material node")
        entries.append({
            "source_anchor": row.source_anchor,
            "reason_code": "consumable_station_usage_unsupported",
            "detail": (
                f"station usage ({row.station}) has no Schema 4.2 surface; "
                "queued for a reviewed action-requirement or contract-extension decision"
            ),
            "station": row.station,
            "material_node_id": node_id,
        })
    return tuple(sorted(entries, key=lambda entry: (entry["source_anchor"], entry["reason_code"])))


def build_node_lineage(
    rows: Sequence[MaterialRow], nodes_result: NodeBuildResult
) -> tuple[dict[str, Any], ...]:
    """One lineage record per contributing row for every material node."""
    records = [
        {
            "target_type": "node",
            "target_id": nodes_result.anchor_to_node_id[row.source_anchor],
            "source": row.source_id,
            "extracted_from": row.source_anchor,
        }
        for row in rows
    ]
    return tuple(sorted(
        records, key=lambda record: (record["target_type"], record["target_id"], record["extracted_from"])
    ))


# ── leakage self-check ───────────────────────────────────────────────────────

def collect_forbidden_values(
    rows: Sequence[Sequence[Any]],
    bom_cfg: Mapping[str, Any],
    location: SheetLocation,
    *,
    leakage_cfg: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Collect forbidden values from sensitive columns: value -> column + anchors."""
    headers = resolve_headers(rows[location.header_row_index], bom_cfg)
    column_index = {column: index for index, column in headers.items()}
    numeric = re.compile(leakage_cfg["numeric_pattern"])
    min_length = leakage_cfg["min_value_length"]
    forbidden: dict[str, dict[str, Any]] = {}
    for column in bom_cfg.get("sensitive_columns", []):
        index = column_index.get(column)
        if index is None:
            continue
        for row_index in range(location.data_start_index, len(rows)):
            value = canonicalize_text(_cell(rows[row_index], index))
            if not value or len(value) < min_length:
                continue
            if leakage_cfg["skip_purely_numeric"] and numeric.match(value):
                continue
            entry = forbidden.setdefault(
                value, {"column": column, "anchors": [], "source_id": bom_cfg["source_id"]}
            )
            entry["anchors"].append(f"{bom_cfg['source_id']}#{location.sheet}!r{row_index + 1}")
    for entry in forbidden.values():
        entry["anchors"].sort()
    return forbidden


def check_leakage(
    artifacts: Mapping[str, bytes],
    forbidden: Mapping[str, dict[str, Any]],
    *,
    nodes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Substring-scan serialized artifacts for forbidden values; raw values stay here."""
    node_names = [
        canonicalize_text(node["properties"].get("canonical_name"))
        for node in nodes
    ] + [
        canonicalize_text(alias)
        for node in nodes
        for alias in node["properties"].get("aliases", [])
    ]
    leaks = []
    for value, meta in sorted(forbidden.items()):
        found_in = sorted(
            name for name, payload in artifacts.items() if value.encode("utf-8") in payload
        )
        if not found_in:
            continue
        inside_name = any(value in name for name in node_names if name)
        leaks.append({
            "value": value,
            "column": meta["column"],
            "anchors": meta["anchors"],
            "found_in": found_in,
            "note": (
                "substring of a legitimate material name - likely false positive"
                if inside_name
                else "not inside any material name - review"
            ),
        })
    return {
        "schema_version": LEAK_REPORT_SCHEMA_VERSION,
        "forbidden_values_checked": len(forbidden),
        "leak_count": len(leaks),
        "leaks": leaks,
    }


# ── assembly ─────────────────────────────────────────────────────────────────

def _schema_exclusions(
    review_entries: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], ...]:
    exclusions = {
        (
            entry["source_anchor"],
            REVIEW_TO_SCHEMA_REASON[entry["reason_code"]],
            f"{entry['reason_code']}: {entry['detail']}",
        )
        for entry in review_entries
        if entry["reason_code"] in REVIEW_TO_SCHEMA_REASON
    }
    return tuple(
        {"source_native_id": anchor, "reason": reason, "detail": detail}
        for anchor, reason, detail in sorted(exclusions)
    )


@dataclass(frozen=True)
class MaterialLayerResult:
    candidate: dict[str, Any]
    exclusions: tuple[dict[str, str], ...]
    lineage: tuple[dict[str, Any], ...]
    audit: dict[str, Any]
    leak_report: dict[str, Any]

    @property
    def complete(self) -> bool:
        return not self.exclusions

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "exclusions": list(self.exclusions),
            "lineage": list(self.lineage),
            "audit": self.audit,
            "leak_report": self.leak_report,
        }


def build_material_layer(
    bom04_extraction: RowExtraction,
    *,
    raw_names: Mapping[str, str],
    salt: str,
    config: Mapping[str, Any],
    forbidden_values: Mapping[str, dict[str, Any]] | None = None,
) -> MaterialLayerResult:
    """Run all replacement-list stages and assemble the Schema 4.2 candidate envelope.

    Node-only by design (data-owner decision 2026-08-27): the BOM03 path and
    ``REPLACEMENT_FOR`` edge resolution were removed, so ``edges`` is always
    empty and station usage stays a review-queue candidate.
    """
    bom04_rows = bom04_extraction.rows

    nodes_result = build_material_nodes(bom04_rows, raw_names, salt=salt, config=config)
    consumable_review = build_consumable_station_review(bom04_rows, nodes_result, config=config)
    node_lineage = build_node_lineage(bom04_rows, nodes_result)

    review_entries = tuple(nodes_result.review_entries) + consumable_review
    exclusions = _schema_exclusions(review_entries)
    lineage = node_lineage

    candidate = {
        "schema_version": "4.2",
        "payload_kind": "diagnostic",
        "nodes": [dict(node) for node in nodes_result.nodes],
        "edges": [],
        "exclusions": [dict(entry) for entry in exclusions],
    }

    warn_rate = config["audit"]["spec_missing_rate_warn"]
    total_rows = len(bom04_rows)
    audit = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "counts": {
            **nodes_result.counts,
            "consumable_station_review_entries": len(consumable_review),
            "review_entries": len(review_entries),
            "document_exclusions": len(exclusions),
            "lineage_records": len(lineage),
            "consumable_rows": len(bom04_rows),
        },
        "flags": {
            "spec_missing_rate_warn_exceeded": (
                total_rows > 0 and nodes_result.counts["spec_missing_rows"] / total_rows > warn_rate
            ),
        },
        "extraction": {"bom04": bom04_extraction.audit},
        "merge_audit": [dict(entry) for entry in nodes_result.merge_audit],
        "review_queue": [dict(entry) for entry in review_entries],
    }

    leak_report = check_leakage(
        {
            "candidate": canonical_json_bytes(candidate),
            "exclusions": canonical_json_bytes(list(exclusions)),
            "lineage": canonical_json_bytes(list(lineage)),
            "audit": canonical_json_bytes(audit),
        },
        forbidden_values or {},
        nodes=nodes_result.nodes,
    )
    return MaterialLayerResult(
        candidate=candidate,
        exclusions=exclusions,
        lineage=lineage,
        audit=audit,
        leak_report=leak_report,
    )
