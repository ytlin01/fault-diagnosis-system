"""Old-KG candidate ranking and expert-ranking input assembly.

Turns per-case executor retrieval output into frozen-rule ranked results
(executor order; dedup by normalized cause text with first-seen action
union; top 5; unmapped causes keep their rank slot as
``unmapped:<digest8>`` pseudo-ids; no scores) and joins them with gold v3
expected labels into the frozen ``route_a_expert_ranking_input_v1``
payload. Graph element IDs never enter the input; only approved mappings
may feed scored evaluation.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from services.evaluation.old_tpdx_expert_ranking_mapping import (
    mapping_lookup,
    normalize_text,
)
from services.evaluation.route_a_expert_ranking import (
    EXPERT_RANKING_INPUT_VERSION,
    FROZEN_METRIC_POLICY,
    validate_expert_ranking_input,
)

INPUT_ASSEMBLY_VERSION = "route_a_expert_ranking_input_assembly_v1"


def unmapped_cause_id(normalized_cause_text: str) -> str:
    """Stable graph-agnostic pseudo-id for a cause outside the vocabulary."""
    digest = hashlib.sha256(normalized_cause_text.encode("utf-8")).hexdigest()
    return f"unmapped:{digest[:8]}"


def build_ranked_results(
    retrieval_items: Sequence[Mapping[str, Any]],
    mapping: Mapping[str, Any],
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    """Apply the frozen ranking rule to one case's executor items."""
    cause_lookup, action_lookup = mapping_lookup(mapping)
    ordered: dict[str, dict[str, Any]] = {}
    for item in retrieval_items:
        cause_text = str((item.get("cause") or {}).get("description") or "").strip()
        if not cause_text:
            continue
        normalized = normalize_text(cause_text)
        entry = ordered.setdefault(
            normalized, {"cause_text": cause_text, "action_ids": []}
        )
        action_text = str((item.get("action") or {}).get("action_name") or "").strip()
        if not action_text:
            continue
        action_id = action_lookup.get(normalize_text(action_text))
        if action_id and action_id not in entry["action_ids"]:
            entry["action_ids"].append(action_id)
    ranked_results: list[dict[str, Any]] = []
    for normalized, entry in ordered.items():
        canonical = cause_lookup.get(normalized)
        ranked_results.append(
            {
                "rank": len(ranked_results) + 1,
                "cause_id": (
                    canonical
                    if canonical
                    else unmapped_cause_id(normalized)
                ),
                "action_ids": entry["action_ids"],
            }
        )
        if len(ranked_results) == top_k:
            break
    return {
        "ranked_results": ranked_results,
        "abstained": not ranked_results,
        "retrieval_row_count": len(retrieval_items),
    }


def build_expert_ranking_input(
    gold_v3: Mapping[str, Any],
    mapping: Mapping[str, Any],
    retrieval_outputs: Mapping[str, Mapping[str, Any]],
    *,
    candidate_id: str,
    graph_version: str,
    snapshot_id: str,
    data_maturity: str,
    config_path: str,
    config_digest: str,
) -> dict[str, Any]:
    """Assemble the frozen expert-ranking input from gold v3 and candidates.

    ``retrieval_outputs`` maps case_id -> executor ``{items, ...}`` dict.
    Fails closed via the frozen contract validator before returning.
    """
    cases: list[dict[str, Any]] = []
    for case in gold_v3["cases"]:
        retrieval = retrieval_outputs.get(case["case_id"])
        if retrieval is None:
            raise ValueError(f"missing retrieval output for {case['case_id']}")
        ranked = build_ranked_results(retrieval.get("items", []), mapping)
        review = case["review"]
        cases.append(
            {
                "case_id": case["case_id"],
                "scenario_id": case["scenario_id"],
                "partition": case["partition"],
                "label_maturity": review["label_maturity"],
                "expected": {
                    "abstention": review["abstention"]["expected"],
                    "acceptable_cause_ids": list(
                        review["canonical_cause_ids"]
                    ),
                    "acceptable_action_pairs": [
                        {"cause_id": pair["cause_id"], "action_id": pair["action_id"]}
                        for pair in review["pairing"]["acceptable_action_pairs"]
                    ],
                },
                "ranked_results": ranked["ranked_results"],
                "abstained": ranked["abstained"],
            }
        )
    payload = {
        "schema_version": EXPERT_RANKING_INPUT_VERSION,
        "metric_policy": dict(FROZEN_METRIC_POLICY),
        "candidate": {
            "candidate_id": candidate_id,
            "graph_version": graph_version,
            "snapshot_id": snapshot_id,
            "data_maturity": data_maturity,
            "config_digest": config_digest,
        },
        "assembly": {
            "assembly_version": INPUT_ASSEMBLY_VERSION,
            "mapping_id": mapping.get("mapping_id"),
            "mapping_snapshot_id": mapping.get("snapshot_id"),
            "config_path": config_path,
        },
        "cases": cases,
    }
    validate_expert_ranking_input(payload)
    return payload
