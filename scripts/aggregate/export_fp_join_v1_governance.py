"""Export TASK-005 v1 baseline review workbook and RAG candidates.

The workbook is intentionally minimal for expert review. The companion
manifest keeps the trace fields and join keys needed for a later V2 import.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.aggregation.structured_fp_join import stable_id, write_json  # noqa: E402

CAUSE = "原因"
ACTION = "維修動作"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export TASK-005 v1 governance artifacts.")
    parser.add_argument("--aggregates-dir", default=str(PROJECT_ROOT / "data" / "processed" / "aggregates"))
    parser.add_argument("--processed-dir", default=str(PROJECT_ROOT / "data" / "processed"))
    parser.add_argument("--baseline-source-file", default="structured_fp_join_v1_semantic_bge_m3.json")
    parser.add_argument("--nomic-file", default="structured_fp_join_v1_semantic.json")
    parser.add_argument("--model-review-pack-file", default="structured_fp_join_v1_model_compare_review_pack.json")
    parser.add_argument("--baseline-output-file", default="structured_fp_join_v1_baseline.json")
    parser.add_argument("--baseline-summary-file", default="structured_fp_join_v1_baseline_summary.json")
    parser.add_argument("--workbook-output-file", default="structured_fp_join_v1_review_workbook.xlsx")
    parser.add_argument("--workbook-manifest-file", default="structured_fp_join_v1_review_workbook_manifest.json")
    parser.add_argument("--rag-output-file", default="rag_fp_case_candidates_v1.json")
    parser.add_argument("--include-nomic-for-baseline-covered-field-fps", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    aggregates_dir = Path(args.aggregates_dir)
    processed_dir = Path(args.processed_dir)
    generated_at = datetime.now(timezone.utc).isoformat()
    baseline_source = load_json(resolve_path(aggregates_dir, args.baseline_source_file))
    nomic_payload = load_json(resolve_path(aggregates_dir, args.nomic_file))
    review_pack = load_json(resolve_path(aggregates_dir, args.model_review_pack_file))
    downtime_records = load_json(processed_dir / "y25_downtime_canonical.json")
    downtime_by_index = {idx: record for idx, record in enumerate(downtime_records)}

    baseline = build_baseline(baseline_source, args.baseline_source_file, generated_at)
    sheets, workbook_manifest = build_review_workbook(baseline, downtime_by_index, generated_at)
    rag = build_rag_candidates(
        baseline,
        nomic_payload,
        review_pack,
        downtime_by_index,
        generated_at=generated_at,
        exclude_covered_field_fps=not args.include_nomic_for_baseline_covered_field_fps,
    )

    baseline_path = resolve_path(aggregates_dir, args.baseline_output_file)
    summary_path = resolve_path(aggregates_dir, args.baseline_summary_file)
    workbook_path = resolve_path(aggregates_dir, args.workbook_output_file)
    manifest_path = resolve_path(aggregates_dir, args.workbook_manifest_file)
    rag_path = resolve_path(aggregates_dir, args.rag_output_file)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(baseline_path, baseline, pretty=True)
    write_json(summary_path, build_baseline_summary(baseline), pretty=True)
    write_xlsx(workbook_path, sheets)
    write_json(manifest_path, workbook_manifest, pretty=True)
    write_json(rag_path, rag, pretty=True)

    print("TASK-005 v1 governance export")
    print(f"  baseline records: {len(baseline.get('records') or [])}")
    print(f"  workbook sheets: {', '.join(sheet['name'] for sheet in sheets)}")
    print(f"  workbook manifest entries: {workbook_manifest['summary']['total_manifest_entries']}")
    print(f"  rag candidates: {len(rag.get('candidates') or [])}")
    print(f"Wrote baseline: {baseline_path}")
    print(f"Wrote baseline summary: {summary_path}")
    print(f"Wrote review workbook: {workbook_path}")
    print(f"Wrote review workbook manifest: {manifest_path}")
    print(f"Wrote RAG candidates: {rag_path}")


def resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def build_baseline(payload: dict[str, Any], source_file: str, generated_at: str) -> dict[str, Any]:
    result = deepcopy(payload)
    metadata = result.setdefault("metadata", {})
    metadata["schema_version"] = "structured_fp_join_v1_baseline"
    metadata["generated_at"] = generated_at
    metadata["baseline"] = {
        "baseline_name": "structured_fp_join_v1_baseline",
        "source_file": source_file,
        "source_model": ((payload.get("metadata") or {}).get("provider") or {}).get("model"),
        "purpose": "Conservative KG/text2cypher review baseline for EC / standard FP / field FP / RC / PA chains.",
        "policy": "bge-m3 semantic candidates are review inputs only until human confirmed.",
    }
    return result


def build_baseline_summary(payload: dict[str, Any]) -> dict[str, Any]:
    records = payload.get("records") or []
    unmatched = payload.get("unmatched") or {}
    return {
        "schema_version": "structured_fp_join_v1_baseline_summary",
        "generated_at": (payload.get("metadata") or {}).get("generated_at"),
        "baseline": (payload.get("metadata") or {}).get("baseline"),
        "summary": {
            "complete_chain_review_records": len(records),
            "ec_fp_need_rc_pa_records": len(unmatched.get("error_code_fps") or []),
            "field_case_need_ec_fp_records": len(unmatched.get("downtime_fps") or []),
            "review_status_counts": dict(Counter(record.get("review_status") for record in records)),
            "route_target_counts": dict(Counter(record.get("route_target") for record in records)),
        },
        "sheets": {
            "A_ec_fp_need_rc_pa": "EC + standard FP without field RC/PA evidence.",
            "B_complete_chain_review": "bge-m3 candidate chains with EC, standard FP, field FP, RC, and PA.",
            "C_field_case_need_ec_fp": "field FP + RC/PA cases without reliable EC/standard FP link.",
        },
    }


def build_review_workbook(
    payload: dict[str, Any],
    downtime_by_index: dict[int, dict[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the expert workbook rows plus the authoritative trace manifest.

    The sheet ID columns are import join keys, not display-only labels; they
    must remain stable so reviewed workbook decisions can be joined back to
    source records without exposing the full trace payload to experts.
    """
    unmatched = payload.get("unmatched") or {}
    manifest = {
        "schema_version": "structured_fp_join_v1_review_workbook_manifest",
        "generated_at": generated_at,
        "metadata": {
            "purpose": "Trace manifest for the simplified expert review workbook.",
            "join_keys": {
                "A_ec_fp_need_rc_pa": "row_id",
                "B_complete_chain_review": "mapping_id",
                "C_field_case_need_ec_fp": "case_id",
            },
            "import_contract": "Use workbook decisions plus this manifest to generate reviewed V2 KG and RAG artifacts.",
        },
        "summary": {},
        "sheets": {
            "A_ec_fp_need_rc_pa": {},
            "B_complete_chain_review": {},
            "C_field_case_need_ec_fp": {},
        },
    }

    a_rows = []
    for index, item in enumerate(unmatched.get("error_code_fps") or [], start=1):
        row_id = f"A-{index:04d}"
        a_rows.append([row_id, "", item.get("EC"), item.get("FP"), "", ""])
        manifest["sheets"]["A_ec_fp_need_rc_pa"][row_id] = {"row_id": row_id, "source_record": item}

    b_rows = []
    for record in payload.get("records") or []:
        mapping_id = str(record.get("mapping_id") or stable_id(record.get("EC"), field_fp_normalized(record), prefix="MAP"))
        b_rows.append([
            mapping_id,
            "",
            record.get("EC"),
            record.get("standard_fp"),
            first_or_empty(record.get("field_fp_variants")),
            join_for_review(record.get("RC")),
            join_for_review(record.get("PA")),
        ])
        manifest["sheets"]["B_complete_chain_review"][mapping_id] = {"mapping_id": mapping_id, "source_record": record}

    c_rows = []
    for index, item in enumerate(unmatched.get("downtime_fps") or [], start=1):
        case_id = stable_id("case", item.get("normalized_fp"), index, prefix="CASE")
        records = records_from_refs(item.get("source_refs") or [], downtime_by_index)
        c_rows.append([
            case_id,
            "",
            first_or_empty(item.get("field_fp_variants")),
            join_for_review(unique_values(record.get(CAUSE) for record in records)),
            join_for_review(unique_values(record.get(ACTION) for record in records)),
            "",
            "",
        ])
        manifest["sheets"]["C_field_case_need_ec_fp"][case_id] = {
            "case_id": case_id,
            "source_record": item,
            "source_downtime_records": records,
        }

    sheets = [
        {
            "name": "A_ec_fp_need_rc_pa",
            "headers": ["row_id", "decision", "EC", "standard_fp", "add_RC", "add_RA"],
            "rows": a_rows,
            "editable_columns": [2, 5, 6],
            "id_column": 1,
            "allowed_decisions": ["fill", "skip", "unclear"],
        },
        {
            "name": "B_complete_chain_review",
            "headers": ["mapping_id", "decision", "EC", "standard_fp", "field_fp", "RC", "RA"],
            "rows": b_rows,
            "editable_columns": [2, 6, 7],
            "id_column": 1,
            "allowed_decisions": ["confirm", "edit", "reject", "unclear"],
        },
        {
            "name": "C_field_case_need_ec_fp",
            "headers": ["case_id", "decision", "field_fp", "RC", "RA", "add_EC", "add_standard_fp"],
            "rows": c_rows,
            "editable_columns": [2, 4, 5, 6, 7],
            "id_column": 1,
            "allowed_decisions": ["link", "rag", "exclude", "unclear"],
        },
    ]
    manifest["summary"] = {
        "A_ec_fp_need_rc_pa_rows": len(a_rows),
        "B_complete_chain_review_rows": len(b_rows),
        "C_field_case_need_ec_fp_rows": len(c_rows),
        "total_manifest_entries": len(a_rows) + len(b_rows) + len(c_rows),
    }
    return sheets, manifest


def build_rag_candidates(
    baseline: dict[str, Any],
    nomic: dict[str, Any],
    review_pack: dict[str, Any],
    downtime_by_index: dict[int, dict[str, Any]],
    *,
    generated_at: str,
    exclude_covered_field_fps: bool,
) -> dict[str, Any]:
    baseline_pairs = {candidate_pair_key(record) for record in baseline.get("records") or []}
    baseline_field_fps = {field_fp_normalized(record) for record in baseline.get("records") or []}
    rejected_pairs = rejected_nomic_pairs(review_pack)
    candidates: list[dict[str, Any]] = []

    for item in ((baseline.get("unmatched") or {}).get("downtime_fps") or []):
        records = records_from_refs(item.get("source_refs") or [], downtime_by_index)
        candidates.append({
            "rag_candidate_id": stable_id("field_case", item.get("normalized_fp"), prefix="RAG"),
            "source_type": "field_case_without_standard_fp",
            "relation_type": "case_evidence",
            "route_target": "rag_case_pool",
            "field_fp_variants": item.get("field_fp_variants"),
            "field_fp_normalized": item.get("normalized_fp"),
            "RC": unique_values(record.get(CAUSE) for record in records),
            "PA": unique_values(record.get(ACTION) for record in records),
            "evidence": item.get("evidence"),
            "source_refs": item.get("source_refs"),
            "filter_basis": {"reason": "No bge-m3 baseline EC/standard FP candidate above threshold."},
        })

    filter_counts: Counter[str] = Counter()
    # Nomic is retained only as a related-case recall source after removing
    # bge-m3 baseline coverage and sampled human rejects. These records must
    # not be promoted into the KG/text2cypher baseline by this exporter.
    for record in nomic.get("records") or []:
        pair = candidate_pair_key(record)
        field_fp = field_fp_normalized(record)
        if pair in baseline_pairs:
            filter_counts["excluded_baseline_pair"] += 1
            continue
        if exclude_covered_field_fps and field_fp in baseline_field_fps:
            filter_counts["excluded_baseline_field_fp"] += 1
            continue
        if pair in rejected_pairs:
            filter_counts["excluded_human_rejected"] += 1
            continue
        candidates.append({
            "rag_candidate_id": stable_id("nomic_related", record.get("EC"), field_fp, prefix="RAG"),
            "source_type": "nomic_semantic_related_candidate",
            "relation_type": "related_case_hint",
            "route_target": "rag_case_pool",
            "EC": record.get("EC"),
            "standard_fp": record.get("standard_fp"),
            "standard_fp_normalized": standard_fp_normalized(record),
            "field_fp_variants": record.get("field_fp_variants"),
            "field_fp_normalized": field_fp,
            "RC": record.get("RC"),
            "PA": record.get("PA"),
            "semantic_score": record.get("semantic_score"),
            "embedding_similarity": record.get("embedding_similarity"),
            "feature_similarity": record.get("feature_similarity"),
            "shared_features": ((record.get("match_basis") or {}).get("shared_features") or {}),
            "evidence": record.get("evidence"),
            "source_refs": record.get("source_refs"),
            "filter_basis": {
                "reason": "Filtered nomic candidate retained for RAG only; not a standard FP mapping.",
                "not_for_kg_text2cypher": True,
            },
        })
        filter_counts["retained_nomic_related"] += 1

    source_counts = Counter(candidate["source_type"] for candidate in candidates)
    return {
        "schema_version": "rag_fp_case_candidates_v1",
        "generated_at": generated_at,
        "metadata": {
            "purpose": "RAG-only case pool for field cases and semantic related hints that are not baseline KG mappings.",
            "baseline_source": "structured_fp_join_v1_baseline",
            "nomic_policy": "Retain as related-case hints after excluding bge-m3 baseline coverage and human-rejected pairs.",
        },
        "summary": {
            "candidate_count": len(candidates),
            "source_type_counts": dict(sorted(source_counts.items())),
            "nomic_filter_counts": dict(sorted(filter_counts.items())),
        },
        "candidates": candidates,
    }


def rejected_nomic_pairs(review_pack: dict[str, Any]) -> set[tuple[str, str, str]]:
    rejected: set[tuple[str, str, str]] = set()
    for item in review_pack.get("review_items") or []:
        decision = str(item.get("review_decision") or "").strip()
        if not decision:
            continue
        field_fp = item.get("field_fp_normalized")
        if item.get("candidate") and decision == "neither":
            rejected.add(compact_candidate_key(item["candidate"], field_fp))
        if item.get("left_top1_candidate") and item.get("right_top1_candidate"):
            if decision in {"neither", "prefer_right"}:
                rejected.add(compact_candidate_key(item["left_top1_candidate"], field_fp))
            if decision in {"neither", "prefer_left"}:
                rejected.add(compact_candidate_key(item["right_top1_candidate"], field_fp))
    return rejected


def records_from_refs(source_refs: list[dict[str, Any]], downtime_by_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for ref in source_refs:
        if not isinstance(ref, dict) or ref.get("source") != "y25_downtime":
            continue
        index = ref.get("record_index")
        if isinstance(index, int) and index in downtime_by_index:
            records.append(downtime_by_index[index])
    return records


def first_or_empty(values: Any) -> str:
    return str(values[0]) if isinstance(values, list) and values else ""


def unique_values(values: Any) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def join_for_review(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, list):
        return "\n---\n".join(str(value).strip() for value in values if str(value or "").strip())
    return str(values).strip()


def candidate_pair_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("EC") or ""), standard_fp_normalized(record), field_fp_normalized(record))


def compact_candidate_key(candidate: dict[str, Any], field_fp: Any) -> tuple[str, str, str]:
    return (str(candidate.get("EC") or ""), str(candidate.get("standard_fp_normalized") or "").strip(), str(field_fp or "").strip())


def field_fp_normalized(record: dict[str, Any]) -> str:
    return str(((record.get("match_basis") or {}).get("field_fp_normalized") or "")).strip()


def standard_fp_normalized(record: dict[str, Any]) -> str:
    return str(((record.get("match_basis") or {}).get("standard_fp_normalized") or "")).strip()


def write_xlsx(path: Path, sheets: list[dict[str, Any]]) -> None:
    import zipfile
    from xml.sax.saxutils import escape

    def esc(value: Any) -> str:
        return escape(str(value), {"'": "&apos;", '"': "&quot;"})

    def cell_ref(row_idx: int, col_idx: int) -> str:
        letters = ""
        n = col_idx
        while n:
            n, rem = divmod(n - 1, 26)
            letters = chr(65 + rem) + letters
        return f"{letters}{row_idx}"

    def normalize(value: Any) -> tuple[str, str]:
        if isinstance(value, (dict, list)):
            return "text", json.dumps(value, ensure_ascii=False)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return "number", str(value)
        text = "" if value is None else str(value)
        if text.startswith(("=", "+", "-", "@")):
            text = "'" + text
        if len(text) > 32767:
            text = text[:32740] + "...[truncated]"
        return "text", text

    def sheet_xml(sheet: dict[str, Any]) -> str:
        rows = [sheet.get("headers") or []] + list(sheet.get("rows") or [])
        xml_rows = []
        for row_idx, row in enumerate(rows, start=1):
            cells = []
            for col_idx, value in enumerate(row, start=1):
                cell_type, cell_value = normalize(value)
                ref = cell_ref(row_idx, col_idx)
                if cell_type == "number":
                    cells.append(f'<c r="{ref}"><v>{cell_value}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{esc(cell_value)}</t></is></c>')
            xml_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')
        max_col = len(sheet.get("headers") or [])
        auto_filter_ref = f"A1:{cell_ref(1, max_col)}" if max_col else "A1:A1"
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<sheetData>' + "".join(xml_rows) + '</sheetData>'
            f'<autoFilter ref="{auto_filter_ref}"/>'
            '</worksheet>'
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(len(sheets)))
        zf.writestr("_rels/.rels", root_rels_xml())
        zf.writestr("xl/workbook.xml", workbook_xml([sheet["name"] for sheet in sheets]))
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml(len(sheets)))
        zf.writestr("xl/styles.xml", styles_xml())
        for index, sheet in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(sheet))


def content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'{sheet_overrides}</Types>'
    )


def root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )


def workbook_xml(sheet_names: list[str]) -> str:
    from xml.sax.saxutils import escape
    sheets_xml = "".join(
        f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheets_xml}</sheets></workbook>'
    )


def workbook_rels_xml(sheet_count: int) -> str:
    sheet_rels = "".join(
        f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        for idx in range(1, sheet_count + 1)
    )
    style_rel = f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{sheet_rels}{style_rel}</Relationships>'
    )


def styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '</styleSheet>'
    )


if __name__ == "__main__":
    main()
