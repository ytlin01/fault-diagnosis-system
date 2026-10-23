"""Deterministic pairing and abstention proposal builder for the C1STN gold v2.

Pairs each mapped case's accepted canonical causes with its accepted canonical
actions and encodes abstention for the unmapped ones. This module produces a
*proposal only*: every pair records its basis — ``shared_alias_evidence`` when
the cause and the action were both evidenced by the same alias pattern in the
accepted mapping proposal, ``case_level_cross_product`` when the pair arises
only from the case-level cross product of accepted labels and the binding
therefore needs domain confirmation. Unmapped cases are proposed as abstention
``required`` carrying their recorded unmapped reason. Nothing here is reviewed
truth.
"""

from __future__ import annotations

from typing import Any, Mapping

from services.evaluation.route_a_golden_annotation import validate_annotation_queue
from services.evaluation.route_a_reviewed_gold import GOLD_V2_QUEUE_ID

PROPOSAL_ID = "v2_task001_c1stn_pairing_abstention_proposal_v1"
MAPPING_PROPOSAL_ID = "v2_task001_c1stn_canonical_mapping_proposal_v1"

PAIRING_RULE = "accepted_labels_cross_product_with_shared_evidence_basis"

_BASIS_SHARED = "shared_alias_evidence"
_BASIS_CROSS = "case_level_cross_product"

_MAPPED_ABSTENTION_REASON = (
    "case carries accepted canonical causes; a ranked canonical answer is "
    "expected, so abstention would fail the safety gate"
)
_UNMAPPED_ABSTENTION_REASON_TEMPLATE = (
    "case maps to no reviewed cause; recorded unmapped reason: {reason}"
)
_UNMAPPED_NO_PAIR_REASON = (
    "case has no accepted canonical causes; nothing to pair"
)


def _evidence_patterns(entries: list[Mapping[str, Any]]) -> dict[str, set[str]]:
    """Map catalog_id -> set of alias patterns that evidenced it."""
    patterns: dict[str, set[str]] = {}
    for entry in entries:
        catalog_id = str(entry["catalog_id"])
        bucket = patterns.setdefault(catalog_id, set())
        for evidence in entry.get("evidence", []):
            bucket.add(str(evidence["pattern"]))
    return patterns


def build_pairing_abstention_proposal(
    gold_v2: Mapping[str, Any],
    mapping_proposal: Mapping[str, Any],
    *,
    gold_v2_path: str,
    gold_v2_sha256: str,
    mapping_proposal_path: str,
    mapping_proposal_sha256: str,
) -> dict[str, Any]:
    """Build the pairing and abstention proposal from gold v2 and its accepted
    mapping proposal.

    Fails closed when gold v2 is not the expected queue, when the mapping
    proposal is not the accepted one, or when a case's accepted canonical IDs
    diverge from the mapping proposal's proposed IDs.
    """
    validate_annotation_queue(gold_v2)
    if gold_v2.get("queue_id") != GOLD_V2_QUEUE_ID:
        raise ValueError(f"expected gold v2 queue {GOLD_V2_QUEUE_ID}")
    if mapping_proposal.get("proposal_id") != MAPPING_PROPOSAL_ID:
        raise ValueError(f"expected mapping proposal {MAPPING_PROPOSAL_ID}")
    proposal_cases = {
        case["case_id"]: case for case in mapping_proposal.get("cases", [])
    }
    cases: list[dict[str, Any]] = []
    binding_review_case_ids: list[str] = []
    abstention_required_case_ids: list[str] = []
    shared_pair_count = 0
    cross_pair_count = 0
    cases_with_pairs = 0
    for raw_case in gold_v2["cases"]:
        review = raw_case["review"]
        proposed = proposal_cases.get(raw_case["case_id"])
        if proposed is None:
            raise ValueError(
                f"mapping proposal is missing case {raw_case['case_id']}"
            )
        cause_patterns = _evidence_patterns(proposed.get("proposed_causes", []))
        action_patterns = _evidence_patterns(proposed.get("proposed_actions", []))
        canonical_causes = list(review.get("canonical_cause_ids", []))
        canonical_actions = list(review.get("canonical_action_ids", []))
        # Gold v2 must be exactly the accepted proposal's labels; any drift
        # means the wrong inputs were supplied.
        if sorted(canonical_causes) != sorted(cause_patterns):
            raise ValueError(
                f"{raw_case['case_id']}: canonical causes diverge from the "
                "accepted mapping proposal"
            )
        if sorted(canonical_actions) != sorted(action_patterns):
            raise ValueError(
                f"{raw_case['case_id']}: canonical actions diverge from the "
                "accepted mapping proposal"
            )
        proposed_pairs: list[dict[str, Any]] = []
        if canonical_causes and canonical_actions:
            cases_with_pairs += 1
            for cause_id in canonical_causes:
                for action_id in canonical_actions:
                    shared = sorted(
                        cause_patterns.get(cause_id, set())
                        & action_patterns.get(action_id, set())
                    )
                    basis = _BASIS_SHARED if shared else _BASIS_CROSS
                    if shared:
                        shared_pair_count += 1
                    else:
                        cross_pair_count += 1
                    proposed_pairs.append(
                        {
                            "cause_id": cause_id,
                            "action_id": action_id,
                            "basis": basis,
                            "shared_patterns": shared,
                        }
                    )
        if canonical_causes:
            abstention = "not_expected"
            abstention_reason = _MAPPED_ABSTENTION_REASON
            no_pair_reason = (
                "" if canonical_actions else review["unmapped_reason"]["actions"]
            )
            pairing_state = (
                "pairs_proposed" if canonical_actions else "no_reviewed_action_to_pair"
            )
        else:
            abstention = "required"
            abstention_required_case_ids.append(raw_case["case_id"])
            abstention_reason = _UNMAPPED_ABSTENTION_REASON_TEMPLATE.format(
                reason=review["unmapped_reason"]["causes"]
            )
            no_pair_reason = _UNMAPPED_NO_PAIR_REASON
            pairing_state = "unmapped_nothing_to_pair"
        if any(pair["basis"] == _BASIS_CROSS for pair in proposed_pairs):
            binding_review_case_ids.append(raw_case["case_id"])
        cases.append(
            {
                "case_id": raw_case["case_id"],
                "scenario_id": raw_case["scenario_id"],
                "pairing_state": pairing_state,
                "proposed_pairs": proposed_pairs,
                "no_pair_reason": no_pair_reason,
                "proposed_abstention": abstention,
                "abstention_reason": abstention_reason,
                "proposal_state": "proposed_not_reviewed",
            }
        )
    return {
        "schema_version": "route_a_pairing_abstention_proposal_v1",
        "proposal_id": PROPOSAL_ID,
        "pairing_rule": PAIRING_RULE,
        "derived_from": {
            "gold_queue_id": gold_v2.get("queue_id"),
            "gold_path": gold_v2_path,
            "gold_sha256": gold_v2_sha256,
            "mapping_proposal_id": mapping_proposal.get("proposal_id"),
            "mapping_proposal_path": mapping_proposal_path,
            "mapping_proposal_sha256": mapping_proposal_sha256,
        },
        "review_gate": (
            "Proposal only. Every case_level_cross_product pair binding and "
            "every abstention encoding requires data-owner review before any "
            "expert-ranking expected-label export."
        ),
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "mapped_case_count": sum(
                1 for case in cases if case["proposed_abstention"] == "not_expected"
            ),
            "unmapped_case_count": len(abstention_required_case_ids),
            "cases_with_pairs": cases_with_pairs,
            "proposed_pair_count": shared_pair_count + cross_pair_count,
            "shared_evidence_pair_count": shared_pair_count,
            "cross_product_only_pair_count": cross_pair_count,
            "binding_review_case_ids": binding_review_case_ids,
            "abstention_required_case_ids": abstention_required_case_ids,
        },
    }
