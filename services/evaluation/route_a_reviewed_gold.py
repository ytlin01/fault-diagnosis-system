"""Deterministic builder for the attestation-reviewed Route A C1STN gold set.

The reviewed gold set is derived from the provisional annotation seed and the
accepted expert-review workbook. Per-case canonical cause/action selections
were never recorded, so the reviewed labels carry the accepted source-suggested
material with an explicit ``not_mapped`` state. Nothing in this module invents
domain mappings.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from services.evaluation.route_a_golden_annotation import validate_annotation_queue

GOLD_QUEUE_ID = "v2_task001_c1stn_error_code_reviewed_gold_v1"
REGISTRY_ID = "route_a_scenario_registry_v1"
ATTESTATION_REVIEWER = "data_owner_attested_domain_review"
ATTESTATION_DATE = "2026-08-18"
ACCEPTANCE_REFERENCE = (
    "docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/notes.md "
    "section 'Recorded - acceptance decision: originals accepted as proposed' "
    "(2026-08-18)"
)

_PLANNED_TYPES = (
    "EC",
    "PHEN",
    "ASSET",
    "AMB",
    "PARTIAL",
    "MULTI",
    "ABSTAIN",
)
# Four development, one validation, one blind per type, per coverage plan v1.
_PARTITION_SLOTS = (
    "development",
    "development",
    "development",
    "development",
    "validation",
    "blind",
)
_TYPE_QUERY_TYPE = {
    "EC": "ec",
    "PHEN": "phenomenon",
    "ASSET": "asset",
    "AMB": "ambiguous",
    "PARTIAL": "partial_chain",
    "MULTI": "multiple_valid_answer",
    "ABSTAIN": "no_hit_abstention",
}


def _reviewed_catalog_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "cause_id": entry["cause_id"],
        "display_name": entry["display_name"],
        "definition": entry.get("definition", ""),
        "family": entry.get("family", ""),
        "review": {
            "state": "reviewed_by_attestation",
            "reviewer": ATTESTATION_REVIEWER,
            "reviewed_at": ATTESTATION_DATE,
            "source": "accepted workbook V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v7",
        },
    }


def _reviewed_action_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action_id": entry["action_id"],
        "display_name": entry["display_name"],
        "definition": entry.get("definition", ""),
        "action_type": entry.get("action_type", ""),
        "review": {
            "state": "reviewed_by_attestation",
            "reviewer": ATTESTATION_REVIEWER,
            "reviewed_at": ATTESTATION_DATE,
            "source": "accepted workbook V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v7",
        },
    }


def build_reviewed_gold(
    seed: Mapping[str, Any],
    cause_catalog: Sequence[Mapping[str, Any]],
    repair_action_catalog: Sequence[Mapping[str, Any]],
    *,
    seed_path: str,
    seed_sha256: str,
    workbook_path: str,
    workbook_sha256: str,
) -> dict[str, Any]:
    """Build the reviewed gold queue from the seed and accepted vocabulary."""
    validate_annotation_queue(seed)
    cases: list[dict[str, Any]] = []
    for raw_case in seed["cases"]:
        case = dict(raw_case)
        case["seed_status"] = "reviewed_by_attestation"
        case["review"] = {
            "decision": "accept",
            "label_maturity": "reviewed",
            "review_basis": "bulk_data_owner_attestation",
            "reviewer": ATTESTATION_REVIEWER,
            "reviewed_at": ATTESTATION_DATE,
            "accepted_material": "source_suggested_repair_action",
            "canonical_cause_ids": [],
            "canonical_action_ids": [],
            "mapping_state": "not_mapped",
        }
        cases.append(case)
    gold = {
        "schema_version": "route_a_annotation_queue_v1",
        "queue_id": GOLD_QUEUE_ID,
        "queue_state": "reviewed_by_attestation",
        "provenance": {
            "derived_from_queue_id": seed["queue_id"],
            "seed_path": seed_path,
            "seed_sha256": seed_sha256,
            "accepted_workbook_path": workbook_path,
            "accepted_workbook_sha256": workbook_sha256,
            "acceptance_reference": ACCEPTANCE_REFERENCE,
            "attestation_date": ATTESTATION_DATE,
            "evidence_basis": (
                "Data-owner verbal attestation of an unnamed domain expert "
                "review; originals accepted as proposed. No per-case canonical "
                "selections or written review artifact exist."
            ),
        },
        "source": dict(seed["source"]),
        "selection_policy": dict(seed["selection_policy"]),
        "cause_catalog": [_reviewed_catalog_entry(entry) for entry in cause_catalog],
        "repair_action_catalog": [
            _reviewed_action_entry(entry) for entry in repair_action_catalog
        ],
        "cause_action_pair_catalog": [],
        "cases": cases,
    }
    validate_annotation_queue(gold)
    return gold


GOLD_V2_QUEUE_ID = "v2_task001_c1stn_error_code_reviewed_gold_v2"
MAPPING_ACCEPTANCE_REFERENCE = (
    "docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/notes.md "
    "section 'Accepted - canonical mapping proposal v1' (2026-08-18): data "
    "owner confirmed the four interpretive bridges as-is (cylinder "
    "not-in-position -> cylinder_stuck; not-enabled -> axis_drive_fault; "
    "negative-pressure check -> verify_air_supply action; vision "
    "positioning -> camera_alignment_offset + verify_image_and_alignment)"
)


def build_gold_v2(
    gold_v1: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    gold_v1_path: str,
    gold_v1_sha256: str,
    proposal_path: str,
    proposal_sha256: str,
) -> dict[str, Any]:
    """Regenerate the gold queue with accepted canonical labels.

    Fills each case's canonical cause/action IDs from the accepted mapping
    proposal. Cases the proposal left unmapped stay explicitly unmapped with
    their recorded reason. No cause/action pairings are asserted; pairing is
    a later, separately reviewed step.
    """
    validate_annotation_queue(gold_v1)
    if gold_v1.get("queue_id") != GOLD_QUEUE_ID:
        raise ValueError(f"expected gold v1 queue {GOLD_QUEUE_ID}")
    proposal_cases = {
        case["case_id"]: case for case in proposal.get("cases", [])
    }
    cause_ids = {entry["cause_id"] for entry in gold_v1.get("cause_catalog", [])}
    action_ids = {
        entry["action_id"] for entry in gold_v1.get("repair_action_catalog", [])
    }
    cases: list[dict[str, Any]] = []
    for raw_case in gold_v1["cases"]:
        case = dict(raw_case)
        review = dict(case["review"])
        proposed = proposal_cases.get(case["case_id"])
        if proposed is None:
            raise ValueError(f"proposal is missing case {case['case_id']}")
        canonical_causes = sorted(
            item["catalog_id"] for item in proposed["proposed_causes"]
        )
        canonical_actions = sorted(
            item["catalog_id"] for item in proposed["proposed_actions"]
        )
        unknown = set(canonical_causes) - cause_ids
        if unknown:
            raise ValueError(f"cause ids outside catalog: {sorted(unknown)}")
        unknown = set(canonical_actions) - action_ids
        if unknown:
            raise ValueError(f"action ids outside catalog: {sorted(unknown)}")
        review["canonical_cause_ids"] = canonical_causes
        review["canonical_action_ids"] = canonical_actions
        review["mapping_state"] = "mapped" if canonical_causes else "not_mapped"
        review["unmapped_reason"] = proposed["unmapped_reason"]
        review["mapping_acceptance"] = {
            "proposal_id": proposal.get("proposal_id"),
            "alias_table_version": proposal.get("alias_table_version"),
            "reference": MAPPING_ACCEPTANCE_REFERENCE,
        }
        case["review"] = review
        cases.append(case)
    gold_v2 = dict(gold_v1)
    gold_v2["queue_id"] = GOLD_V2_QUEUE_ID
    gold_v2["queue_state"] = "reviewed_by_attestation_mapping_confirmed"
    gold_v2["provenance"] = {
        "derived_from_queue_id": gold_v1["queue_id"],
        "gold_v1_path": gold_v1_path,
        "gold_v1_sha256": gold_v1_sha256,
        "accepted_proposal_path": proposal_path,
        "accepted_proposal_sha256": proposal_sha256,
        "acceptance_reference": MAPPING_ACCEPTANCE_REFERENCE,
        "attestation_date": ATTESTATION_DATE,
        "pairing_state": "not_asserted",
    }
    gold_v2["cases"] = cases
    validate_annotation_queue(gold_v2)
    return gold_v2


GOLD_V3_QUEUE_ID = "v2_task001_c1stn_error_code_reviewed_gold_v3"
PAIRING_PROPOSAL_ID = "v2_task001_c1stn_pairing_abstention_proposal_v1"
PAIRING_ACCEPTANCE_REFERENCE = (
    "docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/subtasks/"
    "expert_ranking_first_run/notes.md section 'Accepted - pairing and "
    "abstention proposal v1' (2026-08-19): data owner accepted all 11 pair "
    "bindings including the 5 case-level cross-product pairs, kept the 7 "
    "action-less mapped cases pair-less, and confirmed abstention=required "
    "for the 3 unmapped cases"
)


def build_gold_v3(
    gold_v2: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    gold_v2_path: str,
    gold_v2_sha256: str,
    proposal_path: str,
    proposal_sha256: str,
) -> dict[str, Any]:
    """Regenerate the gold queue with accepted pairing and abstention labels.

    Applies the accepted pairing and abstention proposal to gold v2: each
    case carries its accepted ``acceptable_action_pairs`` and abstention
    encoding with the acceptance reference. Fails closed on the wrong gold
    queue, the wrong proposal, a missing case, or any pair ID outside the
    reviewed catalogs.
    """
    validate_annotation_queue(gold_v2)
    if gold_v2.get("queue_id") != GOLD_V2_QUEUE_ID:
        raise ValueError(f"expected gold v2 queue {GOLD_V2_QUEUE_ID}")
    if proposal.get("proposal_id") != PAIRING_PROPOSAL_ID:
        raise ValueError(f"expected pairing proposal {PAIRING_PROPOSAL_ID}")
    proposal_cases = {
        case["case_id"]: case for case in proposal.get("cases", [])
    }
    cause_ids = {entry["cause_id"] for entry in gold_v2.get("cause_catalog", [])}
    action_ids = {
        entry["action_id"] for entry in gold_v2.get("repair_action_catalog", [])
    }
    cases: list[dict[str, Any]] = []
    for raw_case in gold_v2["cases"]:
        case = dict(raw_case)
        review = dict(case["review"])
        proposed = proposal_cases.get(case["case_id"])
        if proposed is None:
            raise ValueError(
                f"pairing proposal is missing case {case['case_id']}"
            )
        pairs: list[dict[str, str]] = []
        for raw_pair in proposed.get("proposed_pairs", []):
            cause_id = str(raw_pair["cause_id"])
            action_id = str(raw_pair["action_id"])
            if cause_id not in cause_ids:
                raise ValueError(f"pair cause outside catalog: {cause_id}")
            if action_id not in action_ids:
                raise ValueError(f"pair action outside catalog: {action_id}")
            pairs.append({"cause_id": cause_id, "action_id": action_id})
        abstention = proposed.get("proposed_abstention")
        if abstention not in ("required", "allowed", "not_expected"):
            raise ValueError(f"invalid abstention encoding: {abstention!r}")
        review["pairing"] = {
            "acceptable_action_pairs": pairs,
            "pairing_state": (
                "pairs_asserted"
                if pairs
                else (
                    "no_reviewed_action_to_pair"
                    if review.get("mapping_state") == "mapped"
                    else "unmapped_abstention_required"
                )
            ),
            "no_pair_reason": proposed.get("no_pair_reason", ""),
        }
        review["abstention"] = {
            "expected": abstention,
            "reason": proposed.get("abstention_reason", ""),
        }
        review["pairing_acceptance"] = {
            "proposal_id": proposal.get("proposal_id"),
            "pairing_rule": proposal.get("pairing_rule"),
            "reference": PAIRING_ACCEPTANCE_REFERENCE,
        }
        case["review"] = review
        cases.append(case)
    gold_v3 = dict(gold_v2)
    gold_v3["queue_id"] = GOLD_V3_QUEUE_ID
    gold_v3["queue_state"] = "reviewed_by_attestation_mapping_and_pairing_confirmed"
    gold_v3["provenance"] = {
        "derived_from_queue_id": gold_v2["queue_id"],
        "gold_v2_path": gold_v2_path,
        "gold_v2_sha256": gold_v2_sha256,
        "accepted_pairing_proposal_path": proposal_path,
        "accepted_pairing_proposal_sha256": proposal_sha256,
        "acceptance_reference": PAIRING_ACCEPTANCE_REFERENCE,
        "acceptance_date": "2026-08-19",
        "evidence_basis": (
            "Data-owner in-session acceptance of the pairing and abstention "
            "proposal on 2026-08-19; evidence is the data owner's session "
            "answers, no written review artifact exists."
        ),
        "pairing_state": "asserted",
    }
    gold_v3["cases"] = cases
    validate_annotation_queue(gold_v3)
    return gold_v3


def build_scenario_registry(
    seed: Mapping[str, Any],
    *,
    gold_queue_id: str = GOLD_QUEUE_ID,
) -> dict[str, Any]:
    """Build the Route A scenario registry from the coverage plan and seed."""
    validate_annotation_queue(seed)
    planned: list[dict[str, Any]] = []
    for type_code in _PLANNED_TYPES:
        for index, partition in enumerate(_PARTITION_SLOTS, start=1):
            planned.append(
                {
                    "scenario_id": f"RA-GOLD-{type_code}-{index:02d}",
                    "type": type_code,
                    "partition": partition,
                    "binding_state": "unbound",
                    "bound_case_ids": [],
                    "coverage_tags": {
                        "query_type": _TYPE_QUERY_TYPE[type_code],
                        "equipment_scope": "to_assign",
                        "difficulty": "to_assign",
                        "language": "to_assign",
                        "abstention": (
                            "required" if type_code == "ABSTAIN" else "not_expected"
                        ),
                    },
                }
            )
    bound: list[dict[str, Any]] = []
    for case in seed["cases"]:
        bound.append(
            {
                "scenario_id": case["scenario_id"],
                "type": "EC",
                "partition": case["partition"],
                "binding_state": "bound",
                "bound_case_ids": [case["case_id"]],
                "binding_queue_id": gold_queue_id,
                "review_state": "reviewed_by_attestation",
                "mapping_state": "not_mapped",
            }
        )
    return {
        "schema_version": "route_a_scenario_registry_v1",
        "registry_id": REGISTRY_ID,
        "plan_reference": (
            "docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/"
            "scenario_registry_coverage_plan_v1.md"
        ),
        "planned_target": {"total": 42, "per_type": 6},
        "planned_scenarios": planned,
        "bound_seed_scenarios": bound,
        "provenance": {
            "acceptance_reference": ACCEPTANCE_REFERENCE,
            "attestation_date": ATTESTATION_DATE,
            "seed_queue_id": seed["queue_id"],
            "gold_queue_id": gold_queue_id,
        },
    }
