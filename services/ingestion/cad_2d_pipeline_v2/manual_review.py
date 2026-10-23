from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from typing import Any


ALLOWED_DECISIONS = {"asm", "prt", "exclude", "unresolved"}


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _nonblank(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-blank string")
    return value.strip()


def _identity_overrides(
    values: Sequence[Mapping[str, Any]], known_ids: set[str]
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for override_index, raw in enumerate(values):
        if not isinstance(raw, Mapping):
            raise ValueError("identity override must be a mapping")
        rule = raw.get("rule")
        if rule not in {"explicit_reviewed_views", "multi_page_document"}:
            raise ValueError("identity override rule is unsupported")
        source_anchor = _nonblank(raw.get("source_anchor"), "source_anchor")
        source_ids = raw.get("source_record_ids")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or not all(isinstance(value, str) and value.strip() for value in source_ids)
        ):
            raise ValueError("identity override source_record_ids are invalid")
        normalized_ids = [value.strip() for value in source_ids]
        if len(normalized_ids) != len(set(normalized_ids)):
            raise ValueError("identity override repeats a source record")
        if rule == "explicit_reviewed_views" and len(normalized_ids) < 2:
            raise ValueError("explicit reviewed view group requires at least two records")
        if rule == "multi_page_document" and len(normalized_ids) != 1:
            raise ValueError("multi-page identity override requires exactly one record")
        unknown = set(normalized_ids) - known_ids
        if unknown:
            raise ValueError(
                f"identity override references unknown source records; count={len(unknown)}"
            )
        canonical_seed = "|".join(sorted(normalized_ids))
        canonical_definition_id = raw.get("canonical_definition_id") or (
            "part:" + _digest_text("definition|" + canonical_seed)
        )
        group_id = raw.get("group_id") or (
            "view_group:" + _digest_text("view_group|" + canonical_seed)
        )
        page_count = raw.get("page_count")
        if page_count is not None and (
            not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 1
        ):
            raise ValueError("identity override page_count must be a positive integer")
        if rule == "multi_page_document" and (page_count is None or page_count < 2):
            raise ValueError("multi-page identity override requires page_count >= 2")
        aliases = raw.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError("identity override aliases must be a list")
        normalized_aliases = []
        for alias in aliases:
            if not isinstance(alias, Mapping):
                raise ValueError("identity alias must be a mapping")
            normalized_aliases.append(
                {
                    "value": _nonblank(alias.get("value"), "alias.value"),
                    "alias_type": alias.get("alias_type", "reviewed_source_alias"),
                    "source_anchor": _nonblank(
                        alias.get("source_anchor", source_anchor),
                        "alias.source_anchor",
                    ),
                    "reviewer": _nonblank(alias.get("reviewer"), "alias.reviewer"),
                }
            )
        normalized = {
            "rule": rule,
            "source_anchor": source_anchor,
            "canonical_definition_id": _nonblank(
                canonical_definition_id, "canonical_definition_id"
            ),
            "group_id": _nonblank(group_id, "group_id"),
            "page_count": page_count,
            "aliases": normalized_aliases,
            "override_index": override_index,
        }
        for source_id in normalized_ids:
            if source_id in indexed:
                raise ValueError("source record appears in multiple identity overrides")
            indexed[source_id] = normalized
    return indexed


def project_completed_review(
    source: Mapping[str, Any],
    *,
    source_artifact_sha256: str,
    expected_source_artifact_sha256: str,
    verified_pdf_digests: set[str],
    identity_overrides: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if source_artifact_sha256 != expected_source_artifact_sha256:
        raise ValueError("source review artifact digest does not match governance")
    if source.get("schema_version") != "cad_2d_manual_classification_review_v1":
        raise ValueError("source review schema version is unsupported")
    raw_records = source.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("source review records must be a non-empty list")

    source_ids = [_nonblank(row.get("part_number"), "part_number") for row in raw_records]
    sequences = [row.get("sequence") for row in raw_records]
    pdf_digests = [row.get("pdf_sha256") for row in raw_records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source review contains duplicate source record IDs")
    if len(sequences) != len(set(sequences)) or not all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 1
        for value in sequences
    ):
        raise ValueError("source review sequences are invalid or duplicated")
    if len(pdf_digests) != len(set(pdf_digests)) or not all(
        isinstance(value, str) and len(value) == 64 for value in pdf_digests
    ):
        raise ValueError("source review PDF digests are invalid or duplicated")
    if set(pdf_digests) != verified_pdf_digests:
        raise ValueError("source review PDF existence/digest verification is incomplete")

    overrides = _identity_overrides(identity_overrides, set(source_ids))
    output: list[dict[str, Any]] = []
    for row, source_id in zip(raw_records, source_ids, strict=True):
        decision = row.get("decision")
        if decision not in ALLOWED_DECISIONS:
            raise ValueError("source review decision is incomplete or unsupported")
        reviewer = _nonblank(row.get("reviewer"), "reviewer")
        reviewed_at = _nonblank(row.get("reviewed_at"), "reviewed_at")
        confidence = row.get("confidence")
        if decision in {"asm", "prt", "unresolved"} and confidence not in {
            "high",
            "medium",
            "low",
        }:
            raise ValueError("non-excluded review decision requires confidence")
        reason = row.get("review_reason") or None
        pdf_digest = row["pdf_sha256"]
        candidate: dict[str, Any] = {
            "sequence": row["sequence"],
            "source_record_id": source_id,
            "source_pdf_sha256": pdf_digest,
            "evidence_id": "drawing_evidence:" + pdf_digest,
            "decision": decision,
            "confidence": confidence,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "human_review_reason": reason,
            "exclusion_reason_code": None,
            "canonical_definition_id": None,
            "identity_basis": "unresolved_no_definition",
            "view_grouping": None,
            "aliases": [],
            "page_count": None,
            "project_name": row.get("project_name") or None,
        }
        if decision == "exclude":
            if reason != "empty drawing":
                raise ValueError("exclude decision has no supported reason mapping")
            if confidence is not None:
                raise ValueError("exclude decision must not carry confidence")
            candidate["exclusion_reason_code"] = "empty_drawing"
            candidate["identity_basis"] = "excluded_no_definition"
        elif decision in {"asm", "prt"}:
            override = overrides.get(source_id)
            if override:
                candidate["canonical_definition_id"] = override[
                    "canonical_definition_id"
                ]
                candidate["identity_basis"] = (
                    "explicit_reviewed_view_group"
                    if override["rule"] == "explicit_reviewed_views"
                    else "governed_part_identifier"
                )
                candidate["view_grouping"] = {
                    "rule": override["rule"],
                    "group_id": override["group_id"],
                    "source_anchor": override["source_anchor"],
                }
                candidate["page_count"] = override["page_count"]
                candidate["aliases"] = override["aliases"]
            else:
                candidate["canonical_definition_id"] = "part:" + _digest_text(
                    "definition|" + source_id
                )
                candidate["identity_basis"] = "governed_part_identifier"
                candidate["view_grouping"] = {
                    "rule": "singleton",
                    "group_id": "view_group:" + _digest_text("view|" + source_id),
                    "source_anchor": f"human_review_sequence:{row['sequence']}",
                }
        output.append(candidate)

    return {
        "schema_version": "cad_2d_manual_classification_review_v2",
        "task_id": "V2-TASK015",
        "review_state": "human_decisions_complete",
        "identity_rule_version": "cad_2d_identity_v2",
        "source_review": {
            "schema_version": source["schema_version"],
            "artifact_sha256": source_artifact_sha256,
            "immutable": True,
            "record_count": len(output),
        },
        "records": output,
    }


def validate_projection_semantics(payload: Mapping[str, Any]) -> None:
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("projection records must be a list")
    if payload.get("source_review", {}).get("record_count") != len(records):
        raise ValueError("projection record count disagrees with source evidence")
    for key in ("sequence", "source_record_id", "evidence_id"):
        values = [row.get(key) for row in records]
        if len(values) != len(set(values)):
            raise ValueError(f"projection contains duplicate {key}")
    for row in records:
        if row.get("evidence_id") != "drawing_evidence:" + str(
            row.get("source_pdf_sha256")
        ):
            raise ValueError("projection evidence ID disagrees with PDF digest")
    definitions: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        definition = row.get("canonical_definition_id")
        if definition:
            definitions.setdefault(definition, []).append(row)
    for members in definitions.values():
        if len(members) < 2:
            continue
        group_ids = {
            (row.get("view_grouping") or {}).get("group_id") for row in members
        }
        if (
            len(group_ids) != 1
            or None in group_ids
            or any(
                row.get("identity_basis") != "explicit_reviewed_view_group"
                or (row.get("view_grouping") or {}).get("rule")
                != "explicit_reviewed_views"
                for row in members
            )
        ):
            raise ValueError(
                "shared definition requires one explicit reviewed view group"
            )


def projection_classification_records(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if payload.get("schema_version") != "cad_2d_manual_classification_review_v2":
        raise ValueError("manual-review projection schema version is unsupported")
    if payload.get("review_state") != "human_decisions_complete":
        raise ValueError("manual-review projection is not complete")
    validate_projection_semantics(payload)
    result = []
    for row in payload["records"]:
        result.append(
            {
                "part_number": row["source_record_id"],
                "decision": row["decision"],
                "review_note": row.get("human_review_reason") or "",
                "reviewer": row["reviewer"],
                "reviewed_at": row["reviewed_at"],
                "evidence_id": row["evidence_id"],
                "canonical_definition_id": row.get("canonical_definition_id"),
                "identity_basis": row["identity_basis"],
                "view_grouping": row.get("view_grouping"),
                "aliases": row.get("aliases", []),
                "page_count": row.get("page_count"),
                "exclusion_reason_code": row.get("exclusion_reason_code"),
            }
        )
    return result


