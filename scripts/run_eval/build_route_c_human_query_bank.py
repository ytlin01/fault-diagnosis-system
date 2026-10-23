"""Build a review-pending Route C human query-bank candidate set."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import Workbook

DEFAULT_ARTIFACT = Path("data/processed/aggregates/rag_fp_case_candidates_v1.json")
DEFAULT_JSON = Path("data/eval/route_c/route_c_human_query_bank_candidate_v1.json")
DEFAULT_XLSX = Path("data/eval/route_c/route_c_human_query_bank_review_v1.xlsx")


def build_bank(artifact_path: Path, json_path: Path, xlsx_path: Path) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    records = [record for record in artifact.get("candidates", []) if isinstance(record, dict)]
    if not records:
        raise ValueError("Route C artifact has no candidates.")
    by_phenomenon: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        phenomenon = _clean(record.get("field_fp_normalized"))
        if phenomenon:
            by_phenomenon[phenomenon].append(record)
    unique_records = [r for r in records if len(by_phenomenon[_clean(r.get("field_fp_normalized"))]) == 1]
    conflict_records = [r for r in records if len(by_phenomenon[_clean(r.get("field_fp_normalized"))]) > 1]
    selected = _spread(unique_records, 30) + _spread(conflict_records, 10)
    cases: list[dict[str, Any]] = []
    ordinal = 1
    for record in selected:
        phenomenon = _clean(record["field_fp_normalized"])
        group = by_phenomenon[phenomenon]
        ids = [str(item["rag_candidate_id"]) for item in group]
        roots = _unique(str(item.get("RC") or "") for item in group)
        actions = _unique(str(item.get("PA") or "") for item in group)
        variants = [("case_text", phenomenon, "low"), ("punctuation_normalized", _strip_punctuation(phenomenon), "medium")]
        if len(phenomenon) >= 12:
            variants.append(("shortened_phenomenon", _shorten(phenomenon), "high"))
        for query_type, query, difficulty in variants:
            if not query or (query == phenomenon and query_type != "case_text"):
                continue
            cases.append(_case(ordinal, query, query_type, difficulty, ids, roots, actions, record))
            ordinal += 1
    no_hits = [
        ("真空冷却系统超导泄漏报警", "high"), ("激光焊接腔体压力持续异常", "high"),
        ("机器人电池温度超过安全上限", "high"), ("未发生过的海水泵叶轮断裂故障", "high"),
        ("quantum cooling chamber leak", "high"), ("unrelated conveyor lubrication failure", "high"),
        ("完全没有相关历史案例的测试故障", "medium"), ("不存在的 C1STN 超导模块错误", "high"),
        ("random unrelated office printer issue", "high"), ("新能源电池热失控", "high"),
    ]
    for query, difficulty in no_hits:
        cases.append(_case(ordinal, query, "no_hit", difficulty, [], [], [], None))
        ordinal += 1
    bank = {
        "schema_version": "route_c_human_query_bank_candidate_v1",
        "route": "route_c",
        "source_artifact": artifact_path.as_posix(),
        "status": "review_pending",
        "gold_status": "unreviewed",
        "generation_note": "Deterministic transformations plus synthetic no-hit queries; human review is required before benchmark use.",
        "cases": cases,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_workbook(bank, xlsx_path)
    return bank


def _case(ordinal: int, query: str, query_type: str, difficulty: str, ids: list[str], roots: list[str], actions: list[str], record: dict[str, Any] | None) -> dict[str, Any]:
    language = "mixed" if re.search(r"[A-Za-z]", query) and re.search(r"[\u4e00-\u9fff]", query) else ("en" if re.fullmatch(r"[\x00-\x7F]+", query) else "zh")
    return {"query_id": f"RC-HQ-{ordinal:04d}", "query": query, "query_type": query_type, "difficulty": difficulty, "query_language": language, "expected_rag_candidate_ids": ids, "acceptable_root_causes": roots, "acceptable_countermeasures": actions, "source_rag_candidate_id": record.get("rag_candidate_id") if record else None, "review_status": "review_pending", "gold_status": "unreviewed", "review_notes": ""}


def _spread(records: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if len(records) <= count:
        return records
    step = len(records) / count
    return [records[min(int(index * step), len(records) - 1)] for index in range(count)]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _strip_punctuation(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]+", " ", value, flags=re.UNICODE).strip()


def _shorten(value: str) -> str:
    parts = [part for part in re.split(r"[，,；;。.!！?？\s]+", value) if part]
    return value[: max(6, len(value) // 2)] if len(parts) <= 1 else " ".join(parts[: max(1, len(parts) // 2)])


def _unique(values: Any) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _write_workbook(bank: dict[str, Any], path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "query_bank_review"
    columns = ["query_id", "query", "query_type", "difficulty", "query_language", "expected_rag_candidate_ids", "acceptable_root_causes", "acceptable_countermeasures", "source_rag_candidate_id", "review_status", "gold_status", "review_notes"]
    worksheet.append(columns)
    for case in bank["cases"]:
        worksheet.append([case[column] if not isinstance(case[column], list) else " || ".join(case[column]) for column in columns])
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for cell in worksheet[1]:
        cell.font = cell.font.copy(bold=True)
    for column in worksheet.columns:
        values = [len(str(cell.value or "")) for cell in column[:100]]
        column[0].parent.column_dimensions[column[0].column_letter].width = min(max(max(values, default=12) + 2, 12), 50)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()
    bank = build_bank(args.artifact, args.json, args.xlsx)
    print(json.dumps({"cases": len(bank["cases"]), "status": bank["status"], "json": args.json.as_posix(), "xlsx": args.xlsx.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
