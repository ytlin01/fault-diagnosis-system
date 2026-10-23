"""TASK-029B: Route B/C answer-level safety evaluation.

Verifies that the unified assembler enforces evidence-only and candidate-only
boundaries across all serving-safe fixtures. No live LLM calls are made.

Constraint sources:
  Route B — TASK-025 acceptance: evidence_only, no confirmed_diagnosis
  Route C — TASK-026/028 acceptance: candidate-only, no reviewed escalation
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from services.providers.llm import StubProvider
from services.reasoning.unified_answer_assembler import fixture_route_output, synthesize_route_output
from services.routing.query_router import CASE_RETRIEVAL, DOCUMENT_EVIDENCE_RETRIEVAL

# Banned phrases per TASK-029B brief — must never appear in any assembled output.
_ROUTE_A_SOURCE_TYPES = frozenset({
    "reviewed_structured_chain",
    "reviewed_asset_graph",
})
_CONFIRMATORY_PHRASES = (
    "confirmed_diagnosis",
    "confirmed diagnosis",
    '"status": "reviewed"',
    "root cause is",
    "diagnosis is",
    "verified diagnosis",
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_fixtures(route_name: str) -> dict[str, Any]:
    path = _REPO_ROOT / "data/eval" / route_name / f"{route_name}_serving_safe_fixtures_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _get_fixture(route_name: str, fixture_id: str) -> dict[str, Any]:
    payload = _load_fixtures(route_name)
    for item in payload["fixtures"]:
        if item["fixture_id"] == fixture_id:
            return item
    raise AssertionError(f"fixture not found: {fixture_id} in {route_name}")


def _assemble(fixture: dict[str, Any], route: str) -> dict[str, Any]:
    route_output = fixture_route_output(fixture)
    return synthesize_route_output(
        fixture["input"]["query_text"],
        route,
        route_output,
        provider=StubProvider(),
    )


def _dump(conclusion: dict[str, Any]) -> str:
    return json.dumps(conclusion, ensure_ascii=False)


# ── Route B: evidence-only safety ────────────────────────────────────────────

class RouteBEvidenceOnlySafetyTests(unittest.TestCase):

    def _assert_no_confirmatory_language(self, conclusion: dict[str, Any]) -> None:
        text = _dump(conclusion)
        for phrase in _CONFIRMATORY_PHRASES:
            self.assertNotIn(phrase, text, f"confirmatory phrase found: {phrase!r}")

    def _assert_confidence_never_high(self, conclusion: dict[str, Any]) -> None:
        for result in conclusion.get("diagnosis_results", []):
            self.assertNotEqual(result.get("confidence"), "high",
                                "Route B must never produce confidence=high")

    def _assert_no_route_a_source_types(self, conclusion: dict[str, Any]) -> None:
        text = _dump(conclusion)
        for source_type in _ROUTE_A_SOURCE_TYPES:
            self.assertNotIn(source_type, text,
                             f"Route A source type leaked into Route B output: {source_type!r}")

    def _assert_evidence_type_document_snippet(self, conclusion: dict[str, Any]) -> None:
        for result in conclusion.get("diagnosis_results", []):
            for ev in result.get("evidence", []):
                self.assertEqual(ev.get("evidence_type"), "document_snippet",
                                 "Route B evidence_type must be document_snippet")

    def _assert_boundary_warning_present(self, conclusion: dict[str, Any]) -> None:
        warnings_text = " ".join(conclusion.get("warnings", []))
        self.assertIn("evidence_only", warnings_text,
                      "Route B boundary warning (evidence_only) must be present in warnings")

    # ── RB-SAFE-001: normal document evidence hit ─────────────────────────────

    def test_rb_safe_001_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-001"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    def test_rb_safe_001_evidence_type_document_snippet(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-001"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_evidence_type_document_snippet(conclusion)

    def test_rb_safe_001_confidence_not_high(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-001"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_confidence_never_high(conclusion)

    def test_rb_safe_001_no_route_a_source_types(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-001"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_no_route_a_source_types(conclusion)

    def test_rb_safe_001_boundary_warning_present(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-001"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_boundary_warning_present(conclusion)

    def test_rb_safe_001_possible_cause_null(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-001"), DOCUMENT_EVIDENCE_RETRIEVAL)
        for result in conclusion["diagnosis_results"]:
            self.assertIsNone(result.get("possible_cause"),
                              "Route B must not set possible_cause")

    # ── RB-SAFE-003: graphrag evidence-only ───────────────────────────────────

    def test_rb_safe_003_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-003"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    def test_rb_safe_003_evidence_type_document_snippet(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-003"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_evidence_type_document_snippet(conclusion)

    def test_rb_safe_003_confidence_not_high(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-003"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_confidence_never_high(conclusion)

    def test_rb_safe_003_no_route_a_source_types(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-003"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_no_route_a_source_types(conclusion)

    # ── RB-SAFE-002 / RB-SAFE-004: no-hit / blocked sources ──────────────────

    def test_rb_safe_002_no_hit_returns_empty_results(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-002"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self.assertEqual(conclusion["diagnosis_results"], [])
        self.assertTrue(conclusion["warnings"], "no-hit must produce warnings")

    def test_rb_safe_002_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-002"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    def test_rb_safe_004_blocked_source_returns_empty_results(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-004"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self.assertEqual(conclusion["diagnosis_results"], [])
        self.assertTrue(conclusion["warnings"], "source-safety negative must produce warnings")

    def test_rb_safe_004_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_b", "RB-SAFE-004"), DOCUMENT_EVIDENCE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    # ── Cross-fixture: root_cause_actions always empty ────────────────────────

    def test_rb_all_fixtures_root_cause_actions_empty(self) -> None:
        payload = _load_fixtures("route_b")
        for fixture in payload["fixtures"]:
            conclusion = _assemble(fixture, DOCUMENT_EVIDENCE_RETRIEVAL)
            self.assertEqual(conclusion["root_cause_actions"], [],
                             f"{fixture['fixture_id']}: root_cause_actions must be []")


# ── Route C: candidate-only safety ───────────────────────────────────────────

class RouteCCandidateOnlySafetyTests(unittest.TestCase):

    def _assert_no_confirmatory_language(self, conclusion: dict[str, Any]) -> None:
        text = _dump(conclusion)
        for phrase in _CONFIRMATORY_PHRASES:
            self.assertNotIn(phrase, text, f"confirmatory phrase found: {phrase!r}")

    def _assert_confidence_never_high(self, conclusion: dict[str, Any]) -> None:
        for result in conclusion.get("diagnosis_results", []):
            self.assertNotEqual(result.get("confidence"), "high",
                                "Route C must never produce confidence=high")

    def _assert_no_route_a_source_types(self, conclusion: dict[str, Any]) -> None:
        text = _dump(conclusion)
        for source_type in _ROUTE_A_SOURCE_TYPES:
            self.assertNotIn(source_type, text,
                             f"Route A source type leaked into Route C output: {source_type!r}")

    def _assert_evidence_type_case_or_catalog(self, conclusion: dict[str, Any]) -> None:
        for result in conclusion.get("diagnosis_results", []):
            for ev in result.get("evidence", []):
                self.assertIn(ev.get("evidence_type"), {"related_case", "structured_catalog"},
                              "Route C evidence_type must be related_case or structured_catalog")

    def _assert_boundary_warning_present(self, conclusion: dict[str, Any]) -> None:
        warnings_text = " ".join(conclusion.get("warnings", []))
        self.assertIn("candidate", warnings_text,
                      "Route C boundary warning (candidate) must be present in warnings")

    # ── RC-SAFE-001: normal case reference hit ────────────────────────────────

    def test_rc_safe_001_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-001"), CASE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    def test_rc_safe_001_evidence_type_related_case(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-001"), CASE_RETRIEVAL)
        self._assert_evidence_type_case_or_catalog(conclusion)

    def test_rc_safe_001_confidence_not_high(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-001"), CASE_RETRIEVAL)
        self._assert_confidence_never_high(conclusion)

    def test_rc_safe_001_no_route_a_source_types(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-001"), CASE_RETRIEVAL)
        self._assert_no_route_a_source_types(conclusion)

    def test_rc_safe_001_boundary_warning_present(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-001"), CASE_RETRIEVAL)
        self._assert_boundary_warning_present(conclusion)

    def test_rc_safe_001_possible_cause_null(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-001"), CASE_RETRIEVAL)
        for result in conclusion["diagnosis_results"]:
            self.assertIsNone(result.get("possible_cause"),
                              "Route C must not set possible_cause")

    # ── RC-SAFE-003: hard case ────────────────────────────────────────────────

    def test_rc_safe_003_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-003"), CASE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    def test_rc_safe_003_evidence_type_related_case(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-003"), CASE_RETRIEVAL)
        self._assert_evidence_type_case_or_catalog(conclusion)

    def test_rc_safe_003_confidence_not_high(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-003"), CASE_RETRIEVAL)
        self._assert_confidence_never_high(conclusion)

    def test_rc_safe_003_no_route_a_source_types(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-003"), CASE_RETRIEVAL)
        self._assert_no_route_a_source_types(conclusion)

    # ── RC-SAFE-004: candidate-only safety ───────────────────────────────────

    def test_rc_safe_004_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-004"), CASE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    def test_rc_safe_004_confidence_not_high(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-004"), CASE_RETRIEVAL)
        self._assert_confidence_never_high(conclusion)

    def test_rc_safe_004_no_route_a_source_types(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-004"), CASE_RETRIEVAL)
        self._assert_no_route_a_source_types(conclusion)

    def test_rc_safe_004_boundary_warning_present(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-004"), CASE_RETRIEVAL)
        self._assert_boundary_warning_present(conclusion)

    # ── RC-SAFE-002: no-hit ───────────────────────────────────────────────────

    def test_rc_safe_002_no_hit_returns_empty_results(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-002"), CASE_RETRIEVAL)
        self.assertEqual(conclusion["diagnosis_results"], [])
        self.assertTrue(conclusion["warnings"], "no-hit must produce warnings")

    def test_rc_safe_002_no_confirmatory_language(self) -> None:
        conclusion = _assemble(_get_fixture("route_c", "RC-SAFE-002"), CASE_RETRIEVAL)
        self._assert_no_confirmatory_language(conclusion)

    # ── Cross-fixture: root_cause_actions always empty ────────────────────────

    def test_rc_all_fixtures_root_cause_actions_empty(self) -> None:
        payload = _load_fixtures("route_c")
        for fixture in payload["fixtures"]:
            conclusion = _assemble(fixture, CASE_RETRIEVAL)
            self.assertEqual(conclusion["root_cause_actions"], [],
                             f"{fixture['fixture_id']}: root_cause_actions must be []")

    def test_rc_all_fixtures_possible_cause_null(self) -> None:
        payload = _load_fixtures("route_c")
        for fixture in payload["fixtures"]:
            conclusion = _assemble(fixture, CASE_RETRIEVAL)
            for result in conclusion.get("diagnosis_results", []):
                self.assertIsNone(result.get("possible_cause"),
                                  f"{fixture['fixture_id']}: possible_cause must be null")


if __name__ == "__main__":
    unittest.main()
