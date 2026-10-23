from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.retrieval.route_c_executor import execute_route_c
from services.routing.query_router import CASE_RETRIEVAL


DEFAULT_FIXTURE_PATH = REPO_ROOT / "data/eval/route_c/route_c_case_benchmark_v0.json"
ROUTE_C_CASE_SOURCE_ID = "rag_fp_case_candidates_v1"
ROUTE_C_CASE_SOURCE_TYPE = "structured_case_candidate"


@dataclass(frozen=True)
class RouteCCaseBenchmarkResult:
    case_id: str
    query_type: str
    expected_no_hit: bool
    label_gap: bool
    rank: int | None
    top1_case_hit: bool
    top3_case_hit: bool
    candidate_only_pass: bool
    source_safety_pass: bool
    no_hit_correct: bool | None
    ranked_candidate_ids: tuple[str, ...]
    errors: tuple[str, ...]


ExecuteFn = Callable[..., dict[str, Any]]


def load_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_fixture(
    fixture: dict[str, Any],
    *,
    execute_fn: ExecuteFn = execute_route_c,
    case_ranking_strategy: str = "lexical_bm25",
    case_hybrid_config: Mapping[str, Any] | None = None,
    light_rag_config: Mapping[str, Any] | None = None,
) -> list[RouteCCaseBenchmarkResult]:
    source_id = str(fixture.get("source_id", ROUTE_C_CASE_SOURCE_ID))
    source_path = REPO_ROOT / str(fixture.get("source_path", "data/processed/aggregates/rag_fp_case_candidates_v1.json"))
    ranking = fixture.get("ranking", {}) if isinstance(fixture.get("ranking"), dict) else {}
    top_k = int(ranking.get("top_k", 10))
    min_score = float(ranking.get("min_score", 0.1))

    return [
        evaluate_case(
            case,
            source_id=source_id,
            source_path=source_path,
            top_k=top_k,
            min_score=min_score,
            execute_fn=execute_fn,
            case_ranking_strategy=case_ranking_strategy,
            case_hybrid_config=case_hybrid_config,
            light_rag_config=light_rag_config,
        )
        for case in fixture.get("cases", [])
        if isinstance(case, dict)
    ]


def evaluate_case(
    case: dict[str, Any],
    *,
    source_id: str,
    source_path: Path,
    top_k: int,
    min_score: float,
    execute_fn: ExecuteFn = execute_route_c,
    case_ranking_strategy: str = "lexical_bm25",
    case_hybrid_config: Mapping[str, Any] | None = None,
    light_rag_config: Mapping[str, Any] | None = None,
) -> RouteCCaseBenchmarkResult:
    expected = case.get("expected", {}) if isinstance(case.get("expected"), dict) else {}
    case_id = str(case.get("case_id", "<missing>"))
    query_type = str(case.get("query_type", "unknown"))
    expected_no_hit = bool(expected.get("no_hit", False))
    acceptable_ids = {str(value) for value in expected.get("acceptable_candidate_ids", [])}
    label_gap = not expected_no_hit and not acceptable_ids
    errors: list[str] = []

    output = execute_fn(
        str(case.get("query", "")),
        route=CASE_RETRIEVAL,
        allowed_sources=(source_id,),
        source_paths={source_id: source_path},
        top_k=top_k,
        min_score=min_score,
        case_ranking_strategy=case_ranking_strategy,
        case_hybrid_config=case_hybrid_config,
        enable_light_rag=bool((light_rag_config or {}).get("enabled", False)),
        light_rag_config=light_rag_config,
    )
    items = [item for item in output.get("items", []) if isinstance(item, dict)]
    ranked_ids = [_candidate_id_from_item(item, source_id) for item in items]
    ranked_ids = [candidate_id for candidate_id in ranked_ids if candidate_id]

    candidate_only_pass = _candidate_only_pass(items)
    source_safety_pass = source_id == ROUTE_C_CASE_SOURCE_ID and _source_safety_pass(items, source_id)

    if expected_no_hit:
        no_hit_correct = not items
        if not no_hit_correct:
            errors.append(f"expected no hit, got {ranked_ids[:3]}")
        if not candidate_only_pass:
            errors.append("no-hit output failed candidate-only checks")
        if not source_safety_pass:
            errors.append("no-hit output failed source-safety checks")
        return RouteCCaseBenchmarkResult(
            case_id=case_id,
            query_type=query_type,
            expected_no_hit=True,
            label_gap=False,
            rank=None,
            top1_case_hit=False,
            top3_case_hit=False,
            candidate_only_pass=candidate_only_pass,
            source_safety_pass=source_safety_pass,
            no_hit_correct=no_hit_correct,
            ranked_candidate_ids=tuple(ranked_ids),
            errors=tuple(errors),
        )

    if label_gap:
        errors.append("positive case missing acceptable_candidate_ids")

    rank = _first_rank(ranked_ids, acceptable_ids)
    top1_case_hit = rank == 1
    top3_case_hit = rank is not None and rank <= 3

    if not items:
        errors.append("no Route C case candidates returned")
    if not candidate_only_pass:
        errors.append("returned items failed candidate-only checks")
    if not source_safety_pass:
        errors.append("returned items failed source-safety checks")

    return RouteCCaseBenchmarkResult(
        case_id=case_id,
        query_type=query_type,
        expected_no_hit=False,
        label_gap=label_gap,
        rank=rank,
        top1_case_hit=top1_case_hit,
        top3_case_hit=top3_case_hit,
        candidate_only_pass=candidate_only_pass,
        source_safety_pass=source_safety_pass,
        no_hit_correct=None,
        ranked_candidate_ids=tuple(ranked_ids),
        errors=tuple(errors),
    )


def summarize(results: list[RouteCCaseBenchmarkResult], fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    positive = [result for result in results if not result.expected_no_hit and not result.label_gap]
    no_hit = [result for result in results if result.expected_no_hit]
    label_gap_results = [result for result in results if result.label_gap]
    label_gap_total = len(label_gap_results) + _fixture_label_gap_count(fixture or {})
    by_type: dict[str, list[RouteCCaseBenchmarkResult]] = defaultdict(list)
    for result in results:
        by_type[result.query_type].append(result)

    return {
        "total": len(results),
        "positive_total": len(positive),
        "no_hit_total": len(no_hit),
        "label_gap_total": label_gap_total,
        "candidate_only_pass": _ratio_count(results, lambda result: result.candidate_only_pass),
        "source_safety_pass": _ratio_count(results, lambda result: result.source_safety_pass),
        "top1_case_hit": _ratio_count(positive, lambda result: result.top1_case_hit),
        "top3_case_hit": _ratio_count(positive, lambda result: result.top3_case_hit),
        "mrr": _mrr(positive),
        "no_hit_precision": _ratio_count(no_hit, lambda result: result.no_hit_correct is True),
        "by_query_type": {
            query_type: {
                "total": len(items),
                "top1_case_hit": _ratio_count(
                    [item for item in items if not item.expected_no_hit and not item.label_gap],
                    lambda result: result.top1_case_hit,
                ),
                "top3_case_hit": _ratio_count(
                    [item for item in items if not item.expected_no_hit and not item.label_gap],
                    lambda result: result.top3_case_hit,
                ),
                "mrr": _mrr([item for item in items if not item.expected_no_hit and not item.label_gap]),
                "no_hit_precision": _ratio_count(
                    [item for item in items if item.expected_no_hit],
                    lambda result: result.no_hit_correct is True,
                ),
            }
            for query_type, items in sorted(by_type.items())
        },
    }


def failures(results: list[RouteCCaseBenchmarkResult]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for result in results:
        metric_failed = False
        if result.expected_no_hit:
            metric_failed = result.no_hit_correct is not True
        elif not result.label_gap:
            metric_failed = not result.top3_case_hit
        if metric_failed or result.errors:
            failed.append(
                {
                    "case_id": result.case_id,
                    "query_type": result.query_type,
                    "rank": result.rank,
                    "ranked_candidate_ids": list(result.ranked_candidate_ids[:5]),
                    "errors": list(result.errors),
                }
            )
    return failed


def _candidate_id_from_item(item: dict[str, Any], source_id: str) -> str | None:
    evidence = item.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return None
    first = evidence[0]
    if not isinstance(first, dict):
        return None
    record_id = str(first.get("source_id", ""))
    prefix = f"{source_id}:"
    return record_id.removeprefix(prefix) if record_id.startswith(prefix) else None


def _candidate_only_pass(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if item.get("result_type") != "case_reference":
            return False
        if item.get("status") != "candidate":
            return False
        if item.get("result_type") == "confirmed_diagnosis":
            return False
        if item.get("status") == "reviewed":
            return False
        text = json.dumps(item, ensure_ascii=False)
        if "confirmed_diagnosis" in text or "reviewed_structured_chain" in text:
            return False
        for action in item.get("actions", []):
            if isinstance(action, dict) and action.get("source_status") != "candidate_supported":
                return False
    return True


def _source_safety_pass(items: list[dict[str, Any]], source_id: str) -> bool:
    for item in items:
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            return False
        for evidence_item in evidence:
            if not isinstance(evidence_item, dict):
                return False
            if evidence_item.get("source_type") != ROUTE_C_CASE_SOURCE_TYPE:
                return False
            if evidence_item.get("source_name") != source_id:
                return False
            if not str(evidence_item.get("source_id", "")).startswith(f"{source_id}:RAG_"):
                return False
            if evidence_item.get("reviewed") is not False:
                return False
            if evidence_item.get("serving_safe") is not True:
                return False
    return True


def _first_rank(ranked_ids: list[str], acceptable_ids: set[str]) -> int | None:
    for index, candidate_id in enumerate(ranked_ids, start=1):
        if candidate_id in acceptable_ids:
            return index
    return None


def _ratio_count(results: list[RouteCCaseBenchmarkResult], predicate) -> dict[str, float | int | None]:
    total = len(results)
    if total == 0:
        return {"passed": 0, "total": 0, "rate": None}
    passed = sum(1 for result in results if predicate(result))
    return {"passed": passed, "total": total, "rate": round(passed / total, 4)}


def _mrr(results: list[RouteCCaseBenchmarkResult]) -> float | None:
    if not results:
        return None
    return round(sum((1 / result.rank) if result.rank else 0 for result in results) / len(results), 4)


def _fixture_label_gap_count(fixture: dict[str, Any]) -> int:
    total = 0
    for gap in fixture.get("label_gaps", []):
        if not isinstance(gap, dict):
            continue
        case_ids = gap.get("case_ids", [])
        total += len(case_ids) if isinstance(case_ids, list) else 1
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Route C related-case benchmark v0.")
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    parser.add_argument(
        "--light-rag",
        action="store_true",
        help="Enable Route C light-RAG rerank with the deterministic stub provider.",
    )
    parser.add_argument(
        "--compare-light-rag",
        action="store_true",
        help="Print lexical-only and light-RAG summaries side by side.",
    )
    parser.add_argument(
        "--case-ranking-strategy",
        choices=("lexical_bm25", "local_sparse_vector", "hybrid_bm25_local_sparse_vector"),
        default="lexical_bm25",
        help="Opt-in Route C case ranking strategy for benchmark comparison.",
    )
    parser.add_argument(
        "--compare-hybrid",
        action="store_true",
        help="Compare lexical, light-RAG stub, local sparse vector, and hybrid rankings.",
    )
    args = parser.parse_args(argv)

    fixture_path = args.fixture if args.fixture.is_absolute() else REPO_ROOT / args.fixture
    fixture = load_fixture(fixture_path)
    if args.compare_hybrid:
        payload = _comparison_payload(fixture)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_comparison(payload)
        return 0
    if args.compare_light_rag:
        lexical_results = evaluate_fixture(fixture)
        light_results = evaluate_fixture(fixture, light_rag_config={"enabled": True, "provider_type": "stub"})
        payload = {
            "lexical_only": {
                "summary": summarize(lexical_results, fixture),
                "failures": failures(lexical_results),
            },
            "light_rag_stub": {
                "summary": summarize(light_results, fixture),
                "failures": failures(light_results),
            },
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_comparison(payload)
        return 0

    light_rag_config = {"enabled": True, "provider_type": "stub"} if args.light_rag else None
    results = evaluate_fixture(
        fixture,
        case_ranking_strategy=args.case_ranking_strategy,
        case_hybrid_config={"lexical_weight": 0.7, "vector_weight": 0.3},
        light_rag_config=light_rag_config,
    )
    summary = summarize(results, fixture)
    failed = failures(results)

    if args.json:
        print(json.dumps({"summary": summary, "failures": failed}, ensure_ascii=False, indent=2))
    else:
        print(f"Route C case benchmark v0: {summary['total']} cases")
        print(f"- positive cases: {summary['positive_total']}")
        print(f"- no-hit cases: {summary['no_hit_total']}")
        print(f"- label gaps recorded: {summary['label_gap_total']}")
        print(f"- candidate_only_pass: {_format_ratio(summary['candidate_only_pass'])}")
        print(f"- source_safety_pass: {_format_ratio(summary['source_safety_pass'])}")
        print(f"- top1_case_hit: {_format_ratio(summary['top1_case_hit'])}")
        print(f"- top3_case_hit: {_format_ratio(summary['top3_case_hit'])}")
        print(f"- mrr: {summary['mrr']}")
        print(f"- no_hit_precision: {_format_ratio(summary['no_hit_precision'])}")
        if failed:
            print("\nFailures / misses:")
            for item in failed:
                print(
                    f"- {item['case_id']} ({item['query_type']}): "
                    f"rank={item['rank']}, top={item['ranked_candidate_ids']}"
                )
                for error in item["errors"]:
                    print(f"  - {error}")

    return 0


def _comparison_payload(fixture: dict[str, Any]) -> dict[str, Any]:
    strategies = {
        "lexical_only": {
            "case_ranking_strategy": "lexical_bm25",
            "light_rag_config": None,
        },
        "light_rag_stub": {
            "case_ranking_strategy": "lexical_bm25",
            "light_rag_config": {"enabled": True, "provider_type": "stub"},
        },
        "local_sparse_vector": {
            "case_ranking_strategy": "local_sparse_vector",
            "light_rag_config": None,
        },
        "hybrid_bm25_local_sparse_vector": {
            "case_ranking_strategy": "hybrid_bm25_local_sparse_vector",
            "case_hybrid_config": {"lexical_weight": 0.7, "vector_weight": 0.3},
            "light_rag_config": None,
        },
    }
    payload: dict[str, Any] = {}
    for label, config in strategies.items():
        results = evaluate_fixture(
            fixture,
            case_ranking_strategy=str(config["case_ranking_strategy"]),
            case_hybrid_config=config.get("case_hybrid_config"),
            light_rag_config=config.get("light_rag_config"),
        )
        payload[label] = {
            "summary": summarize(results, fixture),
            "failures": failures(results),
        }
    return payload


def _print_comparison(payload: dict[str, Any]) -> None:
    for label in payload:
        summary = payload[label]["summary"]
        print(f"Route C case benchmark v0 ({label}): {summary['total']} cases")
        print(f"- top1_case_hit: {_format_ratio(summary['top1_case_hit'])}")
        print(f"- top3_case_hit: {_format_ratio(summary['top3_case_hit'])}")
        print(f"- mrr: {summary['mrr']}")
        print(f"- candidate_only_pass: {_format_ratio(summary['candidate_only_pass'])}")
        print(f"- source_safety_pass: {_format_ratio(summary['source_safety_pass'])}")
        print("")


def _format_ratio(value: dict[str, Any]) -> str:
    if value["rate"] is None:
        return "n/a"
    return f"{value['passed']}/{value['total']} ({value['rate']:.2%})"


if __name__ == "__main__":
    raise SystemExit(main())
