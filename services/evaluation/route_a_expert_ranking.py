"""Dependency-free Route A expert-ranking evaluator.

Evaluates candidate cause/action rankings against governed gold labels per
the frozen ``route_a_expert_ranking_metrics_v1`` policy in
``contracts/evaluation/route_a_expert_ranking_input_v1.schema.json``:
cause and cause/action-pair recall at cutoffs 1/3/5, MRR at 5, the
abstention safety gate, and no composite score. Domain-correctness
aggregates count only ``reviewed``/``adjudicated`` labels; provisional
maturities are reported separately as framework evidence.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

EXPERT_RANKING_INPUT_VERSION = "route_a_expert_ranking_input_v1"
REPORT_VERSION = "route_a_expert_ranking_report_v1"

FROZEN_METRIC_POLICY: dict[str, Any] = {
    "policy_version": "route_a_expert_ranking_metrics_v1",
    "ranking_depth": 5,
    "primary_metric": "cause_action_pair_recall_at_3",
    "cause_recall_cutoffs": [1, 3, 5],
    "pair_recall_cutoffs": [1, 3, 5],
    "mrr_cutoff": 5,
    "domain_correctness_label_maturities": ["reviewed", "adjudicated"],
    "abstention_safety_gate": (
        "required_abstention_requires_no_ranked_results;"
        "not_expected_abstention_is_failure"
    ),
    "composite_score": "prohibited",
}

_ELIGIBLE_MATURITIES = set(FROZEN_METRIC_POLICY["domain_correctness_label_maturities"])
_CAUSE_CUTOFFS = FROZEN_METRIC_POLICY["cause_recall_cutoffs"]
_PAIR_CUTOFFS = FROZEN_METRIC_POLICY["pair_recall_cutoffs"]
_MRR_CUTOFF = FROZEN_METRIC_POLICY["mrr_cutoff"]
_PARTITIONS = {"development", "validation", "blind"}
_MATURITIES = {"assumed_label_provisional", "provisional", "reviewed", "adjudicated"}
_ABSTENTIONS = {"required", "allowed", "not_expected"}


class ExpertRankingInputError(ValueError):
    """Raised when an expert-ranking input violates the frozen contract."""


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExpertRankingInputError(f"{field} must be an object")
    return value


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExpertRankingInputError(f"{field} must be a non-empty string")
    return value


def _require_enum(value: Any, allowed: set[str], field: str) -> str:
    if value not in allowed:
        raise ExpertRankingInputError(f"{field} is invalid: {value!r}")
    return value


def validate_expert_ranking_input(payload: Mapping[str, Any]) -> None:
    """Structurally validate an input against the frozen contract."""
    if payload.get("schema_version") != EXPERT_RANKING_INPUT_VERSION:
        raise ExpertRankingInputError(
            f"schema_version must be {EXPERT_RANKING_INPUT_VERSION}"
        )
    policy = _require_mapping(payload.get("metric_policy"), "metric_policy")
    for key, expected in FROZEN_METRIC_POLICY.items():
        if policy.get(key) != expected:
            raise ExpertRankingInputError(
                f"metric_policy.{key} must equal the frozen value {expected!r}"
            )
    candidate = _require_mapping(payload.get("candidate"), "candidate")
    for field in (
        "candidate_id",
        "graph_version",
        "snapshot_id",
        "data_maturity",
        "config_digest",
    ):
        _require_str(candidate.get(field), f"candidate.{field}")
    _require_enum(
        candidate.get("data_maturity"), _MATURITIES, "candidate.data_maturity"
    )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ExpertRankingInputError("cases must be a non-empty array")
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(cases):
        case = _require_mapping(raw_case, f"cases[{index}]")
        case_id = _require_str(case.get("case_id"), f"cases[{index}].case_id")
        if case_id in seen_ids:
            raise ExpertRankingInputError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        _require_str(case.get("scenario_id"), f"cases[{index}].scenario_id")
        _require_enum(
            case.get("partition"), _PARTITIONS, f"cases[{index}].partition"
        )
        _require_enum(
            case.get("label_maturity"), _MATURITIES, f"cases[{index}].label_maturity"
        )
        if not isinstance(case.get("abstained"), bool):
            raise ExpertRankingInputError(
                f"cases[{index}].abstained must be a boolean"
            )
        expected = _require_mapping(
            case.get("expected"), f"cases[{index}].expected"
        )
        _require_enum(
            expected.get("abstention"),
            _ABSTENTIONS,
            f"cases[{index}].expected.abstention",
        )
        for field in ("acceptable_cause_ids", "acceptable_action_pairs"):
            values = expected.get(field)
            if not isinstance(values, list):
                raise ExpertRankingInputError(
                    f"cases[{index}].expected.{field} must be an array"
                )
        causes = expected["acceptable_cause_ids"]
        if len(set(causes)) != len(causes):
            raise ExpertRankingInputError(
                f"cases[{index}].expected.acceptable_cause_ids must be unique"
            )
        pairs = expected["acceptable_action_pairs"]
        pair_keys = set()
        for pair_index, raw_pair in enumerate(pairs):
            pair = _require_mapping(
                raw_pair, f"cases[{index}].expected.acceptable_action_pairs[{pair_index}]"
            )
            key = (
                _require_str(pair.get("cause_id"), "pair.cause_id"),
                _require_str(pair.get("action_id"), "pair.action_id"),
            )
            pair_keys.add(key)
        if len(pair_keys) != len(pairs):
            raise ExpertRankingInputError(
                f"cases[{index}].expected.acceptable_action_pairs must be unique"
            )
        results = case.get("ranked_results")
        if not isinstance(results, list) or len(results) > 5:
            raise ExpertRankingInputError(
                f"cases[{index}].ranked_results must be an array of at most 5"
            )
        ranks: set[int] = set()
        for result_index, raw_result in enumerate(results):
            result = _require_mapping(
                raw_result, f"cases[{index}].ranked_results[{result_index}]"
            )
            rank = result.get("rank")
            if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= 5:
                raise ExpertRankingInputError(
                    f"cases[{index}].ranked_results[{result_index}].rank "
                    "must be an integer in [1, 5]"
                )
            if rank in ranks:
                raise ExpertRankingInputError(
                    f"cases[{index}] has duplicate rank {rank}"
                )
            ranks.add(rank)
            _require_str(
                result.get("cause_id"),
                f"cases[{index}].ranked_results[{result_index}].cause_id",
            )
            action_ids = result.get("action_ids")
            if not isinstance(action_ids, list) or not all(
                isinstance(item, str) and item for item in action_ids
            ):
                raise ExpertRankingInputError(
                    f"cases[{index}].ranked_results[{result_index}].action_ids "
                    "must be an array of non-empty strings"
                )
            if len(set(action_ids)) != len(action_ids):
                raise ExpertRankingInputError(
                    f"cases[{index}].ranked_results[{result_index}].action_ids "
                    "must be unique"
                )


def _abstention_gate(
    abstention: str, abstained: bool, ranked_results: Sequence[Mapping[str, Any]]
) -> str:
    if abstention == "required":
        if not abstained:
            return "failure"
        if ranked_results:
            return "failure"
        return "pass"
    if abstention == "not_expected":
        return "failure" if abstained else "pass"
    return "pass"


def _cause_recall_at(
    results: Sequence[Mapping[str, Any]], acceptable: set[str], cutoff: int
) -> float | None:
    if not acceptable:
        return None
    top = [str(result["cause_id"]) for result in results[:cutoff]]
    hits = len(acceptable.intersection(top))
    return hits / len(acceptable)


def _pair_recall_at(
    results: Sequence[Mapping[str, Any]],
    acceptable: set[tuple[str, str]],
    cutoff: int,
) -> float | None:
    if not acceptable:
        return None
    proposed = {
        (str(result["cause_id"]), str(action_id))
        for result in results[:cutoff]
        for action_id in result.get("action_ids", [])
    }
    hits = len(acceptable.intersection(proposed))
    return hits / len(acceptable)


def _mrr_at(
    results: Sequence[Mapping[str, Any]], acceptable: set[str], cutoff: int
) -> float | None:
    if not acceptable:
        return None
    for result in results[:cutoff]:
        if str(result["cause_id"]) in acceptable:
            return 1.0 / float(result["rank"])
    return 0.0


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def evaluate_expert_ranking(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate the ranking input and produce the frozen-policy report."""
    validate_expert_ranking_input(payload)
    case_reports: list[dict[str, Any]] = []
    abstention_failures: list[dict[str, str]] = []
    eligible_cause_recalls: dict[int, list[float]] = {k: [] for k in _CAUSE_CUTOFFS}
    eligible_pair_recalls: dict[int, list[float]] = {k: [] for k in _PAIR_CUTOFFS}
    eligible_mrr: list[float] = []
    provisional_case_ids: list[str] = []
    for case in payload["cases"]:
        results = sorted(case["ranked_results"], key=lambda item: item["rank"])
        acceptable_causes = set(case["expected"]["acceptable_cause_ids"])
        acceptable_pairs = {
            (pair["cause_id"], pair["action_id"])
            for pair in case["expected"]["acceptable_action_pairs"]
        }
        gate = _abstention_gate(
            case["expected"]["abstention"], case["abstained"], results
        )
        eligible = case["label_maturity"] in _ELIGIBLE_MATURITIES
        excluded: list[str] = []
        if not eligible:
            provisional_case_ids.append(case["case_id"])
            excluded.append("label_maturity_not_domain_correctness_eligible")
        if not acceptable_causes:
            excluded.append("no_acceptable_causes")
        if not acceptable_pairs:
            excluded.append("no_acceptable_action_pairs")
        if gate == "failure":
            abstention_failures.append(
                {
                    "case_id": case["case_id"],
                    "expected_abstention": case["expected"]["abstention"],
                    "abstained": str(case["abstained"]).lower(),
                    "ranked_result_count": str(len(results)),
                }
            )
        cause_recalls = {
            f"cause_recall_at_{cutoff}": _cause_recall_at(
                results, acceptable_causes, cutoff
            )
            for cutoff in _CAUSE_CUTOFFS
        }
        pair_recalls = {
            f"pair_recall_at_{cutoff}": _pair_recall_at(
                results, acceptable_pairs, cutoff
            )
            for cutoff in _PAIR_CUTOFFS
        }
        mrr = _mrr_at(results, acceptable_causes, _MRR_CUTOFF)
        if eligible:
            for cutoff in _CAUSE_CUTOFFS:
                value = cause_recalls[f"cause_recall_at_{cutoff}"]
                if value is not None:
                    eligible_cause_recalls[cutoff].append(value)
            for cutoff in _PAIR_CUTOFFS:
                value = pair_recalls[f"pair_recall_at_{cutoff}"]
                if value is not None:
                    eligible_pair_recalls[cutoff].append(value)
            if mrr is not None:
                eligible_mrr.append(mrr)
        case_reports.append(
            {
                "case_id": case["case_id"],
                "scenario_id": case["scenario_id"],
                "partition": case["partition"],
                "label_maturity": case["label_maturity"],
                "domain_correctness_eligible": eligible,
                "abstention_gate": gate,
                **cause_recalls,
                **pair_recalls,
                "mrr_at_5": mrr,
                "excluded_from": excluded,
            }
        )
    primary = _mean(eligible_pair_recalls[3])
    return {
        "schema_version": REPORT_VERSION,
        "metric_policy": dict(payload["metric_policy"]),
        "candidate": dict(payload["candidate"]),
        "case_count": len(case_reports),
        "domain_correctness_case_count": len(case_reports)
        - len(provisional_case_ids),
        "primary_metric": {
            "name": FROZEN_METRIC_POLICY["primary_metric"],
            "value": primary,
            "eligible_case_count": len(eligible_pair_recalls[3]),
        },
        "aggregate": {
            f"mean_cause_recall_at_{cutoff}": _mean(eligible_cause_recalls[cutoff])
            for cutoff in _CAUSE_CUTOFFS
        }
        | {
            f"mean_pair_recall_at_{cutoff}": _mean(eligible_pair_recalls[cutoff])
            for cutoff in _PAIR_CUTOFFS
        }
        | {"mean_mrr_at_5": _mean(eligible_mrr)},
        "abstention_safety_gate_failures": abstention_failures,
        "provisional_maturity_case_ids": provisional_case_ids,
        "excluded_case_count": sum(
            1 for report in case_reports if report["excluded_from"]
        ),
        "cases": case_reports,
        "composite_score": FROZEN_METRIC_POLICY["composite_score"],
    }
