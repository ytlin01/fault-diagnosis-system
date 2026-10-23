"""Shared record layouts for canonical governance storage and review exports."""

from __future__ import annotations

SOURCE_INVENTORY = "source_inventory"
MASKING_LOG = "masking_log"
ANNOTATION_LOG = "annotation_log"
INDEX_REGISTRY = "index_registry"
EVAL_RUN_LOG = "eval_run_log"

SHEET_HEADERS: dict[str, list[str]] = {
    SOURCE_INVENTORY: [
        "source_id",
        "file_path",
        "zone",
        "source_type",
        "route_eligibility",
        "serving_safe",
        "masking_status",
        "reviewed_status",
        "date_added",
        "notes",
    ],
    MASKING_LOG: [
        "log_id",
        "run_id",
        "source_id",
        "masking_source_name",
        "input_source_id",
        "canonical_source_id",
        "serving_source_id",
        "run_timestamp",
        "rules_version",
        "masking_action",
        "input_path",
        "output_canonical_path",
        "output_serving_path",
        "manifest_path",
        "lineage_path",
        "operator",
    ],
    ANNOTATION_LOG: [
        "annotation_id",
        "source_id",
        "source_version",
        "annotated_by",
        "annotated_at",
        "annotation_type",
        "staleness_warning",
        "notes",
    ],
    INDEX_REGISTRY: [
        "index_name",
        "source_id",
        "build_timestamp",
        "serving_snapshot_id",
        "build_script",
        "index_type",
        "notes",
    ],
    EVAL_RUN_LOG: [
        "run_id",
        "eval_set",
        "run_timestamp",
        "model",
        "route",
        "score_summary",
        "notes",
    ],
}
