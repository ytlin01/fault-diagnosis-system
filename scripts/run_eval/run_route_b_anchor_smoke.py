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

from services.retrieval.route_b_index import RouteBSearchHit, search_route_b_documents


DEFAULT_FIXTURE_PATH = REPO_ROOT / "data/eval/route_b/route_b_anchor_smoke_v0.json"
ROUTE_B_SOURCE_ID = "data/serving_unstructured_vlm"


@dataclass(frozen=True)
class AnchorSmokeResult:
    case_id: str
    top1_block_hit: bool
    top3_block_hit: bool
    anchor_correct: bool
    source_safety_pass: bool
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            self.top1_block_hit
            and self.top3_block_hit
            and self.anchor_correct
            and self.source_safety_pass
            and not self.errors
        )


def load_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_fixture(fixture: dict[str, Any]) -> list[AnchorSmokeResult]:
    source_dir = REPO_ROOT / str(fixture.get("source_dir", "data/serving_unstructured_vlm"))
    source_id = str(fixture.get("source_id", ROUTE_B_SOURCE_ID))
    return [
        evaluate_case(case, source_dir=source_dir, source_id=source_id)
        for case in fixture.get("cases", [])
        if isinstance(case, dict)
    ]


def evaluate_case(case: dict[str, Any], *, source_dir: Path, source_id: str) -> AnchorSmokeResult:
    expected = case.get("expected", {})
    case_id = str(case.get("case_id", "<missing>"))
    acceptable_blocks = set(str(block_id) for block_id in expected.get("acceptable_block_ids", []))
    acceptable_types = set(str(block_type) for block_type in expected.get("acceptable_block_types", []))

    errors: list[str] = []
    hits = search_route_b_documents(
        str(case.get("query", "")),
        source_dir=source_dir,
        source_id=source_id,
        top_k=3,
        warnings=errors,
    )
    if not hits:
        errors.append("no Route B hits returned")

    top1_block_hit = bool(hits and hits[0].chunk.block_id in acceptable_blocks)
    top3_block_hit = any(hit.chunk.block_id in acceptable_blocks for hit in hits[:3])
    anchor_correct = _anchor_correct(hits, expected)
    source_safety_pass = _source_safety_pass(hits)

    if hits and acceptable_types and hits[0].chunk.block_type not in acceptable_types:
        errors.append(
            f"top1 block type `{hits[0].chunk.block_type}` not in acceptable types {sorted(acceptable_types)}"
        )
    if hits and str(expected.get("doc_id")) and hits[0].chunk.doc_id != str(expected["doc_id"]):
        errors.append(f"top1 doc_id `{hits[0].chunk.doc_id}` did not match expected `{expected['doc_id']}`")
    if not top1_block_hit:
        errors.append(_hit_error("top1", hits[:1], acceptable_blocks))
    if not top3_block_hit:
        errors.append(_hit_error("top3", hits[:3], acceptable_blocks))
    if not anchor_correct:
        errors.append("returned hits did not include required anchors")
    if not source_safety_pass:
        errors.append("returned hits failed Route B source-safety checks")

    return AnchorSmokeResult(
        case_id=case_id,
        top1_block_hit=top1_block_hit,
        top3_block_hit=top3_block_hit,
        anchor_correct=anchor_correct,
        source_safety_pass=source_safety_pass,
        errors=tuple(errors),
    )


def summarize(results: list[AnchorSmokeResult]) -> dict[str, Any]:
    total = len(results)
    return {
        "total": total,
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "source_safety_passed": sum(1 for result in results if result.source_safety_pass),
        "anchor_correct": sum(1 for result in results if result.anchor_correct),
        "top1_block_hit": sum(1 for result in results if result.top1_block_hit),
        "top3_block_hit": sum(1 for result in results if result.top3_block_hit),
    }


def _anchor_correct(hits: list[RouteBSearchHit], expected: dict[str, Any]) -> bool:
    if not expected.get("must_include_anchor", False):
        return True
    return bool(hits) and all(bool(hit.chunk.anchor) for hit in hits)


def _source_safety_pass(hits: list[RouteBSearchHit]) -> bool:
    if not hits:
        return False
    for hit in hits:
        chunk = hit.chunk
        if chunk.source_type != "serving_document":
            return False
        if not chunk.source_id.startswith(f"{ROUTE_B_SOURCE_ID}:"):
            return False
        if not chunk.serving_safe or chunk.reviewed:
            return False
    return True


def _hit_error(label: str, hits: list[RouteBSearchHit], acceptable_blocks: set[str]) -> str:
    actual = [hit.chunk.block_id for hit in hits]
    return f"{label} block hit failed; expected one of {sorted(acceptable_blocks)}, got {actual}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TASK-016 Route B anchor smoke checks.")
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args(argv)

    fixture_path = args.fixture if args.fixture.is_absolute() else REPO_ROOT / args.fixture
    results = evaluate_fixture(load_fixture(fixture_path))
    summary = summarize(results)
    failures = [
        {"case_id": result.case_id, "errors": list(result.errors)}
        for result in results
        if not result.passed
    ]

    if args.json:
        print(json.dumps({"summary": summary, "failures": failures}, ensure_ascii=False, indent=2))
    else:
        print(f"Route B anchor smoke: {summary['passed']}/{summary['total']} passed")
        print(f"- source_safety_passed: {summary['source_safety_passed']}/{summary['total']}")
        print(f"- anchor_correct: {summary['anchor_correct']}/{summary['total']}")
        print(f"- top1_block_hit: {summary['top1_block_hit']}/{summary['total']}")
        print(f"- top3_block_hit: {summary['top3_block_hit']}/{summary['total']}")
        for failure in failures:
            print(f"\n{failure['case_id']}")
            for error in failure["errors"]:
                print(f"  - {error}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
