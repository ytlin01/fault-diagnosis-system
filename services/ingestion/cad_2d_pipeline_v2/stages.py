from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Iterable

from services.ingestion.cad_2d_pipeline_v2.artifacts import sha256_value


@dataclass(frozen=True)
class StageResult:
    records: list[dict[str, Any]]
    audit: dict[str, Any]
    exclusions: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {"records": self.records, "audit": self.audit, "exclusions": self.exclusions}


def _identifier(value: Any, *, suffixes: Iterable[str] = ()) -> str:
    if value is None or not str(value).strip():
        raise ValueError("part_number must not be blank")
    normalized = str(value).strip()
    for suffix in suffixes:
        if suffix and normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    if not normalized:
        raise ValueError("part_number normalizes to blank")
    return normalized


def _index_unique(records: list[dict], *, suffixes: Iterable[str] = ()) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("records must contain mappings")
        key = _identifier(record.get("part_number"), suffixes=suffixes)
        if key in indexed:
            raise ValueError(f"duplicate or normalized-colliding part_number: {key}")
        indexed[key] = record
    return indexed


def _canonical_decision(value: Any, config: dict) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("classification decision must not be blank")
    aliases = config["classification"].get("decision_aliases", {})
    candidate = aliases.get(value.strip().casefold(), value.strip())
    if candidate not in config["classification"]["allowed_decisions"]:
        raise ValueError("unsupported classification decision")
    return candidate


def merge_classifications(
    reviewed: list[dict],
    full: list[dict],
    config: dict,
    *,
    allow_reviewed_additions: bool = False,
) -> StageResult:
    full_by_id = _index_unique(full)
    reviewed_by_id = _index_unique(reviewed)
    unknown = sorted(set(reviewed_by_id) - set(full_by_id))
    if unknown and not allow_reviewed_additions:
        raise ValueError(f"reviewed classification is not a subset; count={len(unknown)}")

    authority_records = list(full)
    if unknown:
        authority_records.extend(
            {
                "part_number": record["part_number"],
                "decision": "UNKNOWN",
                "source_state": "reviewed_classification_addition",
            }
            for record in reviewed
            if _identifier(record["part_number"]) in set(unknown)
        )

    for source_name, records in (("full", authority_records), ("reviewed", reviewed)):
        for record in records:
            try:
                _canonical_decision(record.get("decision"), config)
            except ValueError as exc:
                raise ValueError(f"{source_name} has unsupported decision") from exc

    output: list[dict] = []
    changed = 0
    consistency_findings = 0
    for record in authority_records:
        key = _identifier(record["part_number"])
        candidate = dict(record)
        if key in reviewed_by_id:
            review = reviewed_by_id[key]
            old = _canonical_decision(record["decision"], config)
            candidate["decision"] = _canonical_decision(review["decision"], config)
            candidate["review_note"] = (
                review.get("human_review_reason")
                or review.get("review_reason")
                or review.get("review_note", "")
            )
            candidate["review_state"] = "reviewed"
            for governed_key in (
                "reviewer",
                "reviewed_at",
                "evidence_id",
                "canonical_definition_id",
                "identity_basis",
                "view_grouping",
                "aliases",
                "page_count",
                "exclusion_reason_code",
            ):
                if governed_key in review:
                    candidate[governed_key] = review[governed_key]
            changed += int(old != candidate["decision"])
            first_pass = review.get("drawing_type")
            consistency_findings += int(first_pass is not None and first_pass != old)
        else:
            candidate["decision"] = _canonical_decision(record["decision"], config)
            candidate["review_note"] = config["classification"]["unreviewed_note"]
            candidate["review_state"] = "unreviewed"
        candidate["promotion_eligible"] = candidate["decision"] not in {
            "EXCLUDE",
            "UNKNOWN",
        }
        output.append(candidate)
    if len(output) != len(authority_records):
        raise RuntimeError("A01 row-count invariant failed")
    return StageResult(
        output,
        {
            "stage": "A01",
            "input_full_count": len(full),
            "input_reviewed_count": len(reviewed),
            "reviewed_addition_count": len(unknown),
            "output_count": len(output),
            "changed_decision_count": changed,
            "first_pass_consistency_finding_count": consistency_findings,
        },
        [
            {
                "reason_code": (
                    "REVIEWED_EXCLUSION"
                    if record["decision"] == "EXCLUDE"
                    else "UNRESOLVED_CLASSIFICATION"
                ),
                "record_index": index,
            }
            for index, record in enumerate(output)
            if not record["promotion_eligible"]
        ],
    )


def _word_parts(word: Any) -> tuple[float, float, float, float, str]:
    if isinstance(word, dict):
        values = (word.get("x0"), word.get("y0"), word.get("x1"), word.get("y1"), word.get("text"))
    elif isinstance(word, (list, tuple)) and len(word) >= 5:
        values = tuple(word[:5])
    else:
        raise ValueError("word must contain x0, y0, x1, y1, text")
    if not all(isinstance(v, (int, float)) for v in values[:4]) or not isinstance(values[4], str):
        raise ValueError("word coordinates/text are invalid")
    return float(values[0]), float(values[1]), float(values[2]), float(values[3]), values[4]


def _words_in_box(words: list[Any], box: list[float]) -> str:
    selected = []
    for raw in words:
        x0, y0, x1, y1, text = _word_parts(raw)
        center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
        if box[0] <= center_x <= box[2] and box[1] <= center_y <= box[3] and text.strip():
            selected.append((round(y0, 3), x0, text.strip()))
    selected.sort(key=lambda item: (item[0], item[1], item[2]))
    return " ".join(item[2] for item in selected)


def extract_fields(documents: list[dict], config: dict) -> StageResult:
    profiles = config["field_extraction"]["profiles"]
    default = config["field_extraction"]["default_profile"]
    suffixes = config["identifier"]["strip_suffixes"]
    seen: set[str] = set()
    output: list[dict] = []
    exclusions: list[dict] = []
    for document in documents:
        key = _identifier(document.get("part_number"), suffixes=suffixes)
        if key in seen:
            raise ValueError(f"duplicate or normalized-colliding part_number: {key}")
        seen.add(key)
        profile_name = document.get("template_profile", default)
        if profile_name not in profiles:
            exclusions.append({"reason_code": "UNKNOWN_TEMPLATE_PROFILE", "record_index": len(output) + len(exclusions)})
            continue
        words = document.get("words")
        if not isinstance(words, list):
            exclusions.append({"reason_code": "WORDS_UNAVAILABLE", "record_index": len(output) + len(exclusions)})
            continue
        profile = profiles[profile_name]
        record = {"part_number": key, "template_profile": profile_name, "extraction_state": "extracted"}
        for field, box in profile["regions"].items():
            record[field] = _words_in_box(words, box)
        output.append(record)
    return StageResult(
        output,
        {"stage": "A02", "input_count": len(documents), "output_count": len(output), "exclusion_count": len(exclusions)},
        exclusions,
    )


def build_drawing_index(classifications: list[dict], fields: list[dict], config: dict) -> StageResult:
    suffixes = config["identifier"]["strip_suffixes"]
    class_by_id = _index_unique(classifications, suffixes=suffixes)
    field_by_id = _index_unique(fields, suffixes=suffixes)
    output = []
    missing_fields = 0
    for source in classifications:
        key = _identifier(source.get("part_number"), suffixes=suffixes)
        extracted = field_by_id.get(key)
        missing_fields += int(extracted is None)
        output.append(
            {
                "part_number": key,
                "drawing_type": source.get("decision"),
                "drawing_title": "" if extracted is None else extracted.get("drawing_title", ""),
                "project_name": "" if extracted is None else extracted.get("project_name", ""),
                "promotion_eligible": source.get("promotion_eligible", True),
                "canonical_definition_id": source.get("canonical_definition_id"),
                "evidence_id": source.get("evidence_id"),
                "identity_basis": source.get("identity_basis"),
                "view_grouping": source.get("view_grouping"),
                "aliases": source.get("aliases", []),
                "page_count": source.get("page_count"),
                "exclusion_reason_code": source.get("exclusion_reason_code"),
            }
        )
    field_only = sorted(set(field_by_id) - set(class_by_id))
    exclusions = [{"reason_code": "FIELD_ONLY_IDENTIFIER", "record_index": index} for index, _ in enumerate(field_only)]
    exclusions.extend(
        {
            "reason_code": (
                "REVIEWED_EXCLUSION"
                if row.get("drawing_type") == "EXCLUDE"
                else "UNRESOLVED_CLASSIFICATION"
            ),
            "record_index": index,
        }
        for index, row in enumerate(output)
        if not row.get("promotion_eligible", True)
    )
    return StageResult(
        output,
        {
            "stage": "A03",
            "classification_count": len(classifications),
            "field_count": len(fields),
            "output_count": len(output),
            "missing_field_count": missing_fields,
            "field_only_count": len(field_only),
        },
        exclusions,
    )


def _group_rows(words: list[Any], tolerance: float) -> list[list[tuple[float, float, float, float, str]]]:
    ordered = sorted((_word_parts(word) for word in words), key=lambda word: (word[1], word[0], word[4]))
    rows: list[list[tuple[float, float, float, float, str]]] = []
    for word in ordered:
        if not rows or abs(word[1] - rows[-1][0][1]) > tolerance:
            rows.append([word])
        else:
            rows[-1].append(word)
    return rows


def _find_header(rows: list[list[tuple]], keywords: dict[str, list[str]], minimum: int) -> tuple[int, dict[str, float]] | None:
    lowered = {column: [value.casefold() for value in values] for column, values in keywords.items()}
    for index, row in enumerate(rows):
        matches: dict[str, float] = {}
        for x0, _, x1, _, text in row:
            folded = text.casefold()
            for column, terms in lowered.items():
                if column not in matches and any(term in folded for term in terms):
                    matches[column] = (x0 + x1) / 2
        if len(matches) >= minimum and all(column in matches for column in ("item", "part_number", "quantity")):
            if any(
                any(
                    abs(matches[optional] - matches[required]) < 1.0
                    for required in ("item", "part_number", "quantity")
                )
                for optional in set(matches) - {"item", "part_number", "quantity"}
            ):
                continue
            return index, matches
    return None


def extract_asm_bom(drawing_index: list[dict], word_documents: list[dict], config: dict) -> StageResult:
    suffixes = config["identifier"]["strip_suffixes"]
    for document in word_documents:
        if not isinstance(document, dict):
            raise ValueError("word documents must contain mappings")
        digest = document.get("source_pdf_sha256")
        if (
            document.get("extraction_state")
            != "local_reviewed_asm_word_geometry"
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(document.get("page_index"), int)
            or not isinstance(document.get("page_count"), int)
            or document["page_count"] <= document["page_index"]
            or document["page_index"] < 0
        ):
            raise ValueError("word document lacks reviewed-PDF provenance")
    documents = _index_unique(word_documents, suffixes=suffixes)
    approved = config["bom"]["approved_parent_decision"]
    thresholds = config["bom"]["thresholds"]
    item_pattern = re.compile(config["bom"]["item_number_pattern"])
    outputs: list[dict] = []
    exclusions: list[dict] = []
    for source_index, drawing in enumerate(drawing_index):
        if drawing.get("drawing_type") != approved:
            continue
        parent = _identifier(drawing.get("part_number"), suffixes=suffixes)
        document = documents.get(parent)
        if document is None or not isinstance(document.get("words"), list):
            exclusions.append({"reason_code": "BOM_SOURCE_UNAVAILABLE", "record_index": source_index, "parent_part_number": parent})
            continue
        rows = _group_rows(document["words"], float(thresholds["row_y_tolerance"]))
        header = _find_header(rows, config["bom"]["header_keywords"], int(thresholds["min_header_matches"]))
        if header is None:
            exclusions.append({"reason_code": "RELIABLE_BOM_HEADER_NOT_FOUND", "record_index": source_index, "parent_part_number": parent})
            continue
        header_index, centers = header
        ordered_columns = sorted(centers, key=centers.get)
        boundaries = [(centers[ordered_columns[i]] + centers[ordered_columns[i + 1]]) / 2 for i in range(len(ordered_columns) - 1)]
        parsed_rows: list[dict] = []
        candidates: list[dict[str, Any]] = []
        for row_number, row in enumerate(rows[header_index + 1 :], start=1):
            cells = {column: [] for column in ordered_columns}
            for x0, y0, x1, y1, text in row:
                x = (x0 + x1) / 2
                column_index = sum(x > boundary for boundary in boundaries)
                cells[ordered_columns[column_index]].append(
                    (x0, y0, x1, y1, text.strip())
                )
            item_cells = [
                cell
                for cell in cells.get("item", [])
                if item_pattern.fullmatch(cell[4]) is not None
                and abs((cell[0] + cell[2]) / 2 - centers["item"])
                <= float(thresholds["item_anchor_tolerance"])
            ]
            if len(item_cells) != 1:
                continue
            candidates.append(
                {
                    "row_number": row_number,
                    "item": item_cells[0][4],
                    "y": (item_cells[0][1] + item_cells[0][3]) / 2,
                    "part_words": list(cells.get("part_number", [])),
                    "quantity_words": list(cells.get("quantity", [])),
                }
            )

        candidate_rows = {candidate["row_number"] for candidate in candidates}
        if candidates:
            minimum_outer_margin = float(thresholds["row_y_tolerance"]) * 2
            top_margin = (
                max(
                    minimum_outer_margin,
                    (candidates[1]["y"] - candidates[0]["y"]) / 2,
                )
                if len(candidates) > 1
                else minimum_outer_margin
            )
            bottom_margin = (
                max(
                    minimum_outer_margin,
                    (candidates[-1]["y"] - candidates[-2]["y"]) / 2,
                )
                if len(candidates) > 1
                else minimum_outer_margin
            )
            table_top = candidates[0]["y"] - top_margin
            table_bottom = candidates[-1]["y"] + bottom_margin
            part_index = ordered_columns.index("part_number")
            part_left = boundaries[part_index - 1] if part_index else float("-inf")
            part_right = boundaries[part_index] if part_index < len(boundaries) else float("inf")
            for row_number, row in enumerate(rows[header_index + 1 :], start=1):
                if row_number in candidate_rows:
                    continue
                owned_part_words = [
                    word
                    for word in row
                    if part_left < (word[0] + word[2]) / 2 < part_right
                    and table_top <= (word[1] + word[3]) / 2 <= table_bottom
                ]
                if owned_part_words:
                    exclusions.append(
                        {
                            "reason_code": "AMBIGUOUS_BOM_PART_CONTINUATION",
                            "record_index": source_index,
                            "row_number": row_number,
                            "parent_part_number": parent,
                        }
                    )

        for candidate in candidates:
            quantity_cells = [
                word
                for word in candidate["quantity_words"]
                if item_pattern.fullmatch(word[4]) is not None
                and abs((word[0] + word[2]) / 2 - centers["quantity"])
                <= float(thresholds["quantity_anchor_tolerance"])
            ]
            if len(quantity_cells) != 1:
                exclusions.append({"reason_code": "INVALID_BOM_QUANTITY", "record_index": source_index, "row_number": candidate["row_number"], "parent_part_number": parent})
                continue
            quantity = int(quantity_cells[0][4])
            part_number = " ".join(
                word[4]
                for word in sorted(
                    candidate["part_words"], key=lambda word: (word[1], word[0])
                )
            ).strip()
            if not part_number or not (thresholds["min_quantity"] <= quantity <= thresholds["max_quantity"]):
                reason = "BLANK_BOM_PART_NUMBER" if not part_number else "BOM_QUANTITY_OUT_OF_RANGE"
                exclusions.append({"reason_code": reason, "record_index": source_index, "row_number": candidate["row_number"], "parent_part_number": parent})
                continue
            parsed_rows.append({"item": candidate["item"], "part_number": part_number, "quantity": quantity})
        if not parsed_rows:
            exclusions.append({"reason_code": "NO_RELIABLE_BOM_ROWS", "record_index": source_index, "parent_part_number": parent})
            continue
        outputs.append(
            {
                "parent_part_number": parent,
                "rows": parsed_rows,
                "extraction_state": "candidate",
                "bom_source": "fresh_reviewed_pdf_words",
                "source_pdf_sha256": document.get("source_pdf_sha256"),
                "page_index": document.get("page_index"),
                "page_count": document.get("page_count"),
            }
        )
    return StageResult(
        outputs,
        {
            "stage": "B01",
            "drawing_count": len(drawing_index),
            "approved_asm_count": sum(1 for row in drawing_index if row.get("drawing_type") == approved),
            "output_parent_count": len(outputs),
            "finding_count": len(exclusions),
        },
        exclusions,
    )


def reuse_historical_bom_candidates(
    drawing_index: list[dict], historical_bom: dict[str, Any], config: dict
) -> StageResult:
    """Filter governed historical structured BOM evidence to currently reviewed ASM.

    This is explicitly not a fresh PDF extraction. Missing newly reviewed ASM
    remain visible as source-unavailable findings for B02.
    """

    if not isinstance(historical_bom, dict):
        raise ValueError("historical BOM input must be an object keyed by parent")
    suffixes = config["identifier"]["strip_suffixes"]
    approved = config["bom"]["approved_parent_decision"]
    drawings = _index_unique(drawing_index, suffixes=suffixes)
    normalized_historical: dict[str, list[Any]] = {}
    for raw_parent, rows in historical_bom.items():
        parent = _identifier(raw_parent, suffixes=suffixes)
        if parent in normalized_historical:
            raise ValueError("historical BOM contains normalized-colliding parents")
        if not isinstance(rows, list):
            raise ValueError("historical BOM parent value must be a list")
        normalized_historical[parent] = rows

    outputs: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    approved_parents = [
        (_identifier(drawing.get("part_number"), suffixes=suffixes), record_index)
        for record_index, drawing in enumerate(drawing_index)
        if drawing.get("drawing_type") == approved
    ]
    for parent, record_index in approved_parents:
        if parent not in normalized_historical:
            exclusions.append(
                {
                    "reason_code": "BOM_SOURCE_UNAVAILABLE",
                    "record_index": record_index,
                    "parent_part_number": parent,
                }
            )
            continue
        normalized_rows = []
        for row_number, row in enumerate(normalized_historical[parent], start=1):
            if not isinstance(row, dict):
                normalized_rows.append(
                    {"row_number": row_number, "source_row_invalid": True}
                )
                continue
            normalized_rows.append(
                {
                    "item_no": row.get("item_no", row.get("item")),
                    "part_number": row.get("part_number"),
                    "quantity": row.get("quantity", row.get("qty")),
                    "description": row.get("description"),
                }
            )
        outputs.append(
            {
                "parent_part_number": parent,
                "rows": normalized_rows,
                "extraction_state": "governed_historical_structured_reuse",
                "bom_source": "governed_historical_structured_reuse",
            }
        )

    for historical_index, parent in enumerate(sorted(normalized_historical)):
        drawing = drawings.get(parent)
        if drawing is None or drawing.get("drawing_type") != approved:
            exclusions.append(
                {
                    "reason_code": "HISTORICAL_BOM_PARENT_NOT_APPROVED_ASM",
                    "record_index": historical_index,
                }
            )
    return StageResult(
        outputs,
        {
            "stage": "B01",
            "extraction_mode": "governed_historical_structured_reuse",
            "drawing_count": len(drawing_index),
            "approved_asm_count": len(approved_parents),
            "historical_parent_count": len(normalized_historical),
            "output_parent_count": len(outputs),
            "missing_current_asm_source_count": sum(
                row["reason_code"] == "BOM_SOURCE_UNAVAILABLE"
                for row in exclusions
            ),
            "finding_count": len(exclusions),
        },
        exclusions,
    )


def validate_b00_word_bundle(
    tertiary_raw: object,
    tertiary_manifest: object,
    config: dict,
) -> tuple[list[dict], list]:
    """Validate a governed B00 reviewed-ASM-word bundle for a combined B01 stage.

    Returns ``(word_documents, word_exclusions)``. Raises ``ValueError`` on any
    governance, manifest, or lineage mismatch.
    """
    if not isinstance(tertiary_raw, dict) or (
        tertiary_raw.get("schema_version") != "cad_2d_reviewed_asm_words_v1"
    ):
        raise ValueError("combined B01 requires a governed B00 word bundle")
    b00_audit = tertiary_raw.get("audit")
    b00_records = tertiary_raw.get("records")
    if (
        not isinstance(b00_audit, dict)
        or not isinstance(b00_records, list)
        or b00_audit.get("stage") != "B00"
        or b00_audit.get("raw_zone_content_accessed") is not False
        or b00_audit.get("processed_pdf_content_accessed") is not True
        or b00_audit.get("output_document_count") != len(b00_records)
    ):
        raise ValueError("combined B01 B00 audit is invalid")
    if not isinstance(tertiary_manifest, dict):
        raise ValueError("combined B01 requires a tertiary manifest")
    if (
        tertiary_manifest.get("stage") != "B00"
        or tertiary_manifest.get("manifest_version") != "cad-2d-run-v1"
        or tertiary_manifest.get("graph_activation") is not False
        or tertiary_manifest.get("promotion_state") != "candidate"
        or tertiary_manifest.get("config_schema_version")
        != config.get("schema_version")
        or tertiary_manifest.get("config_sha256") != sha256_value(config)
        or tertiary_manifest.get("result_sha256") != sha256_value(tertiary_raw)
    ):
        raise ValueError("combined B01 B00 manifest does not match word bundle")
    expected_lineage = config["bom"].get("reviewed_word_bundle_lineage", {})
    manifest_inputs = tertiary_manifest.get("input_sha256")
    if (
        not isinstance(manifest_inputs, dict)
        or manifest_inputs.get("source_review_sha256")
        != sha256_value(expected_lineage.get("source_review_file_sha256"))
        or manifest_inputs.get("projection_sha256")
        != sha256_value(expected_lineage.get("projection_file_sha256"))
        or manifest_inputs.get("page_index")
        != sha256_value(config["bom"]["page_index"])
        or tertiary_manifest.get("result_sha256")
        != expected_lineage.get("b00_bundle_result_sha256")
    ):
        raise ValueError("combined B01 B00 manifest lineage is not governed")
    word_exclusions = tertiary_raw.get("exclusions", [])
    if not isinstance(word_exclusions, list):
        raise ValueError("combined B01 word bundle exclusions must be a list")
    return b00_records, word_exclusions


def combine_bom_candidate_sources(
    drawing_index: list[dict],
    historical_bom: dict[str, Any],
    word_documents: list[dict],
    config: dict,
    *,
    word_exclusions: list[dict] | None = None,
    corrections: list[dict] | None = None,
) -> StageResult:
    """Combine governed historical BOM rows with fresh extraction for uncovered ASM.

    Historical structured evidence remains authoritative for parents it covers.
    Fresh PDF-derived words are evaluated only for currently reviewed ASM that
    have no historical parent, so missing-source findings are not double-counted.
    """

    suffixes = config["identifier"]["strip_suffixes"]
    approved = config["bom"]["approved_parent_decision"]
    historical = reuse_historical_bom_candidates(drawing_index, historical_bom, config)
    historical_parents = {
        _identifier(record["parent_part_number"], suffixes=suffixes)
        for record in historical.records
    }
    word_parents = {
        _identifier(document.get("part_number"), suffixes=suffixes)
        for document in word_documents
    }

    fresh_drawings: list[dict] = []
    fresh_to_original: list[int] = []
    for original_index, drawing in enumerate(drawing_index):
        if drawing.get("drawing_type") != approved:
            continue
        parent = _identifier(drawing.get("part_number"), suffixes=suffixes)
        if parent in historical_parents:
            continue
        fresh_drawings.append(drawing)
        fresh_to_original.append(original_index)

    fresh = extract_asm_bom(fresh_drawings, word_documents, config)
    fresh_exclusions: list[dict[str, Any]] = []
    for exclusion in fresh.exclusions:
        candidate = dict(exclusion)
        subset_index = candidate.get("record_index")
        if not isinstance(subset_index, int) or not 0 <= subset_index < len(fresh_to_original):
            raise ValueError("fresh B01 exclusion has invalid record_index")
        candidate["record_index"] = fresh_to_original[subset_index]
        fresh_exclusions.append(candidate)

    upstream_exclusions: list[dict[str, Any]] = []
    upstream_parents: set[str] = set()
    original_by_parent = {
        _identifier(drawing.get("part_number"), suffixes=suffixes): index
        for index, drawing in enumerate(drawing_index)
    }
    for exclusion in word_exclusions or []:
        if not isinstance(exclusion, dict):
            raise ValueError("B01 word exclusions must contain mappings")
        parent = _identifier(
            exclusion.get("parent_part_number"), suffixes=suffixes
        )
        if parent in historical_parents:
            continue
        if parent not in original_by_parent:
            raise ValueError("B01 word exclusion parent is absent from drawing index")
        candidate = dict(exclusion)
        candidate["parent_part_number"] = parent
        candidate["record_index"] = original_by_parent[parent]
        upstream_exclusions.append(candidate)
        upstream_parents.add(parent)
    if upstream_parents:
        fresh_exclusions = [
            exclusion
            for exclusion in fresh_exclusions
            if not (
                exclusion.get("reason_code") == "BOM_SOURCE_UNAVAILABLE"
                and exclusion.get("parent_part_number") in upstream_parents
            )
        ]

    historical_exclusions = [
        exclusion
        for exclusion in historical.exclusions
        if exclusion.get("reason_code") != "BOM_SOURCE_UNAVAILABLE"
    ]
    records = [*historical.records, *fresh.records]
    exclusions = [
        *historical_exclusions,
        *upstream_exclusions,
        *fresh_exclusions,
    ]
    approved_count = sum(
        drawing.get("drawing_type") == approved for drawing in drawing_index
    )
    records, exclusions, correction_audit = _apply_governed_bom_corrections(
        records, exclusions, corrections, drawing_index, config
    )
    return StageResult(
        records,
        {
            "stage": "B01",
            "extraction_mode": "combined_historical_and_fresh_pdf_words",
            "drawing_count": len(drawing_index),
            "approved_asm_count": approved_count,
            "historical_output_parent_count": len(historical.records),
            "fresh_candidate_parent_count": len(fresh_drawings),
            "fresh_output_parent_count": len(fresh.records),
            "historical_precedence_overlap_count": len(
                historical_parents & word_parents
            ),
            "output_parent_count": len(records),
            "unresolved_current_asm_count": approved_count - len(records),
            "finding_count": len(exclusions),
            **correction_audit,
        },
        exclusions,
    )


def _apply_governed_bom_corrections(
    records: list[dict],
    exclusions: list[dict],
    corrections: list[dict] | None,
    drawing_index: list[dict],
    config: dict,
) -> tuple[list[dict], list[dict], dict[str, int]]:
    """Apply governed, source-anchored BOM row corrections at B01 combine.

    Corrections repair real BOM rows the safe parser dropped or truncated (verified
    on the reviewed PDF). Row-shape corrections add or repair an item row on an
    existing parent record; parent-shape corrections create a governed parent record
    (e.g. a header the anti-overlap guard rejected). Every resolved B01 extraction
    finding whose would-be B02 id is named is cleared so B02 does not re-report it.
    No identifier rule is relaxed and no value is invented.
    """
    if not corrections:
        return (
            records,
            exclusions,
            {
                "correction_count": 0,
                "added_row_count": 0,
                "repaired_row_count": 0,
                "added_parent_count": 0,
                "cleared_extraction_finding_count": 0,
            },
        )
    if not isinstance(corrections, list):
        raise ValueError("governed corrections must be a list")
    suffixes = config["identifier"]["strip_suffixes"]
    allowed_states = set(config["audit"]["override_decision_states"])
    thresholds = config["bom"]["thresholds"]
    drawing_parents = {
        _identifier(drawing.get("part_number"), suffixes=suffixes)
        for drawing in drawing_index
    }
    parent_records: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("rows"), list):
            raise ValueError("B01 record must be a mapping with a rows list")
        key = _identifier(record.get("parent_part_number"), suffixes=suffixes)
        if key in parent_records:
            raise ValueError(f"duplicate B01 parent record: {key}")
        parent_records[key] = record

    resolved_finding_ids: set[str] = set()
    added_row_count = 0
    repaired_row_count = 0
    added_parent_count = 0
    seen_row_targets: set[tuple[str, str]] = set()

    for index, correction in enumerate(corrections):
        if not isinstance(correction, dict):
            raise ValueError("governed corrections must contain mappings")
        missing = set(_CORRECTION_GOVERNED_FIELDS) - set(correction)
        if missing:
            raise ValueError("governed correction is missing governed fields")
        if not all(
            str(correction[key]).strip() for key in _CORRECTION_GOVERNED_FIELDS
        ):
            raise ValueError("governed correction governed fields must not be blank")
        if correction["decision_state"] not in allowed_states:
            raise ValueError("governed correction decision_state is unsupported")
        finding_ids = correction["resolved_finding_ids"]
        if (
            not isinstance(finding_ids, list)
            or not all(isinstance(fid, str) and fid.strip() for fid in finding_ids)
        ):
            raise ValueError(
                "governed correction resolved_finding_ids must be a list of "
                "non-blank strings"
            )
        parent = _identifier(correction["parent_part_number"], suffixes=suffixes)
        if parent not in drawing_parents:
            raise ValueError(
                f"governed correction parent is absent from drawing index: {parent}"
            )
        resolved_finding_ids.update(finding_ids)

        if "rows" in correction:
            rows = correction["rows"]
            if not isinstance(rows, list) or not rows:
                raise ValueError(
                    "governed parent correction rows must be a non-empty list"
                )
            if parent in parent_records:
                raise ValueError(
                    f"governed parent correction duplicates a B01 parent: {parent}"
                )
            normalized_rows: list[dict] = []
            for row in rows:
                if not isinstance(row, dict) or not all(
                    str(row.get(key, "")).strip()
                    for key in ("item", "part_number")
                ):
                    raise ValueError(
                        "governed parent correction rows must be mappings with "
                        "non-blank item and part_number"
                    )
                normalized_rows.append(
                    {
                        "item_no": str(row["item"]).strip(),
                        "part_number": str(row["part_number"]).strip(),
                        "quantity": _validated_correction_quantity(
                            row.get("quantity"), index, thresholds
                        ),
                        "source_anchor": correction["source_anchor"],
                        "correction_reviewed_by": correction["reviewed_by"],
                        "correction_reviewed_at": correction["reviewed_at"],
                    }
                )
            record = {
                "parent_part_number": parent,
                "rows": normalized_rows,
                "extraction_state": "governed_bom_correction",
                "bom_source": "governed_bom_correction",
            }
            records.append(record)
            parent_records[parent] = record
            added_parent_count += 1
            added_row_count += len(normalized_rows)
            continue

        if not all(key in correction for key in ("item", "part_number", "quantity")):
            raise ValueError("governed row correction is missing row fields")
        item = str(correction["item"]).strip()
        part_number = str(correction["part_number"]).strip()
        if not item or not part_number:
            raise ValueError(
                "governed row correction item and part_number must not be blank"
            )
        quantity = _validated_correction_quantity(
            correction["quantity"], index, thresholds
        )
        record = parent_records.get(parent)
        if record is None:
            raise ValueError(
                f"governed row correction parent has no B01 record: {parent}"
            )
        if (parent, item) in seen_row_targets:
            raise ValueError(
                f"duplicate governed row correction for {parent} item {item}"
            )
        seen_row_targets.add((parent, item))
        row = {
            "item_no": item,
            "part_number": part_number,
            "quantity": quantity,
            "source_anchor": correction["source_anchor"],
            "correction_reviewed_by": correction["reviewed_by"],
            "correction_reviewed_at": correction["reviewed_at"],
        }
        target = next(
            (
                existing
                for existing in record["rows"]
                if isinstance(existing, dict)
                and str(existing.get("item_no", existing.get("item", ""))).strip()
                == item
            ),
            None,
        )
        if target is None:
            _insert_bom_row_in_item_order(record["rows"], row)
            added_row_count += 1
        else:
            target.update(row)
            repaired_row_count += 1

    remaining_exclusions: list[dict] = []
    cleared = 0
    for exclusion in exclusions:
        carried_id = _carried_finding_id(exclusion)
        if carried_id is not None and carried_id in resolved_finding_ids:
            cleared += 1
        else:
            remaining_exclusions.append(exclusion)

    return (
        records,
        remaining_exclusions,
        {
            "correction_count": len(corrections),
            "added_row_count": added_row_count,
            "repaired_row_count": repaired_row_count,
            "added_parent_count": added_parent_count,
            "cleared_extraction_finding_count": cleared,
        },
    )


_CORRECTION_GOVERNED_FIELDS = (
    "parent_part_number",
    "source_anchor",
    "reviewed_by",
    "reviewed_at",
    "reason",
    "decision_state",
    "resolved_finding_ids",
)


def _insert_bom_row_in_item_order(rows: list[dict], row: dict) -> None:
    """Insert a corrected BOM row in numeric item order.

    Existing rows are naturally ordered by numeric ``item_no`` (verified at B01
    combine), so inserting by the same key places a governed addition where the
    drawing lists it without reordering pre-existing rows. Falls back to append
    when no existing row sorts after the new one.
    """
    target_item = str(row.get("item_no", row.get("item", ""))).strip()
    for index, existing in enumerate(rows):
        if not isinstance(existing, dict):
            continue
        existing_item = str(
            existing.get("item_no", existing.get("item", ""))
        ).strip()
        if _item_no_order_key(existing_item) > _item_no_order_key(target_item):
            rows.insert(index, row)
            return
    rows.append(row)


def _item_no_order_key(item: str) -> tuple[int, int, str]:
    digits = ""
    offset = 0
    while offset < len(item) and item[offset].isdigit():
        digits += item[offset]
        offset += 1
    if digits:
        return (0, int(digits), item)
    return (1, 0, item)


def _validated_correction_quantity(value: Any, index: int, thresholds: dict) -> int:
    try:
        quantity = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"governed correction {index} has invalid quantity") from None
    if not (thresholds["min_quantity"] <= quantity <= thresholds["max_quantity"]):
        raise ValueError(f"governed correction {index} quantity is out of range")
    return quantity


def _carried_finding_id(exclusion: dict) -> str | None:
    """Return the B02 finding id an extraction finding would carry, if any."""
    parent = exclusion.get("parent_part_number")
    if parent is None or not str(parent).strip():
        return None
    code = str(
        exclusion.get("code")
        or exclusion.get("reason_code")
        or "PENDING_SOURCE_REVIEW"
    ).upper()
    normalized = {
        "POSSIBLE_CLASSIFICATION_ERROR_OR_NO_BOM": "CLASSIFICATION_OR_EMPTY_BOM",
        "SUSPICIOUS_PART_NUMBER": "SUSPICIOUS_IDENTIFIER",
    }.get(code, code)
    return _finding_id(
        {
            "code": normalized,
            "parent_part_number": _identifier(parent),
            "row_number": exclusion.get("row_number"),
            "item_no": exclusion.get("item_no"),
        }
    )


def _finding_id(finding: dict[str, Any]) -> str:
    identity = {
        key: finding.get(key)
        for key in ("code", "parent_part_number", "row_number", "item_no")
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"cad2d_finding_{digest}"


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"{prefix}{digest}"


def _finding(
    code: str,
    severity: str,
    *,
    parent_part_number: str,
    row_number: int | None = None,
    item_no: str | None = None,
) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": severity,
        "parent_part_number": parent_part_number,
        "row_number": row_number,
        "item_no": item_no,
    }
    finding["finding_id"] = _finding_id(finding)
    return finding


def audit_asm_bom(
    drawing_index: list[dict],
    bom_parents: list[dict],
    config: dict,
    *,
    source_findings: list[dict] | None = None,
) -> StageResult:
    """Build a deterministic B02 finding set without inventing BOM values."""

    drawings = _index_unique(drawing_index)
    parents = _index_unique(
        [
            {"part_number": row.get("parent_part_number"), **row}
            for row in bom_parents
        ]
    )
    asm = config["relationships"]["asm_decision"]
    pattern = re.compile(config["audit"]["suspicious_identifier_pattern"])
    findings: list[dict[str, Any]] = []

    for parent, drawing in drawings.items():
        if drawing.get("drawing_type") != asm:
            continue
        source = parents.get(parent)
        rows = [] if source is None else source.get("rows")
        if not isinstance(rows, list) or not rows:
            findings.append(
                _finding("CLASSIFICATION_OR_EMPTY_BOM", "error", parent_part_number=parent)
            )
            continue

        seen_items: set[str] = set()
        integer_items: list[int] = []
        for row_number, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                findings.append(
                    _finding(
                        "EXTRACTION_ROW_INVALID",
                        "error",
                        parent_part_number=parent,
                        row_number=row_number,
                    )
                )
                continue
            item_no = str(row.get("item_no", row.get("item", ""))).strip()
            child = str(row.get("part_number") or "").strip()
            quantity = row.get("quantity", row.get("qty"))
            if not child:
                findings.append(
                    _finding(
                        "BLANK_PART_NUMBER",
                        "error",
                        parent_part_number=parent,
                        row_number=row_number,
                        item_no=item_no or None,
                    )
                )
            elif not pattern.fullmatch(child):
                findings.append(
                    _finding(
                        "SUSPICIOUS_IDENTIFIER",
                        "error",
                        parent_part_number=parent,
                        row_number=row_number,
                        item_no=item_no or None,
                    )
                )
            try:
                parsed_quantity = int(str(quantity).strip())
            except (TypeError, ValueError):
                parsed_quantity = 0
            if not (
                config["bom"]["thresholds"]["min_quantity"]
                <= parsed_quantity
                <= config["bom"]["thresholds"]["max_quantity"]
            ):
                findings.append(
                    _finding(
                        "INVALID_QUANTITY",
                        "error",
                        parent_part_number=parent,
                        row_number=row_number,
                        item_no=item_no or None,
                    )
                )
            if item_no:
                if item_no in seen_items:
                    findings.append(
                        _finding(
                            "DUPLICATE_ITEM_NUMBER",
                            "error",
                            parent_part_number=parent,
                            row_number=row_number,
                            item_no=item_no,
                        )
                    )
                seen_items.add(item_no)
                if item_no.isdigit():
                    integer_items.append(int(item_no))

        if integer_items:
            expected = set(range(min(integer_items), max(integer_items) + 1))
            if expected - set(integer_items):
                findings.append(
                    _finding("ITEM_SEQUENCE_GAP", "warning", parent_part_number=parent)
                )

    for parent in sorted(set(parents) - set(drawings)):
        findings.append(_finding("UNKNOWN_BOM_PARENT", "error", parent_part_number=parent))
    for parent in sorted(set(parents) & set(drawings)):
        if drawings[parent].get("drawing_type") != asm:
            findings.append(_finding("NON_ASM_BOM_PARENT", "error", parent_part_number=parent))

    for source in source_findings or []:
        if not isinstance(source, dict):
            raise ValueError("source_findings must contain mappings")
        code = str(
            source.get("code")
            or source.get("reason_code")
            or "PENDING_SOURCE_REVIEW"
        ).upper()
        normalized_code = {
            "POSSIBLE_CLASSIFICATION_ERROR_OR_NO_BOM": "CLASSIFICATION_OR_EMPTY_BOM",
            "SUSPICIOUS_PART_NUMBER": "SUSPICIOUS_IDENTIFIER",
        }.get(code, code)
        severity = str(source.get("severity") or "error").lower()
        if severity not in {"error", "warning"}:
            raise ValueError("source finding severity is unsupported")
        findings.append(
            _finding(
                normalized_code,
                severity,
                parent_part_number=_identifier(source.get("parent_part_number")),
                row_number=source.get("row_number"),
                item_no=source.get("item_no"),
            )
        )

    unique: dict[str, dict[str, Any]] = {}
    blocking = set(config["audit"]["blocking_severities"])
    for finding in findings:
        existing = unique.get(finding["finding_id"])
        if existing is None:
            unique[finding["finding_id"]] = finding
            continue
        existing_blocks = existing.get("severity") in blocking
        candidate_blocks = finding.get("severity") in blocking
        if candidate_blocks and not existing_blocks:
            unique[finding["finding_id"]] = finding
    ordered = sorted(unique.values(), key=lambda row: row["finding_id"])
    return StageResult(
        ordered,
        {
            "stage": "B02",
            "drawing_count": len(drawing_index),
            "bom_parent_count": len(bom_parents),
            "finding_count": len(ordered),
            "blocking_finding_count": sum(row["severity"] in blocking for row in ordered),
            "finding_counts_by_code": dict(
                sorted(
                    (code, sum(row["code"] == code for row in ordered))
                    for code in {row["code"] for row in ordered}
                )
            ),
        },
        [],
    )


def _accepted_finding_ids(
    findings: list[dict], overrides: list[dict], config: dict
) -> set[str]:
    known = {row.get("finding_id") for row in findings}
    accepted: set[str] = set()
    allowed_states = set(config["audit"]["override_decision_states"])
    required = {"finding_id", "source_anchor", "reviewed_by", "reviewed_at", "reason", "decision_state"}
    for override in overrides:
        if not isinstance(override, dict) or required - set(override):
            raise ValueError("manual override is missing governed fields")
        if not all(str(override[key]).strip() for key in required):
            raise ValueError("manual override governed fields must not be blank")
        if override["decision_state"] not in allowed_states:
            raise ValueError("manual override decision_state is unsupported")
        if override["finding_id"] not in known:
            raise ValueError("manual override references an unknown finding")
        if override["finding_id"] in accepted:
            raise ValueError("duplicate manual override")
        if override["decision_state"] == "accepted":
            accepted.add(override["finding_id"])
    return accepted


def build_relationships(
    drawing_index: list[dict],
    bom_parents: list[dict],
    findings: list[dict],
    config: dict,
    *,
    overrides: list[dict] | None = None,
    source_findings: list[dict] | None = None,
) -> StageResult:
    """Build C01 edges only when every blocking B02 finding is resolved."""

    drawings = _index_unique(drawing_index)
    recomputed_findings = audit_asm_bom(
        drawing_index,
        bom_parents,
        config,
        source_findings=source_findings,
    ).records
    if findings != recomputed_findings:
        raise ValueError("C01 findings do not match recomputed B02")
    accepted = _accepted_finding_ids(findings, overrides or [], config)
    blocking = set(config["audit"]["blocking_severities"])
    unresolved = [
        row
        for row in findings
        if row.get("severity") in blocking and row.get("finding_id") not in accepted
    ]
    if unresolved:
        raise ValueError(f"C01 blocked by unresolved B02 findings; count={len(unresolved)}")

    asm = config["relationships"]["asm_decision"]
    prt = config["relationships"]["prt_decision"]
    output: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for parent_record in bom_parents:
        parent = _identifier(parent_record.get("parent_part_number"))
        if (
            parent not in drawings
            or drawings[parent].get("drawing_type") != asm
            or not drawings[parent].get("promotion_eligible", True)
        ):
            raise ValueError("C01 received a BOM parent that is not an approved ASM")
        parent_definition_id = drawings[parent].get("canonical_definition_id") or _stable_id(
            "part:", {"governed_part_identifier": parent}
        )
        for row_number, row in enumerate(parent_record.get("rows", []), start=1):
            item_no = str(row.get("item_no", row.get("item", ""))).strip()
            child_value = row.get("part_number")
            if child_value is None or not str(child_value).strip():
                exclusions.append(
                    {
                        "reason_code": "BLANK_CHILD_IDENTIFIER",
                        "record_index": row_number - 1,
                        "parent_part_number": parent,
                        "item_no": item_no,
                    }
                )
                continue
            child = _identifier(child_value)
            child_drawing = drawings.get(child)
            if child_drawing is None:
                semantics = "unknown_child"
                child_definition_id = None
            elif not child_drawing.get("promotion_eligible", True):
                exclusions.append(
                    {
                        "reason_code": "EXCLUDED_CHILD_NOT_PROMOTED",
                        "record_index": row_number - 1,
                        "parent_part_number": parent,
                        "item_no": item_no,
                    }
                )
                continue
            elif child_drawing.get("drawing_type") == prt:
                semantics = "confirmed_prt_child"
                child_definition_id = child_drawing.get(
                    "canonical_definition_id"
                ) or _stable_id("part:", {"governed_part_identifier": child})
            elif child_drawing.get("drawing_type") == asm:
                semantics = "known_asm_child"
                child_definition_id = child_drawing.get(
                    "canonical_definition_id"
                ) or _stable_id("part:", {"governed_part_identifier": child})
            else:
                semantics = "unknown_child"
                child_definition_id = None
            source_anchor = row.get("source_anchor") or _stable_id(
                "bom_source:",
                {"parent_definition_id": parent_definition_id, "row_number": row_number},
            )
            occurrence_id = _stable_id(
                "cad2d_occurrence_",
                {
                    "parent_definition_id": parent_definition_id,
                    "child_definition_id": child_definition_id,
                    "unknown_child_identifier_sha256": (
                        None
                        if child_definition_id is not None
                        else hashlib.sha256(child.encode("utf-8")).hexdigest()
                    ),
                    "source_anchor": source_anchor,
                    "item_no": item_no,
                    "row_number": row_number,
                },
            )
            output.append(
                {
                    "occurrence_id": occurrence_id,
                    "parent_asm_part_number": parent,
                    "parent_definition_id": parent_definition_id,
                    "child_part_number": child,
                    "child_definition_id": child_definition_id,
                    "source_anchor": source_anchor,
                    "occurrence_ordinal": row_number,
                    "item_no": item_no,
                    "quantity": int(str(row.get("quantity", row.get("qty"))).strip()),
                    "description": str(row.get("description") or ""),
                    "child_semantics": semantics,
                }
            )
    return StageResult(
        output,
        {
            "stage": "C01",
            "relationship_count": len(output),
            "confirmed_prt_child_count": sum(
                row["child_semantics"] == "confirmed_prt_child" for row in output
            ),
            "known_asm_child_count": sum(
                row["child_semantics"] == "known_asm_child" for row in output
            ),
            "unknown_child_count": sum(
                row["child_semantics"] == "unknown_child" for row in output
            ),
            "accepted_risk_count": len(accepted),
        },
        exclusions,
    )


def build_project_owner_output(
    drawing_index: list[dict], relationships: list[dict], config: dict
) -> StageResult:
    """Build the C02 candidate while preserving separate child semantics."""

    drawings = _index_unique(drawing_index)
    by_parent: dict[str, list[dict]] = {}
    by_child: dict[str, list[dict]] = {}
    for relation in relationships:
        parent = _identifier(relation.get("parent_asm_part_number"))
        child = _identifier(relation.get("child_part_number"))
        if parent not in drawings:
            raise ValueError("C02 relationship parent is absent from drawing index")
        if not drawings[parent].get("promotion_eligible", True):
            raise ValueError("C02 relationship parent is excluded from promotion")
        child_drawing = drawings.get(child)
        if child_drawing is not None and not child_drawing.get(
            "promotion_eligible", True
        ):
            raise ValueError("C02 relationship child is excluded from promotion")
        by_parent.setdefault(parent, []).append(relation)
        by_child.setdefault(child, []).append(relation)

    output = []
    exclusions: list[dict[str, Any]] = []
    for source_index, drawing in enumerate(drawing_index):
        if not drawing.get("promotion_eligible", True):
            exclusions.append(
                {"reason_code": "DRAWING_NOT_PROMOTED", "record_index": source_index}
            )
            continue
        key = _identifier(drawing.get("part_number"))
        children = by_parent.get(key, [])
        output.append(
            {
                "part_number": key,
                "drawing_type": drawing.get("drawing_type"),
                "drawing_title": drawing.get("drawing_title", ""),
                "project_name": drawing.get("project_name", ""),
                "canonical_definition_id": drawing.get("canonical_definition_id"),
                "parent_asm_part_numbers": sorted(
                    {row["parent_asm_part_number"] for row in by_child.get(key, [])}
                ),
                "child_part_numbers": sorted({row["child_part_number"] for row in children}),
                "child_prt_part_numbers": sorted(
                    {
                        row["child_part_number"]
                        for row in children
                        if row["child_semantics"] == "confirmed_prt_child"
                    }
                ),
                "unknown_child_part_numbers": sorted(
                    {
                        row["child_part_number"]
                        for row in children
                        if row["child_semantics"] == "unknown_child"
                    }
                ),
            }
        )
    return StageResult(
        output,
        {
            "stage": "C02",
            "drawing_count": len(output),
            "relationship_count": len(relationships),
            "drawing_with_parent_count": sum(bool(row["parent_asm_part_numbers"]) for row in output),
            "drawing_with_children_count": sum(bool(row["child_part_numbers"]) for row in output),
        },
        exclusions,
    )
