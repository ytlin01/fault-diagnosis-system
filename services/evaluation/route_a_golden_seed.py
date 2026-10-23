"""Build a deterministic Route A expert-annotation seed from masked records."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SELECTION_POLICY_VERSION = "v2_task001_c1stn_error_code_seed_selection_v1"
QUEUE_SCHEMA_VERSION = "route_a_annotation_queue_v1"
REQUIRED_FIELDS = (
    "Error Description",
    "Code",
    "Category",
    "Error Description (Chinese)",
    "Repair Actions",
    "Local Alarm Code",
)


class GoldenSeedInputError(ValueError):
    """Raised when the masked source cannot produce a governed seed."""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _stable_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _code_shape(value: str) -> str:
    shape = re.sub(r"[A-Za-z]+", "A", value)
    return re.sub(r"\d+", "9", shape)


def _normalized_category(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    return normalized or "missing"


def _validate_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise GoldenSeedInputError("masked source must contain at least one row")
    for index, row in enumerate(rows):
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            raise GoldenSeedInputError(
                f"row {index} is missing required fields: {missing}"
            )
        for field in (
            "Error Description",
            "Code",
            "Error Description (Chinese)",
            "Repair Actions",
            "Local Alarm Code",
        ):
            if not _text(row.get(field)):
                raise GoldenSeedInputError(f"row {index}.{field} is blank")


def _enrich_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    code_counts = Counter(_text(row.get("Code")) for row in rows)
    alarm_counts = Counter(_text(row.get("Local Alarm Code")) for row in rows)
    category_counts = Counter(
        _normalized_category(_text(row.get("Category"))) for row in rows
    )
    repair_counts = Counter(_text(row.get("Repair Actions")) for row in rows)

    enriched: list[dict[str, Any]] = []
    for source_index, raw_row in enumerate(rows):
        row = {field: _text(raw_row.get(field)) for field in REQUIRED_FIELDS}
        digest = _stable_digest(row)
        row.update(
            {
                "_source_index": source_index,
                "_digest": digest,
                "_code_shape": _code_shape(row["Code"]),
                "_category_key": _normalized_category(row["Category"]),
                "_code_count": code_counts[row["Code"]],
                "_alarm_count": alarm_counts[row["Local Alarm Code"]],
                "_category_count": category_counts[
                    _normalized_category(row["Category"])
                ],
                "_repair_count": repair_counts[row["Repair Actions"]],
            }
        )
        enriched.append(row)
    return enriched


def _select_one(
    selected: list[dict[str, Any]],
    candidates: Sequence[dict[str, Any]],
) -> None:
    selected_digests = {row["_digest"] for row in selected}
    remaining = [
        row for row in candidates if row["_digest"] not in selected_digests
    ]
    if remaining:
        selected.append(min(remaining, key=lambda row: row["_digest"]))


def select_pilot_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    count: int = 15,
) -> list[dict[str, Any]]:
    """Select a stable, coverage-aware development pilot."""
    if count < 1:
        raise GoldenSeedInputError("count must be positive")
    _validate_rows(rows)
    enriched = _enrich_rows(rows)
    count = min(count, len(enriched))
    selected: list[dict[str, Any]] = []

    # Preserve each raw category variant so anomalies remain visible.
    for category in sorted({row["Category"] or "<blank>" for row in enriched}):
        _select_one(
            selected,
            [
                row
                for row in enriched
                if (row["Category"] or "<blank>") == category
            ],
        )

    # Cover every observed primary-code format.
    for shape in sorted({row["_code_shape"] for row in enriched}):
        _select_one(
            selected,
            [row for row in enriched if row["_code_shape"] == shape],
        )

    # Include up to three distinct duplicate-code groups for ambiguity review.
    duplicate_codes = sorted(
        {row["Code"] for row in enriched if row["_code_count"] > 1}
    )
    for code in duplicate_codes[:3]:
        _select_one(
            selected,
            [row for row in enriched if row["Code"] == code],
        )

    # Fill by rarity and new repair-action coverage, with a stable digest tie.
    while len(selected) < count:
        selected_digests = {row["_digest"] for row in selected}
        selected_repairs = {row["Repair Actions"] for row in selected}
        remaining = [
            row for row in enriched if row["_digest"] not in selected_digests
        ]
        if not remaining:
            break

        def priority(row: Mapping[str, Any]) -> tuple[float, str]:
            novelty = 2.0 if row["Repair Actions"] not in selected_repairs else 0.0
            duplicate_bonus = 1.0 if row["_code_count"] > 1 else 0.0
            rarity = (
                1.0 / row["_category_count"]
                + 1.0 / row["_repair_count"]
            )
            return (-(novelty + duplicate_bonus + rarity), row["_digest"])

        selected.append(min(remaining, key=priority))

    return selected[:count]


def _difficulty(row: Mapping[str, Any]) -> str:
    category = row["_category_key"]
    if row["_code_count"] > 1 or category in {
        "missing",
        "actual downtimeactual downtime",
    }:
        return "high"
    if category != "actual downtime" or row["_repair_count"] >= 10:
        return "medium"
    return "low"


def build_annotation_seed(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_path: Path,
    source_id: str,
    manifest_path: str,
    masking_log_id: str,
    count: int = 15,
) -> dict[str, Any]:
    selected = select_pilot_rows(rows, count=count)
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    cases = []
    for ordinal, row in enumerate(selected, start=1):
        record_id = f"src-c1stn-ec-{row['_digest'][:12]}"
        case_id = f"RA-SEED-C1STN-EC-{ordinal:03d}"
        scenario_id = f"RA-SEED-C1STN-EC-S{ordinal:03d}"
        query = (
            f"C1STN alarm {row['Local Alarm Code']} / code {row['Code']}: "
            f"{row['Error Description (Chinese)']} "
            f"({row['Error Description']}). "
            "Identify acceptable cause(s) and repair action(s), or abstain "
            "when the evidence is insufficient."
        )
        cases.append(
            {
                "case_id": case_id,
                "scenario_id": scenario_id,
                "partition": "development",
                "query": query,
                "query_language": "zh-en",
                "coverage": {
                    "query_type": "ec",
                    "difficulty": _difficulty(row),
                    "equipment_scope": "c1stn_unspecified",
                },
                "seed_status": "provisional_annotation_candidate",
                "source_context": {
                    "source_id": source_id,
                    "source_record_id": record_id,
                    "source_anchor": f"serving_record_sha256:{row['_digest']}",
                    "label_authority": "source_suggested_only",
                    "code": row["Code"],
                    "local_alarm_code": row["Local Alarm Code"],
                    "category": row["Category"],
                    "error_description": row["Error Description"],
                    "error_description_zh": row[
                        "Error Description (Chinese)"
                    ],
                    "source_suggested_repair_action": row["Repair Actions"],
                    "source_row_index": row["_source_index"],
                    "code_shape": row["_code_shape"],
                    "duplicate_code_count": row["_code_count"],
                },
            }
        )

    selection_digest = hashlib.sha256(
        "\n".join(case["source_context"]["source_record_id"] for case in cases)
        .encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_id": "v2_task001_c1stn_error_code_annotation_seed_v1",
        "queue_state": "provisional",
        "source": {
            "source_id": source_id,
            "path": source_path.as_posix(),
            "sha256": source_sha256,
            "manifest_path": manifest_path,
            "masking_log_id": masking_log_id,
            "masking_status": "masked",
            "audit_status": "data_owner_reported_clean",
            "allowed_use": "annotation_only",
            "reviewed_status": "pending",
        },
        "selection_policy": {
            "policy_version": SELECTION_POLICY_VERSION,
            "source_row_count": len(rows),
            "selected_case_count": len(cases),
            "partition": "development",
            "selection_digest": selection_digest,
            "coverage_order": [
                "raw_category_variant",
                "code_shape",
                "duplicate_code_group",
                "repair_action_rarity",
            ],
        },
        "cases": cases,
        "cause_catalog": [],
        "cause_action_pair_catalog": [],
    }
