from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.retrieval.route_b_index import RouteBSearchHit, search_route_b_documents


DEFAULT_FIXTURE_PATH = REPO_ROOT / "data/eval/route_b/route_b_benchmark_v0.json"
ROUTE_B_SOURCE_ID = "data/serving_unstructured_vlm"


@dataclass(frozen=True)
class RouteBBenchmarkResult:
    case_id: str
    query_type: str
    expected_no_hit: bool
    rank: int | None
    top1_block_hit: bool
    top3_block_hit: bool
    anchor_correct: bool
    source_safety_pass: bool
    no_hit_correct: bool | None
    ranked_block_ids: tuple[str, ...]
    errors: tuple[str, ...]


def load_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


SearchFn = Callable[..., list[Any]]


def evaluate_fixture(
    fixture: dict[str, Any],
    *,
    search_fn: SearchFn = search_route_b_documents,
) -> list[RouteBBenchmarkResult]:
    source_dir = REPO_ROOT / str(fixture.get("source_dir", "data/serving_unstructured_vlm"))
    source_id = str(fixture.get("source_id", ROUTE_B_SOURCE_ID))
    return [
        evaluate_case(case, source_dir=source_dir, source_id=source_id, search_fn=search_fn)
        for case in fixture.get("cases", [])
        if isinstance(case, dict)
    ]


def evaluate_case(
    case: dict[str, Any],
    *,
    source_dir: Path,
    source_id: str,
    search_fn: SearchFn = search_route_b_documents,
) -> RouteBBenchmarkResult:
    expected = case.get("expected", {})
    case_id = str(case.get("case_id", "<missing>"))
    query_type = str(case.get("query_type", "unknown"))
    expected_no_hit = bool(expected.get("no_hit", False))
    errors: list[str] = []

    hits = search_fn(
        str(case.get("query", "")),
        source_dir=source_dir,
        source_id=source_id,
        top_k=10,
        warnings=errors,
    )
    ranked_blocks = _unique_block_ids(hits)

    if expected_no_hit:
        no_hit_correct = not hits
        if not no_hit_correct:
            errors.append(f"expected no hit, got {ranked_blocks[:3]}")
        source_safety_pass = True if not hits else _source_safety_pass(hits)
        return RouteBBenchmarkResult(
            case_id=case_id,
            query_type=query_type,
            expected_no_hit=True,
            rank=None,
            top1_block_hit=False,
            top3_block_hit=False,
            anchor_correct=True,
            source_safety_pass=source_safety_pass,
            no_hit_correct=no_hit_correct,
            ranked_block_ids=tuple(ranked_blocks),
            errors=tuple(errors),
        )

    acceptable_blocks = set(str(block_id) for block_id in expected.get("acceptable_block_ids", []))
    if not acceptable_blocks:
        errors.append("positive case missing acceptable_block_ids")
    rank = _first_rank(ranked_blocks, acceptable_blocks)
    top1_block_hit = rank == 1
    top3_block_hit = rank is not None and rank <= 3
    anchor_correct = _anchor_correct(hits, expected)
    source_safety_pass = _source_safety_pass(hits)

    if not hits:
        errors.append("no Route B hits returned")
    if not anchor_correct:
        errors.append("returned hits did not include required anchors")
    if not source_safety_pass:
        errors.append("returned hits failed Route B source-safety checks")

    return RouteBBenchmarkResult(
        case_id=case_id,
        query_type=query_type,
        expected_no_hit=False,
        rank=rank,
        top1_block_hit=top1_block_hit,
        top3_block_hit=top3_block_hit,
        anchor_correct=anchor_correct,
        source_safety_pass=source_safety_pass,
        no_hit_correct=None,
        ranked_block_ids=tuple(ranked_blocks),
        errors=tuple(errors),
    )


def summarize(results: list[RouteBBenchmarkResult]) -> dict[str, Any]:
    positive = [result for result in results if not result.expected_no_hit]
    no_hit = [result for result in results if result.expected_no_hit]
    by_type: dict[str, list[RouteBBenchmarkResult]] = defaultdict(list)
    for result in results:
        by_type[result.query_type].append(result)

    return {
        "total": len(results),
        "positive_total": len(positive),
        "no_hit_total": len(no_hit),
        "source_safety_pass": _ratio_count(results, lambda result: result.source_safety_pass),
        "anchor_correct": _ratio_count(positive, lambda result: result.anchor_correct),
        "top1_block_hit": _ratio_count(positive, lambda result: result.top1_block_hit),
        "top3_block_hit": _ratio_count(positive, lambda result: result.top3_block_hit),
        "mrr": _mrr(positive),
        "no_hit_precision": _ratio_count(no_hit, lambda result: result.no_hit_correct is True),
        "by_query_type": {
            query_type: {
                "total": len(items),
                "top1_block_hit": _ratio_count(
                    [item for item in items if not item.expected_no_hit],
                    lambda result: result.top1_block_hit,
                ),
                "top3_block_hit": _ratio_count(
                    [item for item in items if not item.expected_no_hit],
                    lambda result: result.top3_block_hit,
                ),
                "mrr": _mrr([item for item in items if not item.expected_no_hit]),
                "no_hit_precision": _ratio_count(
                    [item for item in items if item.expected_no_hit],
                    lambda result: result.no_hit_correct is True,
                ),
            }
            for query_type, items in sorted(by_type.items())
        },
    }


def failures(results: list[RouteBBenchmarkResult]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for result in results:
        metric_failed = False
        if result.expected_no_hit:
            metric_failed = result.no_hit_correct is not True
        else:
            metric_failed = not result.top3_block_hit
        if metric_failed or result.errors:
            failed.append(
                {
                    "case_id": result.case_id,
                    "query_type": result.query_type,
                    "rank": result.rank,
                    "ranked_block_ids": list(result.ranked_block_ids[:5]),
                    "errors": list(result.errors),
                }
            )
    return failed


def _unique_block_ids(hits: list[RouteBSearchHit]) -> list[str]:
    seen: set[str] = set()
    blocks: list[str] = []
    for hit in hits:
        block_id = hit.chunk.block_id
        if block_id in seen:
            continue
        seen.add(block_id)
        blocks.append(block_id)
    return blocks


def _first_rank(ranked_blocks: list[str], acceptable_blocks: set[str]) -> int | None:
    for index, block_id in enumerate(ranked_blocks, start=1):
        if block_id in acceptable_blocks:
            return index
    return None


def _anchor_correct(hits: list[RouteBSearchHit], expected: dict[str, Any]) -> bool:
    if not expected.get("must_include_anchor", False):
        return True
    return bool(hits) and all(bool(hit.chunk.anchor) for hit in hits)


def _source_safety_pass(hits: list[RouteBSearchHit]) -> bool:
    for hit in hits:
        chunk = hit.chunk
        if chunk.source_type != "serving_document":
            return False
        if not chunk.source_id.startswith(f"{ROUTE_B_SOURCE_ID}:"):
            return False
        if not chunk.serving_safe or chunk.reviewed:
            return False
    return True


def _ratio_count(results: list[RouteBBenchmarkResult], predicate) -> dict[str, float | int | None]:
    total = len(results)
    if total == 0:
        return {"passed": 0, "total": 0, "rate": None}
    passed = sum(1 for result in results if predicate(result))
    return {"passed": passed, "total": total, "rate": round(passed / total, 4)}


def _mrr(results: list[RouteBBenchmarkResult]) -> float | None:
    ranked = [result for result in results if result.rank is not None]
    if not results:
        return None
    return round(sum(1 / result.rank for result in ranked if result.rank) / len(results), 4)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Route B document retrieval benchmark v0.")
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args(argv)

    fixture_path = args.fixture if args.fixture.is_absolute() else REPO_ROOT / args.fixture
    results = evaluate_fixture(load_fixture(fixture_path))
    summary = summarize(results)
    failed = failures(results)

    if args.json:
        print(json.dumps({"summary": summary, "failures": failed}, ensure_ascii=False, indent=2))
    else:
        print(f"Route B benchmark v0: {summary['total']} cases")
        print(f"- positive cases: {summary['positive_total']}")
        print(f"- no-hit cases: {summary['no_hit_total']}")
        print(f"- source_safety_pass: {_format_ratio(summary['source_safety_pass'])}")
        print(f"- anchor_correct: {_format_ratio(summary['anchor_correct'])}")
        print(f"- top1_block_hit: {_format_ratio(summary['top1_block_hit'])}")
        print(f"- top3_block_hit: {_format_ratio(summary['top3_block_hit'])}")
        print(f"- mrr: {summary['mrr']}")
        print(f"- no_hit_precision: {_format_ratio(summary['no_hit_precision'])}")
        if failed:
            print("\nFailures / misses:")
            for item in failed:
                print(f"- {item['case_id']} ({item['query_type']}): rank={item['rank']}, top={item['ranked_block_ids']}")
                for error in item["errors"]:
                    print(f"  - {error}")

    return 0


def _format_ratio(value: dict[str, Any]) -> str:
    if value["rate"] is None:
        return "n/a"
    return f"{value['passed']}/{value['total']} ({value['rate']:.2%})"


if __name__ == "__main__":
    raise SystemExit(main())
