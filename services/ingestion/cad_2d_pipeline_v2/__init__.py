"""Governed, synthetic-first CAD 2D A/B/C pipeline primitives.

The package intentionally does not activate a graph or read repository data.
"""

from .config import load_config, validate_config
from .handoff import HandoffSnapshot, compare_legacy_triples, load_cleaned_handoff
from .manual_review import (
    project_completed_review,
    projection_classification_records,
    validate_projection_semantics,
)
from .stages import (
    StageResult,
    audit_asm_bom,
    build_drawing_index,
    build_project_owner_output,
    build_relationships,
    combine_bom_candidate_sources,
    extract_asm_bom,
    extract_fields,
    merge_classifications,
    reuse_historical_bom_candidates,
    validate_b00_word_bundle,
)

__all__ = [
    "StageResult",
    "HandoffSnapshot",
    "audit_asm_bom",
    "build_drawing_index",
    "build_project_owner_output",
    "build_relationships",
    "combine_bom_candidate_sources",
    "extract_asm_bom",
    "extract_fields",
    "compare_legacy_triples",
    "load_config",
    "load_cleaned_handoff",
    "merge_classifications",
    "reuse_historical_bom_candidates",
    "validate_b00_word_bundle",
    "project_completed_review",
    "projection_classification_records",
    "validate_projection_semantics",
    "validate_config",
]
