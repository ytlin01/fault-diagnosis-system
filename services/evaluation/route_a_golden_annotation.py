"""Dependency-free boundary for Route A expert golden-case annotation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


QUEUE_SCHEMA_VERSION = "route_a_annotation_queue_v1"
REVIEW_SCHEMA_VERSION = "route_a_annotation_review_v1"
_ROLES = {"annotator", "domain_reviewer", "adjudicator"}
_DECISIONS = {"accept", "reject", "replace", "abstain"}
_MATURITIES = {"assumed_label_provisional", "provisional", "reviewed", "adjudicated"}
_ABSTENTION = {"required", "allowed", "not_expected"}
_SOURCE_STATES = {"pending", "reviewed", "adjudicated"}
_ALLOWED_USES = {"annotation_only", "evaluation_only", "annotation_and_evaluation"}
_PARTITIONS = {"development", "validation", "blind"}
_QUERY_TYPES = {
    "ec",
    "phenomenon",
    "asset",
    "ambiguous",
    "partial_chain",
    "multiple_valid_answer",
    "no_hit_abstention",
}
_DIFFICULTIES = {"low", "medium", "high"}
_PROHIBITED_SOURCE_CONTEXT_FIELDS = {
    "graph_id",
    "graph_node_id",
    "node_id",
    "ranked_results",
    "retrieval_results",
    "cypher",
}


class GoldenAnnotationInputError(ValueError):
    """Raised when an annotation queue or submitted review is malformed."""


def _non_empty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoldenAnnotationInputError(f"{field} must be a non-empty string")
    return value.strip()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GoldenAnnotationInputError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise GoldenAnnotationInputError(f"{field} must be an array")
    return value


def validate_annotation_queue(queue: Mapping[str, Any]) -> None:
    """Validate a data-free or governed expert annotation queue.

    The queue deliberately has no KG result field. Its optional catalogs are
    controlled domain vocabularies, not retrieval candidates.
    """
    if queue.get("schema_version") != QUEUE_SCHEMA_VERSION:
        raise GoldenAnnotationInputError(f"schema_version must be {QUEUE_SCHEMA_VERSION}")
    _non_empty(queue.get("queue_id"), "queue_id")
    cases = _list(queue.get("cases"), "cases")
    if not cases:
        raise GoldenAnnotationInputError("cases must not be empty")
    seen_case_ids: set[str] = set()
    scenario_partitions: dict[str, str] = {}
    for index, raw_case in enumerate(cases):
        case = _mapping(raw_case, f"cases[{index}]")
        case_id = _non_empty(case.get("case_id"), f"cases[{index}].case_id")
        if case_id in seen_case_ids:
            raise GoldenAnnotationInputError(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)
        scenario_id = _non_empty(case.get("scenario_id"), f"cases[{index}].scenario_id")
        _non_empty(case.get("query"), f"cases[{index}].query")
        _non_empty(case.get("query_language"), f"cases[{index}].query_language")
        partition = case.get("partition")
        if partition not in _PARTITIONS:
            raise GoldenAnnotationInputError(f"cases[{index}].partition is invalid")
        prior_partition = scenario_partitions.setdefault(scenario_id, partition)
        if prior_partition != partition:
            raise GoldenAnnotationInputError(
                f"scenario_id {scenario_id} crosses partitions: "
                f"{prior_partition}/{partition}"
            )
        coverage = _mapping(case.get("coverage"), f"cases[{index}].coverage")
        query_type = _non_empty(
            coverage.get("query_type"), f"cases[{index}].coverage.query_type"
        )
        if query_type not in _QUERY_TYPES:
            raise GoldenAnnotationInputError(
                f"cases[{index}].coverage.query_type is invalid"
            )
        difficulty = _non_empty(
            coverage.get("difficulty"), f"cases[{index}].coverage.difficulty"
        )
        if difficulty not in _DIFFICULTIES:
            raise GoldenAnnotationInputError(
                f"cases[{index}].coverage.difficulty is invalid"
            )
        _non_empty(
            coverage.get("equipment_scope"),
            f"cases[{index}].coverage.equipment_scope",
        )
        if "source_context" in case:
            context = _mapping(
                case.get("source_context"),
                f"cases[{index}].source_context",
            )
            prohibited = sorted(
                _PROHIBITED_SOURCE_CONTEXT_FIELDS.intersection(context)
            )
            if prohibited:
                raise GoldenAnnotationInputError(
                    f"cases[{index}].source_context contains prohibited "
                    f"graph/retrieval fields: {prohibited}"
                )
            for field in (
                "source_id",
                "source_record_id",
                "source_anchor",
                "code",
                "local_alarm_code",
                "error_description",
                "error_description_zh",
                "source_suggested_repair_action",
            ):
                _non_empty(
                    context.get(field),
                    f"cases[{index}].source_context.{field}",
                )
            if context.get("label_authority") != "source_suggested_only":
                raise GoldenAnnotationInputError(
                    f"cases[{index}].source_context.label_authority must be "
                    "source_suggested_only"
                )
            source_row_index = context.get("source_row_index")
            if not isinstance(source_row_index, int) or source_row_index < 0:
                raise GoldenAnnotationInputError(
                    f"cases[{index}].source_context.source_row_index must be "
                    "a non-negative integer"
                )
            duplicate_count = context.get("duplicate_code_count")
            if not isinstance(duplicate_count, int) or duplicate_count < 1:
                raise GoldenAnnotationInputError(
                    f"cases[{index}].source_context.duplicate_code_count must "
                    "be a positive integer"
                )

    cause_ids: set[str] = set()
    for index, raw_cause in enumerate(queue.get("cause_catalog", [])):
        cause = _mapping(raw_cause, f"cause_catalog[{index}]")
        cause_id = _non_empty(cause.get("cause_id"), f"cause_catalog[{index}].cause_id")
        _non_empty(cause.get("display_name"), f"cause_catalog[{index}].display_name")
        if cause_id in cause_ids:
            raise GoldenAnnotationInputError(f"duplicate cause_catalog cause_id: {cause_id}")
        cause_ids.add(cause_id)
    pair_ids: set[tuple[str, str]] = set()
    for index, raw_pair in enumerate(queue.get("cause_action_pair_catalog", [])):
        pair = _mapping(raw_pair, f"cause_action_pair_catalog[{index}]")
        pair_id = (_non_empty(pair.get("cause_id"), f"cause_action_pair_catalog[{index}].cause_id"), _non_empty(pair.get("action_id"), f"cause_action_pair_catalog[{index}].action_id"))
        _non_empty(pair.get("display_name"), f"cause_action_pair_catalog[{index}].display_name")
        if pair_id in pair_ids:
            raise GoldenAnnotationInputError(f"duplicate cause/action pair: {pair_id[0]}/{pair_id[1]}")
        if cause_ids and pair_id[0] not in cause_ids:
            raise GoldenAnnotationInputError(
                f"cause_action_pair_catalog[{index}].cause_id is outside cause_catalog"
            )
        pair_ids.add(pair_id)


def queue_case(queue: Mapping[str, Any], case_id: str, *, allow_blind: bool = False) -> Mapping[str, Any]:
    """Return one annotatable case and enforce the blind-label boundary."""
    validate_annotation_queue(queue)
    wanted = _non_empty(case_id, "case_id")
    for raw_case in queue["cases"]:
        case = _mapping(raw_case, "case")
        if case["case_id"] == wanted:
            if case["partition"] == "blind" and not allow_blind:
                raise GoldenAnnotationInputError("blind cases require explicit allow_blind authorization")
            return case
    raise GoldenAnnotationInputError(f"case_id not found: {wanted}")


def _validate_anchors(anchors: Sequence[Any]) -> list[dict[str, str]]:
    if not anchors:
        raise GoldenAnnotationInputError("at least one source anchor is required")
    normalized = []
    for index, raw_anchor in enumerate(anchors):
        anchor = _mapping(raw_anchor, f"source_anchors[{index}]")
        source_review_state = anchor.get("source_review_state")
        allowed_use = anchor.get("allowed_use")
        if source_review_state not in _SOURCE_STATES:
            raise GoldenAnnotationInputError(f"source_anchors[{index}].source_review_state is invalid")
        if allowed_use not in _ALLOWED_USES:
            raise GoldenAnnotationInputError(f"source_anchors[{index}].allowed_use is invalid")
        normalized.append({
            "source_id": _non_empty(anchor.get("source_id"), f"source_anchors[{index}].source_id"),
            "anchor": _non_empty(anchor.get("anchor"), f"source_anchors[{index}].anchor"),
            "source_review_state": source_review_state,
            "allowed_use": allowed_use,
        })
    return normalized


def create_review_record(
    queue: Mapping[str, Any],
    *,
    case_id: str,
    reviewer_id: str,
    role: str,
    decision: str,
    label_maturity: str,
    abstention: str,
    cause_ids: Sequence[str],
    cause_action_pairs: Sequence[Mapping[str, Any]],
    source_anchors: Sequence[Mapping[str, Any]],
    rationale_anchor: str,
    allow_blind: bool = False,
) -> dict[str, Any]:
    """Create one append-only review record; never mutates a golden label."""
    case = queue_case(queue, case_id, allow_blind=allow_blind)
    if role not in _ROLES:
        raise GoldenAnnotationInputError("role is invalid")
    if decision not in _DECISIONS:
        raise GoldenAnnotationInputError("decision is invalid")
    if label_maturity not in _MATURITIES:
        raise GoldenAnnotationInputError("label_maturity is invalid")
    if abstention not in _ABSTENTION:
        raise GoldenAnnotationInputError("abstention is invalid")
    if label_maturity == "reviewed" and role not in {"domain_reviewer", "adjudicator"}:
        raise GoldenAnnotationInputError(
            "reviewed maturity requires domain_reviewer or adjudicator"
        )
    if label_maturity == "adjudicated" and role != "adjudicator":
        raise GoldenAnnotationInputError(
            "adjudicated maturity requires an adjudicator"
        )
    if case["partition"] == "blind" and label_maturity not in {"reviewed", "adjudicated"}:
        raise GoldenAnnotationInputError(
            "blind cases require reviewed or adjudicated maturity"
        )

    catalog_causes = {item["cause_id"] for item in queue.get("cause_catalog", [])}
    selected_causes = [_non_empty(item, "cause_id") for item in cause_ids]
    if len(set(selected_causes)) != len(selected_causes):
        raise GoldenAnnotationInputError("cause_ids must be unique")
    if catalog_causes and not set(selected_causes).issubset(catalog_causes):
        raise GoldenAnnotationInputError("selected cause_id is outside the controlled catalog")

    catalog_pairs = {(item["cause_id"], item["action_id"]) for item in queue.get("cause_action_pair_catalog", [])}
    selected_pairs: list[dict[str, str]] = []
    for index, raw_pair in enumerate(cause_action_pairs):
        pair = _mapping(raw_pair, f"cause_action_pairs[{index}]")
        selected_pairs.append({"cause_id": _non_empty(pair.get("cause_id"), f"cause_action_pairs[{index}].cause_id"), "action_id": _non_empty(pair.get("action_id"), f"cause_action_pairs[{index}].action_id")})
    if len({(pair["cause_id"], pair["action_id"]) for pair in selected_pairs}) != len(selected_pairs):
        raise GoldenAnnotationInputError("cause_action_pairs must be unique")
    if catalog_pairs and not {(pair["cause_id"], pair["action_id"]) for pair in selected_pairs}.issubset(catalog_pairs):
        raise GoldenAnnotationInputError("selected cause/action pair is outside the controlled catalog")
    if any(pair["cause_id"] not in selected_causes for pair in selected_pairs):
        raise GoldenAnnotationInputError(
            "each selected cause/action pair must reference a selected cause_id"
        )
    if abstention == "required" and (selected_causes or selected_pairs):
        raise GoldenAnnotationInputError("required abstention cannot include selected labels")
    if abstention == "not_expected" and not selected_causes:
        raise GoldenAnnotationInputError("not_expected abstention requires at least one selected cause")
    if decision == "abstain" and abstention == "not_expected":
        raise GoldenAnnotationInputError(
            "an abstain decision requires required or allowed abstention"
        )

    normalized_anchors = _validate_anchors(source_anchors)
    if label_maturity in {"reviewed", "adjudicated"}:
        for index, anchor in enumerate(normalized_anchors):
            if anchor["source_review_state"] not in {"reviewed", "adjudicated"}:
                raise GoldenAnnotationInputError(
                    f"source_anchors[{index}] is not reviewed"
                )
            if anchor["allowed_use"] not in {
                "evaluation_only",
                "annotation_and_evaluation",
            }:
                raise GoldenAnnotationInputError(
                    f"source_anchors[{index}] is not eligible for evaluation"
                )

    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "queue_id": queue["queue_id"],
        "case_id": case["case_id"],
        "scenario_id": case["scenario_id"],
        "partition": case["partition"],
        "reviewer_id": _non_empty(reviewer_id, "reviewer_id"),
        "role": role,
        "decision": decision,
        "label_maturity": label_maturity,
        "abstention": abstention,
        "cause_ids": selected_causes,
        "cause_action_pairs": selected_pairs,
        "source_anchors": normalized_anchors,
        "rationale_anchor": _non_empty(rationale_anchor, "rationale_anchor"),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
