"""Core masking engine — orchestrates per-source, per-column masking.

Responsibilities:
    1. Load masking_rules.yaml
    2. For a given source, resolve column → (level, canonical_action, serving_action)
    3. Apply field_actions to every cell, producing canonical & serving rows
    4. Emit lineage records for every transformation
    5. Produce manifest at the end

This module provides the orchestration skeleton.
Actual I/O (reading xlsx, writing JSON) is handled by the script entry points
in scripts/ingest/, which call into this engine.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from services.ingestion.field_actions import resolve_action
from services.ingestion.header_normalize import (
    HeaderResolver,
    HeaderResolution,
)


# ── Config loading ───────────────────────────────────────────────────────────

def load_rules(config_path: Path | None = None) -> dict:
    """Load and return masking rules dict from YAML."""
    if config_path is None:
        config_path = Path("configs/masking_rules.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_source_config(rules: dict, source_name: str) -> dict:
    """Extract the source-specific config block. Raises KeyError if missing."""
    sources = rules.get("sources", {})
    if source_name not in sources:
        raise KeyError(
            f"Source '{source_name}' not found in masking_rules.yaml. "
            f"Available: {list(sources.keys())}"
        )
    return sources[source_name]


def resolve_headers(
    raw_headers: list[str],
    source_config: dict,
) -> HeaderResolution:
    """Run header normalization and alias resolution for a source.

    Uses column_rules keys as canonical names and column_aliases for variants.
    """
    column_rules = source_config.get("column_rules", {})
    column_aliases = source_config.get("column_aliases", {})
    resolver = HeaderResolver(column_rules, column_aliases)
    return resolver.resolve(raw_headers)


# ── Column rule resolution ───────────────────────────────────────────────────

def resolve_column_rule(
    column_name: str,
    source_config: dict,
    rules: dict,
    *,
    rule_name_override: str | None = None,
) -> dict:
    """Resolve the masking rule for a single column.

    Args:
        column_name: The (possibly normalized) header from the data file.
        source_config: Source block from masking_rules.yaml.
        rules: Full rules dict.
        rule_name_override: If header resolution mapped this column to a
            different rule name, pass it here to look up the correct rule.

    Priority: source column_rules > global field_classification > default passthrough.

    Returns dict with keys:
        level, canonical_action, serving_action, generalize_method,
        review_flag, rename_to, mask_config
    """
    lookup_name = rule_name_override or column_name

    # Check source-specific rules first
    col_rules = source_config.get("column_rules", {})
    if lookup_name in col_rules:
        cr = col_rules[lookup_name]
        return {
            "level": cr.get("level", "C"),
            "canonical_action": cr.get("canonical_action", "passthrough"),
            "serving_action": cr.get("serving_action", "passthrough"),
            "generalize_method": cr.get("generalize_method"),
            "review_flag": cr.get("review_flag", False),
            "rename_to": cr.get("rename_to"),
            "mask_config": cr.get("mask_config"),
            "type_mapping": cr.get("type_mapping"),
        }

    # Fall back to global field classification
    fc = rules.get("field_classification", {})
    level_defaults = rules.get("level_defaults", {})

    for level_key, level_code in [
        ("A_must_deidentify", "A"),
        ("B_retain_generalize", "B"),
        ("C_must_retain", "C"),
    ]:
        if lookup_name.lower() in [f.lower() for f in fc.get(level_key, [])]:
            defaults = level_defaults.get(level_code, {})
            return {
                "level": level_code,
                "canonical_action": defaults.get("canonical", "passthrough"),
                "serving_action": defaults.get("serving", "passthrough"),
                "generalize_method": None,
                "review_flag": False,
                "rename_to": None,
                "mask_config": None,
                "type_mapping": None,
            }

    # Unknown column — default to passthrough with review flag
    return {
        "level": "C",
        "canonical_action": "passthrough",
        "serving_action": "passthrough",
        "generalize_method": None,
        "review_flag": True,
        "rename_to": None,
        "mask_config": None,
        "type_mapping": None,
    }


# ── Single-cell masking ─────────────────────────────────────────────────────

def mask_cell(
    value: Any,
    *,
    action_name: str,
    tokenizer_config: dict | None = None,
    generalize_method: str | None = None,
    mask_config: dict | None = None,
    rename_to: str | None = None,
    type_mapping: dict | None = None,
) -> tuple[Any, str]:
    """Apply one masking action to a single cell value.

    Returns (masked_value, action_detail_string).
    """
    action_fn = resolve_action(action_name)
    config = dict(tokenizer_config or {})
    if generalize_method:
        config["generalize_method"] = generalize_method
    if mask_config:
        config.update(mask_config)
    if rename_to:
        config["rename_to"] = rename_to
    if type_mapping:
        config["type_mapping"] = type_mapping
    return action_fn(value, config=config)


# ── Row-level masking ────────────────────────────────────────────────────────

def mask_row(
    row: dict[str, Any],
    *,
    source_config: dict,
    rules: dict,
    view: str,  # "canonical" or "serving"
    header_resolution: HeaderResolution | None = None,
) -> tuple[dict[str, Any], list[dict]]:
    """Mask all columns in a single row for the specified view.

    Args:
        row: dict of {column_name: value} — column names should be normalized.
        source_config: Source config block from rules.
        rules: Full masking rules dict.
        view: "canonical" or "serving".
        header_resolution: If provided, used to look up rule names for columns
            whose normalized header differs from the rule name.

    Returns:
        masked_row  — dict with masked values (columns with drop action are omitted)
        actions_log — list of per-column action dicts for lineage
    """
    tokenizer_config = rules.get("tokenizer", {})
    masked = {}
    actions_log = []

    for col_name, value in row.items():
        # Resolve rule name via header resolution if available
        rule_name = None
        if header_resolution:
            rule_name = header_resolution.get_rule_name(col_name)

        col_rule = resolve_column_rule(
            col_name, source_config, rules,
            rule_name_override=rule_name,
        )
        action_key = f"{view}_action"
        action_name = col_rule.get(action_key, "passthrough")

        masked_value, detail = mask_cell(
            value,
            action_name=action_name,
            tokenizer_config=tokenizer_config,
            generalize_method=col_rule.get("generalize_method"),
            mask_config=col_rule.get("mask_config"),
            rename_to=col_rule.get("rename_to"),
            type_mapping=col_rule.get("type_mapping"),
        )

        # Determine output column name (rename support)
        out_col = col_rule.get("rename_to") or col_name

        if action_name != "drop":
            masked[out_col] = masked_value

        actions_log.append({
            "column": col_name,
            "output_column": out_col,
            "level": col_rule["level"],
            "action": action_name,
            "detail": detail,
            "review_flag": col_rule.get("review_flag", False),
        })

    return masked, actions_log
