"""Build the governed Route C case-candidate artifact from a cleaned workbook.

The workbook is an input staging asset.  Route C runtime consumes the named
JSON artifact produced here, never the raw or cleaned workbook directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


DEFAULT_INPUT = Path("data/raw/C1STN_error_data/Data_test_cleaned_route_c.xlsx")
DEFAULT_OUTPUT = Path("data/processed/aggregates/rag_fp_case_candidates_v1.json")
DEFAULT_MANIFEST = Path(
    "data/processed/aggregates/rag_fp_case_candidates_v1.manifest.json"
)
SOURCE_ID = "rag_fp_case_candidates_v1"
SOURCE_TYPE = "structured_case_candidate"
ROUTE_TARGET = "rag_case_pool"


def build_artifact(
    input_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    input_bytes = input_path.read_bytes()
    input_hash = hashlib.sha256(input_bytes).hexdigest()
    workbook = load_workbook(input_path, read_only=True, data_only=True)
    if "route_c_cases" not in workbook.sheetnames:
        raise ValueError("Input workbook must contain a `route_c_cases` sheet.")

    worksheet = workbook["route_c_cases"]
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Input workbook contains no rows.")
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    required = {
        "rag_candidate_id",
        "route_target",
        "source_type",
        "anomaly_category",
        "phenomenon_normalized",
        "root_cause",
        "countermeasure",
        "dt_mins",
        "source_file",
        "source_sheet",
        "source_row",
        "needs_review",
        "duplicate_conflict",
    }
    missing = sorted(required.difference(headers))
    if missing:
        raise ValueError(f"Input workbook is missing required columns: {missing}")

    records: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    dt_missing_count = 0
    review_count = 0
    duplicate_conflict_count = 0

    for row_number, values in enumerate(rows[1:], start=2):
        row = dict(zip(headers, values))
        case_id = _text(row.get("rag_candidate_id"))
        phenomenon = _text(row.get("phenomenon_normalized"))
        root_cause = _text(row.get("root_cause"))
        countermeasure = _text(row.get("countermeasure"))
        if not case_id or not phenomenon or not root_cause or not countermeasure:
            reasons = []
            if not case_id:
                reasons.append("missing_rag_candidate_id")
            if not phenomenon:
                reasons.append("missing_phenomenon")
            if not root_cause:
                reasons.append("missing_root_cause")
            if not countermeasure:
                reasons.append("missing_countermeasure")
            excluded.append(
                {
                    "input_row": row_number,
                    "rag_candidate_id": case_id,
                    "reasons": reasons,
                }
            )
            continue

        dt_mins = _number_or_none(row.get("dt_mins"))
        if dt_mins is None:
            dt_missing_count += 1
        needs_review = bool(row.get("needs_review"))
        duplicate_conflict = bool(row.get("duplicate_conflict"))
        review_count += int(needs_review)
        duplicate_conflict_count += int(duplicate_conflict)

        category = _text(row.get("anomaly_category"))
        record: dict[str, Any] = {
            "rag_candidate_id": case_id,
            "source_type": SOURCE_TYPE,
            "relation_type": "related_case",
            "route_target": ROUTE_TARGET,
            "field_fp_variants": [phenomenon],
            "field_fp_normalized": phenomenon,
            "RC": root_cause,
            "PA": countermeasure,
            "evidence": {
                "anomaly_category": category,
                "dt_mins": dt_mins,
                "needs_review": needs_review,
                "duplicate_conflict": duplicate_conflict,
            },
            "source_refs": [
                {
                    "source_file": _text(row.get("source_file")),
                    "source_sheet": _text(row.get("source_sheet")),
                    "source_row": row.get("source_row"),
                }
            ],
            "filter_basis": {
                "reason": "C1STN cleaned historical case candidate"
            },
        }
        records.append(record)

    artifact = {
        "schema_version": SOURCE_ID,
        "source_id": SOURCE_ID,
        "source_type": SOURCE_TYPE,
        "route_target": "case_retrieval",
        "publication_status": "candidate_only",
        "input_workbook": input_path.as_posix(),
        "candidates": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    artifact_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
    manifest = {
        "manifest_version": "route_c_case_candidates_manifest_v1",
        "source_id": SOURCE_ID,
        "contract_version": "route_c_source_boundary_v1",
        "input": {
            "path": input_path.as_posix(),
            "sha256": input_hash,
            "sheet": "route_c_cases",
            "input_records": len(rows) - 1,
        },
        "output": {
            "path": output_path.as_posix(),
            "sha256": artifact_hash,
            "candidate_records": len(records),
            "excluded_records": len(excluded),
        },
        "quality": {
            "excluded": excluded,
            "dt_missing_records": dt_missing_count,
            "needs_review_records": review_count,
            "duplicate_conflict_records": duplicate_conflict_count,
        },
        "index_text_policy": {
            "query_text": "field_fp_normalized",
            "answer_payload": ["RC", "PA", "evidence.dt_mins"],
            "excluded_from_index_text": ["source_refs", "raw records", "debug fields"],
        },
        "promotion": {
            "status": "candidate_only",
            "may_promote_to_reviewed_diagnosis": False,
            "may_promote_in_route_c": False,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\r", "\n").split())
    return text or None


def _number_or_none(value: Any) -> int | float | None:
    if value in (None, "", "/", "-", "—"):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    if isinstance(value, datetime):
        return round((value - datetime(1899, 12, 30)).total_seconds() / 60)
    if isinstance(value, date):
        return round(
            (datetime.combine(value, time()) - datetime(1899, 12, 30)).total_seconds()
            / 60
        )
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    manifest = build_artifact(args.input, args.output, args.manifest)
    print(json.dumps(manifest["output"], ensure_ascii=False))
    print(json.dumps(manifest["quality"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
