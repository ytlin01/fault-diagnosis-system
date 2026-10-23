from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.routing import RoutingContext, route_query


DEFAULT_TESTSET_PATHS = (
    REPO_ROOT / "data/eval/phase1_routing_eval_v0.json",
    REPO_ROOT / "data/eval/phase1_kg_diagnosis_eval_v0.json",
    REPO_ROOT / "data/eval/phase1_asset_eval_v0.json",
    REPO_ROOT / "data/eval/phase1_case_retrieval_eval_v0.json",
    REPO_ROOT / "data/eval/phase1_document_evidence_eval_v0.json",
    REPO_ROOT / "data/eval/phase1_safety_negative_eval_v0.json",
    REPO_ROOT / "data/eval/troubleshooting_eval_testset_v0.json",
)

COMMON_REQUIRED_FIELDS = {
    "case_id",
    "track",
    "query",
    "source_status",
    "data_readiness",
    "gold_status",
    "expected_assertion_level",
    "expected",
}

SERVING_FORBIDDEN_BLOCK_KEYS = {
    "response_text",
    "raw_response",
    "resolved_image_path",
    "asset_local_path",
    "asset_source_path",
    "image_path",
    "endpoint",
}


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    track: str
    passed: bool
    errors: tuple[str, ...] = ()


def load_cases(paths: list[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload.get("cases", []):
            case = dict(case)
            case["_source_file"] = str(path.relative_to(REPO_ROOT))
            cases.append(case)
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> list[CaseResult]:
    return [validate_case(case) for case in cases]


def validate_case(case: dict[str, Any]) -> CaseResult:
    errors = validate_common(case)
    track = str(case.get("track", ""))

    if not errors:
        if track == "routing":
            errors.extend(validate_routing_case(case))
        elif track == "kg_diagnosis":
            errors.extend(validate_kg_diagnosis_case(case))
        elif track == "kg_asset":
            errors.extend(validate_asset_case(case))
        elif track == "case_retrieval":
            errors.extend(validate_case_retrieval_case(case))
        elif track in {"document_evidence", "troubleshooting"}:
            errors.extend(validate_evidence_case(case))
        elif track == "safety_negative":
            errors.extend(validate_safety_case(case))
        else:
            errors.append(f"unknown track `{track}`")

    return CaseResult(
        case_id=str(case.get("case_id", "<missing>")),
        track=track or "<missing>",
        passed=not errors,
        errors=tuple(errors),
    )


def validate_common(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(COMMON_REQUIRED_FIELDS - set(case))
    if missing:
        errors.append(f"missing common fields: {', '.join(missing)}")
    if not isinstance(case.get("expected"), dict):
        errors.append("expected must be an object")
    if case.get("source_status") not in {
        "synthetic_or_sanitized_eval_fixture",
        "real_sanitized",
    }:
        errors.append("source_status must be synthetic_or_sanitized_eval_fixture or real_sanitized")
    if case.get("gold_status") not in {"provisional", "reviewed", "frozen"}:
        errors.append("gold_status must be provisional, reviewed, or frozen")
    return errors


def validate_routing_case(case: dict[str, Any]) -> list[str]:
    expected = case["expected"]
    decision = run_router(case)
    errors: list[str] = []

    comparisons = {
        "intent": decision.intent,
        "route_family": decision.route_family,
        "route_target": decision.route,
        "kg_eligible": decision.kg_eligible,
    }
    if "requires_review" in expected:
        comparisons["requires_review"] = decision.requires_review

    for key, actual in comparisons.items():
        if key in expected and expected[key] != actual:
            errors.append(f"{key} expected {expected[key]!r}, got {actual!r}")

    allowed_sources = set(decision.allowed_sources)
    for source in expected.get("allowed_sources", []):
        if source not in allowed_sources:
            errors.append(f"allowed source `{source}` missing from decision")

    blocked_sources = {blocked.source for blocked in decision.blocked_sources}
    for source in expected.get("blocked_sources", []):
        if source not in blocked_sources:
            errors.append(f"blocked source `{source}` missing from decision")

    return errors


def validate_kg_diagnosis_case(case: dict[str, Any]) -> list[str]:
    expected = case["expected"]
    errors: list[str] = []
    triples = expected.get("triples", [])
    if not isinstance(triples, list):
        errors.append("expected.triples must be a list")
    for triple in triples:
        if not (isinstance(triple, list) and len(triple) == 3 and all(isinstance(part, str) for part in triple)):
            errors.append(f"invalid triple shape: {triple!r}")
    if expected.get("kg_eligible") is True and not triples:
        errors.append("kg_eligible=true requires at least one reviewed expected triple")
    if expected.get("kg_eligible") in {"pending", False} and triples:
        errors.append("pending/non-eligible KG cases must not include confirmed triples")
    return errors


def validate_asset_case(case: dict[str, Any]) -> list[str]:
    expected = case["expected"]
    errors: list[str] = []
    if "QPL" in expected.get("hierarchy", []):
        errors.append("asset hierarchy must not require QPL in current v0")
    if "QPL" not in expected.get("must_not_nodes", []):
        errors.append("asset cases should explicitly keep QPL out of current v0 node targets")
    return errors


def validate_case_retrieval_case(case: dict[str, Any]) -> list[str]:
    expected = case["expected"]
    errors: list[str] = []
    if expected.get("evidence_policy") and "confirmed" in str(expected["evidence_policy"]):
        errors.append("case retrieval evidence policy must not be confirmed diagnosis")
    if "promote_related_case_to_confirmed_kg_fact" not in expected.get("must_not", []) and case["case_id"] == "CASE-0001":
        errors.append("related case fixture must guard against KG promotion")
    return errors


def validate_evidence_case(case: dict[str, Any]) -> list[str]:
    expected = case["expected"]
    errors: list[str] = []
    allowed_sources = expected.get("allowed_sources", [])
    if "data/serving_unstructured_vlm" in allowed_sources:
        serving_files = sorted((REPO_ROOT / "data/serving_unstructured_vlm").glob("*.json"))
        if not serving_files:
            errors.append("no serving_unstructured_vlm JSON files found")
        else:
            errors.extend(validate_serving_files(serving_files, expected))

    if "promote_troubleshooting_sop_to_confirmed_kg_fact" in expected.get("must_not", []):
        if expected.get("kg_eligible") is True:
            errors.append("troubleshooting evidence must not be KG eligible by default")

    return errors


def validate_safety_case(case: dict[str, Any]) -> list[str]:
    expected = case["expected"]
    errors: list[str] = []
    if expected.get("unsafe_leak_expected") is not False:
        errors.append("safety_negative cases must set unsafe_leak_expected=false")

    if case.get("expected_assertion_level") == "router_runner":
        decision = run_router(case)
        blocked_sources = {blocked.source for blocked in decision.blocked_sources}
        for source in expected.get("blocked_sources", []):
            if source not in blocked_sources:
                errors.append(f"blocked source `{source}` missing from decision")

    return errors


def validate_serving_files(paths: list[Path], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    anchor_found = False
    forbidden_hits: list[str] = []

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        blocks = payload.get("blocks", [])
        if any(block.get("source_anchor") for block in blocks if isinstance(block, dict)):
            anchor_found = True
        for index, block in enumerate(blocks):
            forbidden_hits.extend(
                f"{path.name}/blocks[{index}]{hit}"
                for hit in find_forbidden_keys(block, SERVING_FORBIDDEN_BLOCK_KEYS)
            )

    if expected.get("must_include_anchor") and not anchor_found:
        errors.append("serving evidence expected at least one block source_anchor")
    if forbidden_hits:
        errors.append("serving block forbidden fields found: " + ", ".join(forbidden_hits[:5]))
    return errors


def find_forbidden_keys(value: Any, forbidden: set[str], path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if key in forbidden:
                hits.append(child_path)
            hits.extend(find_forbidden_keys(child, forbidden, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, forbidden, f"{path}[{index}]"))
    return hits


def run_router(case: dict[str, Any]):
    context_payload = case.get("context", {})
    context = RoutingContext(
        reviewed_diagnostic_chain_available=bool(context_payload.get("reviewed_diagnostic_chain_available", False)),
        asset_structured_source_available=bool(context_payload.get("asset_structured_source_available", False)),
    )
    return route_query(
        {
            "query_text": case["query"],
            "query_type_hint": case.get("query_type_hint"),
            "available_sources": case.get("available_sources", []),
        },
        context,
    )


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    by_track: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_track.setdefault(result.track, {"passed": 0, "failed": 0})
        bucket["passed" if result.passed else "failed"] += 1
    return {
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "by_track": by_track,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run FaultDx Phase 1 eval v0 checks.")
    parser.add_argument("paths", nargs="*", type=Path, help="Optional eval JSON paths.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args(argv)

    paths = args.paths or list(DEFAULT_TESTSET_PATHS)
    cases = load_cases([path if path.is_absolute() else REPO_ROOT / path for path in paths])
    results = validate_cases(cases)
    summary = summarize(results)

    if args.json:
        print(
            json.dumps(
                {
                    "summary": summary,
                    "failures": [
                        {
                            "case_id": result.case_id,
                            "track": result.track,
                            "errors": list(result.errors),
                        }
                        for result in results
                        if not result.passed
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Phase 1 eval v0: {summary['passed']}/{summary['total']} passed")
        for track, counts in sorted(summary["by_track"].items()):
            print(f"- {track}: {counts['passed']} passed, {counts['failed']} failed")
        for result in results:
            if not result.passed:
                print(f"\n{result.case_id} [{result.track}]")
                for error in result.errors:
                    print(f"  - {error}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
