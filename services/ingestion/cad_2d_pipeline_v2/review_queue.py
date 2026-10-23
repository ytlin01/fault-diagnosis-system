from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


PDF_SUFFIXES = ("_redacted", "_masked")


def normalized_pdf_identifier(path: Path) -> str:
    identifier = path.stem
    for suffix in PDF_SUFFIXES:
        if identifier.casefold().endswith(suffix):
            identifier = identifier[: -len(suffix)]
    return identifier.strip().casefold()


def build_manual_classification_records(
    classifications: Sequence[Mapping[str, Any]],
    title_fields: Mapping[str, Mapping[str, Any]],
    pdf_paths: Iterable[Path],
) -> list[dict[str, Any]]:
    classified = {
        str(record.get("part_number") or "").strip().casefold()
        for record in classifications
    }
    if "" in classified:
        raise ValueError("classification contains a blank part_number")

    pdf_lookup: dict[str, list[Path]] = {}
    for path in pdf_paths:
        pdf_lookup.setdefault(normalized_pdf_identifier(path), []).append(path)

    records: list[dict[str, Any]] = []
    for part_number in sorted(title_fields, key=lambda value: value.casefold()):
        normalized = str(part_number).strip().casefold()
        if not normalized:
            raise ValueError("title-fields input contains a blank identifier")
        if normalized in classified:
            continue
        matches = pdf_lookup.get(normalized, [])
        if len(matches) != 1:
            raise ValueError(
                "each unclassified drawing must match exactly one governed PDF"
            )
        fields = title_fields[part_number] or {}
        records.append(
            {
                "sequence": len(records) + 1,
                "part_number": part_number,
                "source_pdf": matches[0],
                "source_partition": matches[0].parent.name,
                "drawing_title": fields.get("drawing_title") or None,
                "project_name": fields.get("project_name") or None,
                "decision": None,
                "confidence": None,
                "reviewer": None,
                "review_reason": None,
                "reviewed_at": None,
            }
        )
    return records
