from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml


def _nonblank_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a non-empty list of non-blank strings")
    return value


def validate_config(config: Any) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("CAD 2D config must be a mapping")
    required = {
        "schema_version",
        "identifier",
        "classification",
        "field_extraction",
        "bom",
        "audit",
        "relationships",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"CAD 2D config missing sections: {missing}")
    if not str(config["schema_version"]).strip():
        raise ValueError("schema_version must not be blank")

    suffixes = config["identifier"].get("strip_suffixes", [])
    if not isinstance(suffixes, list) or not all(isinstance(v, str) for v in suffixes):
        raise ValueError("identifier.strip_suffixes must be a list of strings")
    allowed_decisions = _nonblank_strings(
        config["classification"].get("allowed_decisions"), "allowed_decisions"
    )
    aliases = config["classification"].get("decision_aliases", {})
    if not isinstance(aliases, dict) or not aliases:
        raise ValueError("classification.decision_aliases must be a non-empty mapping")
    if not all(
        isinstance(source, str)
        and source.strip()
        and isinstance(target, str)
        and target in allowed_decisions
        for source, target in aliases.items()
    ):
        raise ValueError("classification.decision_aliases contains an invalid mapping")
    for required_alias in ("asm", "prt", "exclude", "unresolved"):
        if required_alias not in aliases:
            raise ValueError(
                f"classification.decision_aliases missing {required_alias!r}"
            )

    extraction = config["field_extraction"]
    profiles = extraction.get("profiles")
    default_profile = extraction.get("default_profile")
    if not isinstance(profiles, dict) or default_profile not in profiles:
        raise ValueError("field_extraction.default_profile must name a configured profile")
    for name, profile in profiles.items():
        if not isinstance(profile, dict) or not isinstance(profile.get("page_index"), int):
            raise ValueError(f"profile {name!r} requires integer page_index")
        regions = profile.get("regions")
        if not isinstance(regions, dict) or not regions:
            raise ValueError(f"profile {name!r} requires regions")
        for field, box in regions.items():
            if (
                not isinstance(box, list)
                or len(box) != 4
                or not all(isinstance(v, (int, float)) for v in box)
                or box[0] >= box[2]
                or box[1] >= box[3]
            ):
                raise ValueError(f"profile {name!r} region {field!r} is invalid")

    bom = config["bom"]
    item_pattern = bom.get("item_number_pattern")
    if not isinstance(item_pattern, str) or not item_pattern:
        raise ValueError("bom.item_number_pattern must be a string")
    try:
        re.compile(item_pattern)
    except re.error as exc:
        raise ValueError("bom.item_number_pattern is invalid") from exc
    lineage = bom.get("reviewed_word_bundle_lineage")
    if lineage is not None and (
        not isinstance(lineage, dict)
        or any(
            not isinstance(lineage.get(key), str)
            or re.fullmatch(r"[0-9a-f]{64}", lineage[key]) is None
            for key in (
                "source_review_file_sha256",
                "projection_file_sha256",
                "b00_bundle_result_sha256",
            )
        )
    ):
        raise ValueError("bom.reviewed_word_bundle_lineage is invalid")
    for column in ("item", "part_number", "quantity"):
        _nonblank_strings(bom.get("header_keywords", {}).get(column), f"bom.header_keywords.{column}")
    thresholds = bom.get("thresholds", {})
    for key in ("header_y_tolerance", "row_y_tolerance", "item_anchor_tolerance", "quantity_anchor_tolerance", "min_header_matches", "min_quantity", "max_quantity"):
        if not isinstance(thresholds.get(key), (int, float)) or thresholds[key] < 0:
            raise ValueError(f"bom.thresholds.{key} must be non-negative")
    if thresholds["min_quantity"] > thresholds["max_quantity"]:
        raise ValueError("bom quantity thresholds are contradictory")

    audit = config["audit"]
    _nonblank_strings(audit.get("blocking_severities"), "audit.blocking_severities")
    _nonblank_strings(
        audit.get("override_decision_states"), "audit.override_decision_states"
    )
    pattern = audit.get("suspicious_identifier_pattern")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("audit.suspicious_identifier_pattern must be a string")

    relationships = config["relationships"]
    for key in ("asm_decision", "prt_decision", "unknown_decision"):
        if relationships.get(key) not in config["classification"]["allowed_decisions"]:
            raise ValueError(f"relationships.{key} must be an allowed decision")
    return config


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        return validate_config(yaml.safe_load(handle))
