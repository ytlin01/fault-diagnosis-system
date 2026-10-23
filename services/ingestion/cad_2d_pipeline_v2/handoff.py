from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


JSON_PATHS = {
    "a01": Path("run_results/intermediate_json/A01_classification/drawing_class_merged.json"),
    "a02": Path("run_results/intermediate_json/A02_title_fields/title_fields.json"),
    "a03": Path("run_results/intermediate_json/A03_drawing_index/drawing_index.json"),
    "b01": Path("run_results/intermediate_json/B01_asm_bom/asm_bom.json"),
    "b02": Path("run_results/intermediate_json/B02_audit/asm_bom_audit_report.json"),
    "b02_history": Path(
        "run_results/intermediate_json/B02_audit/asm_bom_audit_report_V1_20260611_record.json"
    ),
    "c01_edges": Path("run_results/final_json/C01_relationships/C01_bom_edges.json"),
    "c01_combined": Path("run_results/final_json/C01_relationships/C01_combined.json"),
    "c02": Path("run_results/final_json/C01_project_owner_final/project_owner_final.json"),
    "round1": Path("user_inputs/classification_json/Round1_tfpn_summary.json"),
    "round2": Path("user_inputs/manual_review_notes/Round2_review_A_S.json"),
}


@dataclass(frozen=True)
class HandoffSnapshot:
    classifications: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    drawing_index: list[dict[str, Any]]
    bom_parents: list[dict[str, Any]]
    source_findings: list[dict[str, Any]]
    evidence: dict[str, Any]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid cleaned-handoff JSON: {path.name}") from error


def _require_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be a list of mappings")
    return value


def _ids(rows: list[dict], label: str) -> set[str]:
    values = []
    for row in rows:
        value = row.get("part_number")
        if value is None or not str(value).strip():
            raise ValueError(f"{label} contains a blank part_number")
        values.append(str(value).strip())
    if len(values) != len(set(values)):
        raise ValueError(f"{label} contains duplicate part_number values")
    return set(values)


def _decision(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {"ASM", "PRT", "UNKNOWN"}:
        raise ValueError("cleaned handoff contains an unsupported classification decision")
    return normalized


def _file_manifest(root: Path) -> tuple[list[dict[str, Any]], str]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    identity = hashlib.sha256(
        json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return files, f"cad2d_handoff_{identity}"


def load_cleaned_handoff(root: str | Path) -> HandoffSnapshot:
    """Validate and normalize the authorized cleaned handoff without copying it."""

    source_root = Path(root)
    if not source_root.is_dir():
        raise ValueError("cleaned handoff root is not a directory")
    missing = [str(path) for path in JSON_PATHS.values() if not (source_root / path).is_file()]
    if missing:
        raise ValueError(f"cleaned handoff is incomplete; missing_count={len(missing)}")
    raw = {name: _load_json(source_root / path) for name, path in JSON_PATHS.items()}

    a01 = _require_list(raw["a01"], "A01")
    if not isinstance(raw["a02"], dict):
        raise ValueError("A02 must be an identifier-to-field mapping")
    a03 = _require_list(raw["a03"], "A03")
    if not isinstance(raw["b01"], dict):
        raise ValueError("B01 must be an ASM-to-rows mapping")
    c01_edges = _require_list(raw["c01_edges"], "C01 edges")
    c01_combined = _require_list(raw["c01_combined"], "C01 combined")
    c02 = _require_list(raw["c02"], "C02")
    round2 = _require_list(raw["round2"].get("items"), "Round2 items")

    a01_ids = _ids(a01, "A01")
    a03_ids = _ids(a03, "A03")
    combined_ids = _ids(c01_combined, "C01 combined")
    c02_ids = _ids(c02, "C02")
    a02_ids = {str(value).strip() for value in raw["a02"]}
    if len(a02_ids) != len(raw["a02"]) or "" in a02_ids:
        raise ValueError("A02 contains blank or duplicate identifiers")
    if not (a01_ids == a03_ids == combined_ids == c02_ids):
        raise ValueError("A01/A03/C01/C02 identifier sets disagree")
    if not a01_ids <= a02_ids:
        raise ValueError("A01 identifiers are not a subset of A02")

    round1 = raw["round1"]
    buckets = []
    for name in ("tp", "tn", "fp", "fn"):
        buckets.extend(_require_list(round1.get(name), f"Round1 {name}"))
    if _ids(buckets, "Round1 buckets") != a01_ids:
        raise ValueError("Round1 buckets do not partition A01")
    round2_ids = _ids(round2, "Round2")
    if not round2_ids <= a01_ids:
        raise ValueError("Round2 is not a subset of A01")

    classifications = []
    non_boolean_review_flags = 0
    for row in a01:
        flag = row.get("review_needed", False)
        non_boolean_review_flags += int(not isinstance(flag, bool))
        normalized = dict(row)
        normalized["part_number"] = str(row["part_number"]).strip()
        normalized["decision"] = _decision(row.get("decision"))
        normalized["drawing_type"] = _decision(row.get("drawing_type"))
        normalized["review_needed"] = normalized["part_number"] in round2_ids
        normalized["review_state"] = (
            "human_reviewed" if normalized["part_number"] in round2_ids else "first_pass"
        )
        classifications.append(normalized)

    fields = [
        {
            "part_number": str(part_number).strip(),
            "drawing_title": str(values.get("drawing_title") or ""),
            "project_name": str(values.get("project_name") or ""),
        }
        for part_number, values in raw["a02"].items()
        if isinstance(values, dict)
    ]
    if len(fields) != len(raw["a02"]):
        raise ValueError("A02 values must all be mappings")

    drawing_index = [
        {
            "part_number": str(row["part_number"]).strip(),
            "drawing_type": _decision(row.get("drawing_type")),
            "drawing_title": str(row.get("drawing_title") or ""),
            "project_name": str(row.get("project_name") or ""),
        }
        for row in a03
    ]
    final_decisions = {row["part_number"]: row["decision"] for row in classifications}
    if any(final_decisions[row["part_number"]] != row["drawing_type"] for row in drawing_index):
        raise ValueError("A03 does not preserve A01 final decisions")

    bom_parents = []
    valid_bom_rows = 0
    blank_child_rows = 0
    for parent, rows in raw["b01"].items():
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("B01 parent values must be lists of mappings")
        normalized_rows = []
        for row in rows:
            child = str(row.get("part_number") or "").strip()
            blank_child_rows += int(not child)
            valid_bom_rows += int(bool(child))
            normalized_rows.append(
                {
                    "item_no": str(row.get("item_no") or "").strip(),
                    "part_number": child,
                    "description": str(row.get("description") or ""),
                    "quantity": row.get("qty"),
                }
            )
        bom_parents.append(
            {"parent_part_number": str(parent).strip(), "rows": normalized_rows}
        )

    edge_keys = {
        (
            str(row.get("asm") or "").strip(),
            str(row.get("prt") or "").strip(),
            str(row.get("item_no") or "").strip(),
            str(row.get("qty") or "").strip(),
        )
        for row in c01_edges
    }
    bom_keys = {
        (
            parent["parent_part_number"],
            row["part_number"],
            row["item_no"],
            str(row.get("quantity") or "").strip(),
        )
        for parent in bom_parents
        for row in parent["rows"]
        if row["part_number"]
    }
    if edge_keys != bom_keys:
        raise ValueError("historical C01 edges disagree with nonblank B01 rows")

    b02 = raw["b02"]
    if not isinstance(b02, dict) or not isinstance(b02.get("issues_by_asm"), dict):
        raise ValueError("B02 audit shape is invalid")
    source_findings = []
    for parent, issues in b02["issues_by_asm"].items():
        for issue in _require_list(issues, "B02 issues"):
            source_findings.append(
                {
                    "parent_part_number": str(parent).strip(),
                    "code": issue.get("code"),
                    "severity": issue.get("severity"),
                    "row_number": (
                        issue.get("row_index") + 1
                        if isinstance(issue.get("row_index"), int)
                        else None
                    ),
                    "item_no": issue.get("item_no"),
                }
            )

    files, snapshot_id = _file_manifest(source_root)
    evidence = {
        "manifest_version": "cad-2d-cleaned-handoff-evidence-v1",
        "snapshot_id": snapshot_id,
        "source_role": "reference_candidate",
        "serving_eligible": False,
        "graph_activation": False,
        "promotion_state": "blocked_pending_governance_and_b02_resolution",
        "files": files,
        "counts": {
            "a02_source_count": len(a02_ids),
            "classified_count": len(a01_ids),
            "a02_only_count": len(a02_ids - a01_ids),
            "round2_review_count": len(round2_ids),
            "non_boolean_review_flag_count": non_boolean_review_flags,
            "asm_count": sum(row["drawing_type"] == "ASM" for row in drawing_index),
            "prt_count": sum(row["drawing_type"] == "PRT" for row in drawing_index),
            "bom_parent_count": len(bom_parents),
            "bom_row_count": sum(len(parent["rows"]) for parent in bom_parents),
            "blank_child_row_count": blank_child_rows,
            "historical_c01_edge_count": len(c01_edges),
            "valid_bom_row_count": valid_bom_rows,
            "source_b02_finding_count": len(source_findings),
            "title_missing_count": sum(not row["drawing_title"] for row in drawing_index),
            "project_missing_count": sum(not row["project_name"] for row in drawing_index),
        },
        "validated_invariants": [
            "a01_a03_c01_c02_identifier_sets_equal",
            "a01_subset_of_a02",
            "round1_partitions_a01",
            "round2_subset_of_a01",
            "a03_preserves_a01_final_decision",
            "c01_edges_equal_nonblank_b01_rows",
        ],
        "exclusions": [
            "no_direct_copy_into_route_a",
            "no_occurrence_identity_inference_from_part_number",
            "no_material_fields_present",
            "no_graph_activation",
        ],
        "documentation_conflicts": [
            "source_manifest_claims_no_real_json_but_eleven_json_payloads_are_present",
            "validation_report_claims_synthetic_only_but_real_outputs_are_present",
        ],
    }
    return HandoffSnapshot(
        classifications=classifications,
        fields=fields,
        drawing_index=drawing_index,
        bom_parents=bom_parents,
        source_findings=source_findings,
        evidence=evidence,
    )


def compare_legacy_triples(triples: Any, drawing_index: list[dict]) -> dict[str, Any]:
    """Return identifier-safe name-overlap evidence; never assert an occurrence join."""

    if not isinstance(triples, dict) or not isinstance(triples.get("nodes"), list):
        raise ValueError("legacy triples bundle is invalid")
    names: dict[str, int] = {}
    for node in triples["nodes"]:
        if not isinstance(node, dict):
            raise ValueError("legacy triples nodes must be mappings")
        name = str((node.get("properties") or {}).get("name") or "").strip().casefold()
        if name:
            names[name] = names.get(name, 0) + 1
    drawings = {str(row.get("part_number") or "").strip().casefold() for row in drawing_index}
    drawings.discard("")
    overlap = drawings & set(names)
    return {
        "comparison_state": "display_name_overlap_only",
        "join_approved": False,
        "legacy_node_count": len(triples["nodes"]),
        "drawing_identifier_count": len(drawings),
        "exact_display_name_overlap_count": len(overlap),
        "ambiguous_display_name_overlap_count": sum(names[value] > 1 for value in overlap),
        "reason": "part numbers are reusable definitions; v4.2 nodes require governed occurrence identities",
    }
