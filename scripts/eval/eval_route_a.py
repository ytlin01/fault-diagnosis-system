"""Route A (text2cypher) + KG triples quality evaluation script.

Runs two evaluations and combines them into a single report:

  1. Scenario eval  — reads golden_set.json, calls execute_text2cypher() for
                      each case, checks results against expected keys/counts.

  2. Triples audit  — queries Neo4j directly to check graph structural
                      integrity, chain completeness, and cross-layer coverage.

Usage
-----
    python scripts/eval/eval_route_a.py
    python scripts/eval/eval_route_a.py --skip-audit        # scenarios only
    python scripts/eval/eval_route_a.py --skip-scenarios    # audit only
    python scripts/eval/eval_route_a.py --golden data/eval/route_a/golden_set.json
    python scripts/eval/eval_route_a.py --output data/eval/route_a/eval_report.json

Requirements
------------
- Neo4j running and FAULTDX_NEO4J_* env vars set (or .env at repo root)
- data/eval/route_a/golden_set.json populated with real node IDs
  (only needed for scenario eval; audit runs without it)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.graph.neo4j_client import NEO4J_DATABASE, NEO4J_HOST, NEO4J_PASSWORD, NEO4J_USER, make_driver
from services.retrieval.route_a_executor import execute_text2cypher
from services.graph.text2cypher.templates import INTENT_HIERARCHY, VALID_INTENTS
from services.evaluation.route_a_static_coverage import StaticCoverageInputError, evaluate_static_coverage
from services.evaluation.route_a_blind import build_review_key, load_query_bank, run_query_bank_ollama

DEFAULT_GOLDEN_PATH = REPO_ROOT / "data/eval/route_a/golden_set.json"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data/eval/route_a/scenario_registry.json"


# ---------------------------------------------------------------------------
# Scenario evaluation
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    scenario_id: str
    scenario_tag: str
    nl_query: str
    intent: str
    passed: bool
    failure_reason: str = ""
    item_count: int = 0
    warnings: list[str] = field(default_factory=list)


def load_golden(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"ERROR: golden_set.json not found at {path}", file=sys.stderr)
        print(
            "Create it with real Neo4j node IDs.\n"
            "See data/eval/route_a/golden_set.json for the expected format.",
            file=sys.stderr,
        )
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    entries = json.loads(path.read_text(encoding="utf-8"))
    return {e["scenario_id"]: e for e in entries if e.get("scenario_id")}


def _build_canonical_state(override: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "query": {"text": "", "normalized_text": "", "language": "zh-CN", "received_at": ""},
        "entities": {
            "asset": {
                "station":      {"raw": None, "canonical": None, "confidence": "unknown"},
                "module":       {"raw": None, "canonical": None, "confidence": "unknown"},
                "component":    {"raw": None, "canonical": None, "confidence": "unknown"},
                "subcomponent": {"raw": None, "canonical": None, "confidence": "unknown"},
            },
            "diagnostic": {
                "error_code": {"raw": None, "canonical": None, "confidence": "unknown"},
                "fault":      {"raw": None, "canonical": None, "confidence": "unknown"},
            },
            "observation": {},
        },
    }
    for group, slots in override.get("entities", {}).items():
        if isinstance(slots, dict):
            state["entities"].setdefault(group, {})
            for slot_name, slot_val in slots.items():
                state["entities"][group][slot_name] = slot_val
    return state


def _resolve_intent(case: dict[str, Any]) -> str:
    intent = str(case.get("expected_intent", INTENT_HIERARCHY))
    return intent if intent in VALID_INTENTS else INTENT_HIERARCHY


def _should_skip(case: dict[str, Any]) -> bool:
    """Skip data_gap cases whose REPLACE_WITH_* placeholders were never filled."""
    if not case.get("skip_if_no_data"):
        return False
    return "REPLACE_WITH_" in str(case.get("canonical_state_override", {}))


def evaluate_case(case: dict[str, Any]) -> CaseResult:
    scenario_id = str(case.get("scenario_id", "?"))
    scenario_tag = str(case.get("scenario_tag", "unknown"))
    nl_query = str(case.get("nl_query", ""))
    intent = _resolve_intent(case)
    expected_node_id = case.get("expected_node_id")
    expected_result_keys = list(case.get("expected_result_keys", []))
    min_result_count = int(case.get("min_result_count", 1))

    canonical_state = _build_canonical_state(case.get("canonical_state_override", {}))

    try:
        output = execute_text2cypher(canonical_state, intent=intent)
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            scenario_id=scenario_id, scenario_tag=scenario_tag,
            nl_query=nl_query, intent=intent, passed=False,
            failure_reason=f"execute_text2cypher raised: {exc}",
        )

    warnings = list(output.get("warnings", []))
    items = list(output.get("items", []))

    # min_result_count=0 → expects empty/warning response; treat as pass
    if min_result_count == 0:
        return CaseResult(
            scenario_id=scenario_id, scenario_tag=scenario_tag,
            nl_query=nl_query, intent=intent, passed=True,
            item_count=len(items), warnings=warnings,
        )

    if warnings and not items:
        return CaseResult(
            scenario_id=scenario_id, scenario_tag=scenario_tag,
            nl_query=nl_query, intent=intent, passed=False,
            failure_reason=f"executor returned warning: {warnings[0]!r}",
            item_count=0, warnings=warnings,
        )

    if len(items) < min_result_count:
        return CaseResult(
            scenario_id=scenario_id, scenario_tag=scenario_tag,
            nl_query=nl_query, intent=intent, passed=False,
            failure_reason=f"expected ≥{min_result_count} items, got {len(items)}",
            item_count=len(items), warnings=warnings,
        )

    for key in expected_result_keys:
        if not any(key in item for item in items):
            return CaseResult(
                scenario_id=scenario_id, scenario_tag=scenario_tag,
                nl_query=nl_query, intent=intent, passed=False,
                failure_reason=f"expected_result_key {key!r} not found in any item",
                item_count=len(items), warnings=warnings,
            )

    if expected_node_id:
        if not any(
            str(v) == str(expected_node_id)
            for item in items
            for v in _flatten_values(item)
        ):
            return CaseResult(
                scenario_id=scenario_id, scenario_tag=scenario_tag,
                nl_query=nl_query, intent=intent, passed=False,
                failure_reason=f"expected_node_id {expected_node_id!r} not found in items",
                item_count=len(items), warnings=warnings,
            )

    return CaseResult(
        scenario_id=scenario_id, scenario_tag=scenario_tag,
        nl_query=nl_query, intent=intent, passed=True,
        item_count=len(items), warnings=warnings,
    )


def _flatten_values(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        result: list[str] = []
        for v in obj.values():
            result.extend(_flatten_values(v))
        return result
    if isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(_flatten_values(item))
        return result
    return [str(obj)] if obj is not None else []


def build_scenario_report(
    results: list[CaseResult],
    *,
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    per_tag: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0})
    gaps: list[dict[str, str]] = []

    for r in results:
        per_tag[r.scenario_tag]["pass" if r.passed else "fail"] += 1
        if not r.passed:
            gaps.append({
                "scenario_id": r.scenario_id,
                "scenario_tag": r.scenario_tag,
                "failure_reason": r.failure_reason,
            })

    registry_gaps = []
    if registry:
        for sid, entry in registry.items():
            if entry.get("data_gap") or entry.get("template_gap"):
                registry_gaps.append({
                    "scenario_id": sid,
                    "scenario_tag": entry.get("scenario_tag"),
                    "data_gap": bool(entry.get("data_gap")),
                    "template_gap": bool(entry.get("template_gap")),
                    "notes": entry.get("notes", ""),
                })

    return {
        "overall": {
            "pass": passed,
            "total": total,
            "coverage_pct": round(100 * passed / total, 1) if total else 0.0,
        },
        "per_tag": {tag: counts for tag, counts in sorted(per_tag.items())},
        "gaps": gaps,
        "registry_gap_scenarios": registry_gaps,
        "per_case": [
            {
                "scenario_id": r.scenario_id,
                "scenario_tag": r.scenario_tag,
                "passed": r.passed,
                "item_count": r.item_count,
                "failure_reason": r.failure_reason,
                "warnings": r.warnings,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# Triples audit
# ---------------------------------------------------------------------------

# Each audit check: (check_id, description, cypher, pass_condition)
# pass_condition is a lambda(result_dict) -> bool
# result_dict is the first row returned, or {} if no rows.

_AUDIT_CHECKS: list[tuple[str, str, str, Any]] = [

    # ── Node counts (informational, always pass) ──────────────────────────
    ("A01", "Node inventory: Station count",
     "MATCH (n:Station) RETURN count(n) AS value",
     lambda r: True),

    ("A02", "Node inventory: Module count",
     "MATCH (n:Module) RETURN count(n) AS value",
     lambda r: True),

    ("A03", "Node inventory: Component count",
     "MATCH (n:Component) RETURN count(n) AS value",
     lambda r: True),

    ("A04", "Node inventory: SubComponent count",
     "MATCH (n:SubComponent) RETURN count(n) AS value",
     lambda r: True),

    ("A05", "Node inventory: ErrorCode count",
     "MATCH (n:ErrorCode) RETURN count(n) AS value",
     lambda r: True),

    ("A06", "Node inventory: Fault count",
     "MATCH (n:Fault) RETURN count(n) AS value",
     lambda r: True),

    ("A07", "Node inventory: Cause count",
     "MATCH (n:Cause) RETURN count(n) AS value",
     lambda r: True),

    ("A08", "Node inventory: Action count",
     "MATCH (n:Action) RETURN count(n) AS value",
     lambda r: True),

    ("A09", "Node inventory: ActionStep count",
     "MATCH (n:ActionStep) RETURN count(n) AS value",
     lambda r: True),

    # ── Structural integrity ──────────────────────────────────────────────
    ("B01", "Integrity: Modules with no parent Station",
     "MATCH (m:Module) WHERE NOT ()-[:HAS_MODULE]->(m) RETURN count(m) AS value",
     lambda r: r.get("value", 0) == 0),

    ("B02", "Integrity: Components with no parent Module",
     "MATCH (c:Component) WHERE NOT ()-[:HAS_COMPONENT]->(c) RETURN count(c) AS value",
     lambda r: r.get("value", 0) == 0),

    ("B03", "Integrity: SubComponents with no parent Component or SubComponent",
     "MATCH (sc:SubComponent) WHERE NOT ()-[:HAS_SUBCOMPONENT]->(sc) RETURN count(sc) AS value",
     lambda r: r.get("value", 0) == 0),

    ("B04", "Integrity: Faults unreachable from any asset or ErrorCode",
     """MATCH (f:Fault)
        WHERE NOT ()-[:INDICATES]->(f) AND NOT ()-[:TRIGGERS]->(f)
        RETURN count(f) AS value""",
     lambda r: True),  # informational — may be non-zero while data is sparse

    ("B05", "Integrity: Causes with no parent Fault",
     "MATCH (ca:Cause) WHERE NOT ()-[:HAS_CAUSE]->(ca) RETURN count(ca) AS value",
     lambda r: r.get("value", 0) == 0),

    ("B06", "Integrity: Actions with no parent Cause",
     "MATCH (act:Action) WHERE NOT ()-[:RESOLVED_BY]->(act) RETURN count(act) AS value",
     lambda r: r.get("value", 0) == 0),

    ("B07", "Integrity: ActionSteps with no parent Action",
     "MATCH (s:ActionStep) WHERE NOT ()-[:HAS_STEP]->(s) RETURN count(s) AS value",
     lambda r: r.get("value", 0) == 0),

    # ── Diagnostic chain completeness ─────────────────────────────────────
    ("C01", "Completeness: Faults with no HAS_CAUSE edge",
     "MATCH (f:Fault) WHERE NOT (f)-[:HAS_CAUSE]->() RETURN count(f) AS value",
     lambda r: True),  # informational

    ("C02", "Completeness: Causes with no RESOLVED_BY edge",
     "MATCH (ca:Cause) WHERE NOT (ca)-[:RESOLVED_BY]->() RETURN count(ca) AS value",
     lambda r: True),  # informational

    ("C03", "Completeness: Actions with no HAS_STEP edge",
     "MATCH (act:Action) WHERE NOT (act)-[:HAS_STEP]->() RETURN count(act) AS value",
     lambda r: True),  # informational

    ("C04", "Completeness: ErrorCodes with full chain (→Fault→Cause→Action→Step)",
     """MATCH (ec:ErrorCode)-[:INDICATES]->(f:Fault)-[:HAS_CAUSE]->(ca:Cause)
              -[:RESOLVED_BY]->(act:Action)-[:HAS_STEP]->(s:ActionStep)
        RETURN count(distinct ec) AS value""",
     lambda r: True),  # informational — higher is better

    ("C05", "Completeness: ErrorCodes with at least INDICATES→Fault",
     "MATCH (ec:ErrorCode)-[:INDICATES]->(f:Fault) RETURN count(distinct ec) AS value",
     lambda r: True),

    # ── Property completeness ─────────────────────────────────────────────
    # Checks whether the properties used by templates and returned in results
    # are actually populated. Pass = zero missing; informational = always pass.

    ("E01", "Property: Component nodes missing name",
     "MATCH (c:Component) WHERE c.name IS NULL OR c.name = '' RETURN count(c) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E02", "Property: Component nodes missing description (CAD nodes expected)",
     "MATCH (c:Component) WHERE c.description IS NULL OR c.description = '' RETURN count(c) AS value",
     lambda r: True),  # informational — CAD-derived nodes have no description by design

    ("E03", "Property: Fault nodes missing name",
     "MATCH (f:Fault) WHERE f.name IS NULL OR f.name = '' RETURN count(f) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E04", "Property: Fault nodes missing description",
     "MATCH (f:Fault) WHERE f.description IS NULL OR f.description = '' RETURN count(f) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E05", "Property: Cause nodes missing description",
     "MATCH (ca:Cause) WHERE ca.description IS NULL OR ca.description = '' RETURN count(ca) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E06", "Property: Action nodes missing action_name",
     "MATCH (act:Action) WHERE act.action_name IS NULL OR act.action_name = '' RETURN count(act) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E07", "Property: ActionStep nodes missing instruction",
     "MATCH (s:ActionStep) WHERE s.instruction IS NULL OR s.instruction = '' RETURN count(s) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E08", "Property: ActionStep nodes missing order",
     "MATCH (s:ActionStep) WHERE s.order IS NULL RETURN count(s) AS value",
     lambda r: r.get("value", 0) == 0),

    ("E09", "Property: ActionStep nodes missing expected_result (known gap)",
     "MATCH (s:ActionStep) WHERE s.expected_result IS NULL OR s.expected_result = '' RETURN count(s) AS value",
     lambda r: True),  # informational — field was never populated

    # ── Cross-layer coverage ──────────────────────────────────────────────
    ("D01", "Coverage: Components with TRIGGERS edges",
     "MATCH (c:Component)-[:TRIGGERS]->(f:Fault) RETURN count(distinct c) AS value",
     lambda r: True),  # informational — track over time

    ("D02", "Coverage: Total components (denominator for D01)",
     "MATCH (c:Component) RETURN count(c) AS value",
     lambda r: True),

    ("D03", "Coverage: Faults reachable from asset layer via TRIGGERS",
     "MATCH ()-[:TRIGGERS]->(f:Fault) RETURN count(distinct f) AS value",
     lambda r: True),

    ("D04", "Coverage: Total faults (denominator for D03)",
     "MATCH (f:Fault) RETURN count(f) AS value",
     lambda r: True),

    # ── Content quality (ISO 8000 / W3C DQV aligned) ─────────────────────
    # Five standard KG quality dimensions: Conciseness, Consistency,
    # Validity, Completeness (contextual), Timeliness.
    # All rate-based metrics (%) so results are comparable across data loads.
    # Reference: Zaveri et al. (2016) "Quality Assessment for Linked Data".

    # --- Dimension 1: Conciseness — no redundant entities or relationships ---
    # Entity uniqueness: duplicate-free instances / total instances
    ("F01", "Conciseness: Fault entity uniqueness rate (%)",
     """MATCH (f:Fault)
        WITH count(f) AS total, count(distinct f.name) AS uniq
        RETURN round(100.0 * uniq / total, 1) AS value""",
     lambda r: r.get("value", 0.0) >= 100.0),

    ("F02", "Conciseness: ErrorCode entity uniqueness rate (%)",
     """MATCH (ec:ErrorCode)
        WITH count(ec) AS total, count(distinct ec.code_id) AS uniq
        RETURN round(100.0 * uniq / total, 1) AS value""",
     lambda r: r.get("value", 0.0) >= 100.0),

    # Relationship uniqueness: duplicate triples (same subject-predicate-object)
    ("F03", "Conciseness: Duplicate INDICATES triples",
     """MATCH (ec:ErrorCode)-[:INDICATES]->(f:Fault)
        WITH ec, f, count(*) AS c WHERE c > 1
        RETURN count(*) AS value""",
     lambda r: r.get("value", 0) == 0),

    ("F04", "Conciseness: Duplicate TRIGGERS triples",
     """MATCH (c:Component)-[:TRIGGERS]->(f:Fault)
        WITH c, f, count(*) AS c2 WHERE c2 > 1
        RETURN count(*) AS value""",
     lambda r: r.get("value", 0) == 0),

    # --- Dimension 2: Consistency — schema and constraint adherence ---
    # Cardinality: ErrorCode→Fault is 1:1 by schema design
    ("F05", "Consistency: ErrorCode 1:1 INDICATES cardinality violations",
     """MATCH (ec:ErrorCode)-[:INDICATES]->(f:Fault)
        WITH ec, count(f) AS n WHERE n > 1
        RETURN count(ec) AS value""",
     lambda r: r.get("value", 0) == 0),

    # Type consistency: no node should carry conflicting schema labels
    ("F06", "Consistency: Multi-label type conflicts",
     """MATCH (n) WHERE size(labels(n)) > 1
        AND any(l IN labels(n) WHERE l IN
            ['Station','Module','Component','SubComponent',
             'ErrorCode','Fault','Cause','Action','ActionStep'])
        RETURN count(n) AS value""",
     lambda r: r.get("value", 0) == 0),

    # Referential integrity: relationships point to existing typed nodes
    # (orphan checks are in B category; here we check direction consistency)
    ("F07", "Consistency: HAS_CAUSE edges pointing to non-Cause nodes",
     """MATCH (f:Fault)-[:HAS_CAUSE]->(n) WHERE NOT n:Cause
        RETURN count(n) AS value""",
     lambda r: r.get("value", 0) == 0),

    # --- Dimension 3: Validity — format and domain conformance ---
    # Syntactic validity: ID values match expected naming pattern
    ("F08", "Validity: ErrorCode ID format conformance rate (%)",
     """MATCH (ec:ErrorCode)
        WITH count(ec) AS total,
             count(CASE WHEN ec.code_id =~ '[A-Z][0-9]{2}[A-Z0-9]{4,5}-[0-9]{2}-[0-9]{2}' THEN 1 END) AS conforming
        RETURN round(100.0 * conforming / total, 1) AS value""",
     lambda r: True),  # informational — pattern may evolve

    # Domain validity: severity restricted to expected value set
    ("F09", "Validity: Fault severity domain validity rate (%)",
     """MATCH (f:Fault)
        WITH count(f) AS total,
             count(CASE WHEN f.severity IN ['low','medium','high','critical'] THEN 1 END) AS valid
        RETURN round(100.0 * valid / total, 1) AS value""",
     lambda r: r.get("value", 0.0) >= 100.0),

    # --- Dimension 4: Completeness (contextual) — property fill rate ---
    # Schema-level completeness: % of expected properties populated per node type.
    # Expressed as average fill rate across all diagnostic node properties.
    ("F10", "Completeness: Diagnostic node average property fill rate (%)",
     """MATCH (n) WHERE (n:Fault OR n:Cause OR n:Action OR n:ActionStep)
        WITH n, [k IN keys(n) WHERE n[k] IS NOT NULL AND n[k] <> ''] AS filled,
             keys(n) AS all_keys
        WITH avg(100.0 * size(filled) / CASE size(all_keys) WHEN 0 THEN 1 ELSE size(all_keys) END) AS avg_fill
        RETURN round(avg_fill, 1) AS value""",
     lambda r: r.get("value", 0.0) >= 80.0),  # 80% threshold

    # --- Dimension 5: Timeliness — currency and review status ---
    # Validated rate: % of diagnostic nodes marked as reviewed/validated.
    # Tracks data currency as expert review progresses.
    ("F11", "Timeliness: Validated diagnostic nodes (numerator)",
     """MATCH (n) WHERE (n:ErrorCode OR n:Fault OR n:Cause OR n:Action OR n:ActionStep)
        AND n.validated = true RETURN count(n) AS value""",
     lambda r: True),

    ("F12", "Timeliness: Total diagnostic nodes (denominator for F11)",
     """MATCH (n) WHERE (n:ErrorCode OR n:Fault OR n:Cause OR n:Action OR n:ActionStep)
        RETURN count(n) AS value""",
     lambda r: True),
]


@dataclass
class AuditResult:
    check_id: str
    description: str
    value: Any
    passed: bool
    error: str = ""


def run_triples_audit() -> list[AuditResult]:
    """Run all audit checks against Neo4j. Returns results even if some checks fail."""
    results: list[AuditResult] = []
    try:
        driver = make_driver(NEO4J_HOST, NEO4J_USER, NEO4J_PASSWORD)
    except Exception as exc:  # noqa: BLE001
        return [AuditResult("CONN", "Neo4j connectivity", None, False, str(exc))]

    with driver:
        for check_id, description, cypher, pass_condition in _AUDIT_CHECKS:
            try:
                with driver.session(database=NEO4J_DATABASE) as session:
                    rows = [dict(r) for r in session.run(cypher)]
                row = rows[0] if rows else {}
                value = row.get("value")
                passed = bool(pass_condition(row))
                results.append(AuditResult(check_id, description, value, passed))
            except Exception as exc:  # noqa: BLE001
                results.append(AuditResult(check_id, description, None, False, str(exc)))

    return results


def build_content_quality_metrics(results: list[AuditResult]) -> dict[str, Any]:
    """Derive ISO 8000 / W3C DQV aligned content quality 指标 from F-category results.

    Dimensions: Conciseness, Consistency, Validity, Completeness, Timeliness.
    Reference: Zaveri et al. (2016) "Quality Assessment for Linked Data".
    """
    by_id = {r.check_id: r for r in results}

    def _val(check_id: str) -> Any:
        r = by_id.get(check_id)
        return r.value if r and r.value is not None else 0

    def _pct(num: float, denom: float) -> float:
        return round(100.0 * num / denom, 1) if denom else 0.0

    validated   = _val("F11")
    diag_total  = _val("F12")

    return {
        # -- Conciseness --
        "conciseness": {
            "fault_entity_uniqueness_pct":    _val("F01"),   # 100% = no duplicate fault names
            "error_code_entity_uniqueness_pct": _val("F02"), # 100% = no duplicate code_ids
            "duplicate_indicates_triples":    _val("F03"),   # 0 = clean
            "duplicate_triggers_triples":     _val("F04"),   # 0 = clean
        },
        # -- Consistency --
        "consistency": {
            "errorcode_cardinality_violations": _val("F05"), # 0 = all 1:1
            "multi_label_type_conflicts":     _val("F06"),   # 0 = clean
            "has_cause_type_violations":      _val("F07"),   # 0 = clean
        },
        # -- Validity --
        "validity": {
            "error_code_format_conformance_pct": _val("F08"),  # % matching ID pattern
            "fault_severity_domain_validity_pct": _val("F09"), # % in {low,medium,high,critical}
        },
        # -- Completeness (contextual) --
        "completeness": {
            "diagnostic_avg_property_fill_pct": _val("F10"),  # avg fill rate across diag nodes
        },
        # -- Timeliness --
        "timeliness": {
            "validated_count":  validated,
            "validated_total":  diag_total,
            "validated_pct":    _pct(validated, diag_total),  # % marked reviewed
        },
        # Raw failure list for downstream consumers
        "dimension_failures": [
            r.check_id for r in results
            if r.check_id.startswith("F") and not r.passed and not r.error
        ],
    }


def build_audit_report(results: list[AuditResult]) -> dict[str, Any]:
    checks = []
    for r in results:
        checks.append({
            "check_id": r.check_id,
            "description": r.description,
            "value": r.value,
            "passed": r.passed,
            "error": r.error,
        })

    # Derive cross-layer coverage ratio from D01/D02 and D03/D04
    by_id = {r.check_id: r for r in results}
    triggers_components = (by_id["D01"].value or 0) if "D01" in by_id else 0
    total_components = (by_id["D02"].value or 0) if "D02" in by_id else 0
    triggers_faults = (by_id["D03"].value or 0) if "D03" in by_id else 0
    total_faults = (by_id["D04"].value or 0) if "D04" in by_id else 0

    cross_layer = {
        "triggers_components": triggers_components,
        "total_components": total_components,
        "component_coverage_pct": (
            round(100 * triggers_components / total_components, 1)
            if total_components else 0.0
        ),
        "faults_reachable_from_asset": triggers_faults,
        "total_faults": total_faults,
        "fault_reachability_pct": (
            round(100 * triggers_faults / total_faults, 1)
            if total_faults else 0.0
        ),
    }

    integrity_failures = [
        c for c in checks
        if c["check_id"].startswith("B") and not c["passed"] and not c["error"]
    ]

    property_failures = [
        c for c in checks
        if c["check_id"].startswith("E") and not c["passed"] and not c["error"]
    ]

    content_metrics = build_content_quality_metrics(results)

    return {
        "checks": checks,
        "cross_layer_coverage": cross_layer,
        "integrity_failures": integrity_failures,
        "property_failures": property_failures,
        "content_quality": content_metrics,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_scenario_summary(report: dict[str, Any], *, label: str = "Scenario Eval") -> None:
    overall = report["overall"]
    print(f"\n── {label} ──────────────────────────────────────")
    print(f"Overall: {overall['pass']}/{overall['total']} passed ({overall['coverage_pct']}%)\n")
    print("Per-tag:")
    for tag, counts in report["per_tag"].items():
        p = counts.get("pass", 0)
        f = counts.get("fail", 0)
        mark = "✓" if f == 0 else "✗"
        print(f"  {mark} {tag:<45} {p}/{p + f}")
    if report["gaps"]:
        print("\nFailures:")
        for gap in report["gaps"]:
            print(f"  [{gap['scenario_id']}] {gap['scenario_tag']}: {gap['failure_reason']}")


def print_audit_summary(report: dict[str, Any]) -> None:
    checks = report["checks"]
    if not checks:
        return

    # Connection failure
    if checks[0].get("check_id") in ("CONN", "SETUP") and not checks[0]["passed"]:
        print(f"\n── Triples Audit ─────────────────────────────────")
        print(f"  SKIPPED — {checks[0]['error']}")
        return

    print(f"\n── Triples Audit ─────────────────────────────────")

    # Node inventory
    print("\nNode inventory:")
    for c in checks:
        if c["check_id"].startswith("A"):
            label = c["description"].replace("Node inventory: ", "")
            print(f"  {label:<30} {c['value']}")

    # Structural integrity
    print("\nStructural integrity:")
    for c in checks:
        if c["check_id"].startswith("B"):
            mark = "✓" if c["passed"] else "✗"
            val = f"({c['value']} orphan)" if not c["passed"] else "OK"
            if c["error"]:
                val = f"ERROR: {c['error']}"
            desc = c["description"].replace("Integrity: ", "")
            print(f"  {mark} {desc:<50} {val}")

    # Chain completeness
    print("\nDiagnostic chain completeness:")
    by_id = {c["check_id"]: c for c in checks}
    total_faults = (by_id.get("A06") or {}).get("value") or "?"
    total_ec = (by_id.get("A05") or {}).get("value") or "?"
    for c in checks:
        if c["check_id"].startswith("C"):
            desc = c["description"].replace("Completeness: ", "")
            denom = total_faults if "Fault" in desc else total_ec
            print(f"  {desc:<55} {c['value']} / {denom}")

    # Property completeness
    print("\nProperty completeness:")
    for c in checks:
        if c["check_id"].startswith("E"):
            mark = "✓" if c["passed"] else "✗"
            desc = c["description"].replace("Property: ", "")
            if c["error"]:
                print(f"  {mark} {desc:<55} ERROR: {c['error']}")
            else:
                note = " (informational)" if c["passed"] and c["value"] and c["value"] > 0 else ""
                print(f"  {mark} {desc:<55} {c['value']}{note}")

    # Cross-layer
    cl = report["cross_layer_coverage"]
    print("\nCross-layer coverage (TRIGGERS):")
    print(f"  Components with TRIGGERS edges:  {cl['triggers_components']} / {cl['total_components']} ({cl['component_coverage_pct']}%)")
    print(f"  Faults reachable from asset:     {cl['faults_reachable_from_asset']} / {cl['total_faults']} ({cl['fault_reachability_pct']}%)")

    # Integrity failures
    if report["integrity_failures"]:
        print("\n  ⚠ Integrity issues found:")
        for f in report["integrity_failures"]:
            print(f"    [{f['check_id']}] {f['description']}: {f['value']} orphaned nodes")

    # Property failures
    if report.get("property_failures"):
        print("\n  ⚠ Property completeness issues found:")
        for f in report["property_failures"]:
            print(f"    [{f['check_id']}] {f['description']}: {f['value']} nodes missing required property")

    # Content quality metrics (ISO 8000 / W3C DQV dimensions)
    cq = report.get("content_quality")
    if cq:
        print("\nContent quality 指标 (ISO 8000 / W3C DQV):")
        con = cq.get("conciseness", {})
        print(f"  [Conciseness]")
        print(f"    Fault entity uniqueness:          {con.get('fault_entity_uniqueness_pct')}%")
        print(f"    ErrorCode entity uniqueness:      {con.get('error_code_entity_uniqueness_pct')}%")
        print(f"    Duplicate INDICATES triples:      {con.get('duplicate_indicates_triples')}")
        print(f"    Duplicate TRIGGERS triples:       {con.get('duplicate_triggers_triples')}")
        cs = cq.get("consistency", {})
        print(f"  [Consistency]")
        print(f"    ErrorCode cardinality violations: {cs.get('errorcode_cardinality_violations')}")
        print(f"    Multi-label type conflicts:       {cs.get('multi_label_type_conflicts')}")
        print(f"    HAS_CAUSE type violations:        {cs.get('has_cause_type_violations')}")
        va = cq.get("validity", {})
        print(f"  [Validity]")
        print(f"    ErrorCode ID format conformance:  {va.get('error_code_format_conformance_pct')}%")
        print(f"    Fault severity domain validity:   {va.get('fault_severity_domain_validity_pct')}%")
        cp = cq.get("completeness", {})
        print(f"  [Completeness]")
        print(f"    Diagnostic avg property fill:     {cp.get('diagnostic_avg_property_fill_pct')}%")
        ti = cq.get("timeliness", {})
        print(f"  [Timeliness]")
        print(f"    Validated (reviewed):             {ti.get('validated_pct')}%  ({ti.get('validated_count')} / {ti.get('validated_total')})")
        if cq.get("dimension_failures"):
            print(f"\n  ⚠ Content quality failures: {cq['dimension_failures']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Route A (text2cypher) scenarios + KG triples quality"
    )
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--blind-query-bank", type=Path, help="Query-only governed blind bank; requires both skip flags and --blind-output.")
    parser.add_argument("--blind-output", type=Path, help="Output report for --blind-query-bank.")
    parser.add_argument("--blind-review-key-from-workbook", type=Path, help="Authorized masked workbook used only to make a local human-review key.")
    parser.add_argument("--blind-review-key-output", type=Path, help="Local output path for the separate blind review key.")
    parser.add_argument("--skip-scenarios", action="store_true",
                        help="Skip golden-set scenario evaluation")
    parser.add_argument("--skip-audit", action="store_true",
                        help="Skip triples quality audit")
    parser.add_argument("--static-coverage-input", type=Path,
                        help="Adapter-normalized static-coverage snapshot JSON")
    parser.add_argument("--static-coverage-output", type=Path,
                        help="Static-coverage report JSON (requires --static-coverage-input)")
    args = parser.parse_args(argv)

    if args.static_coverage_input:
        if not args.static_coverage_output:
            parser.error("--static-coverage-output is required with --static-coverage-input")
        if not (args.skip_scenarios and args.skip_audit):
            parser.error("static coverage requires --skip-scenarios --skip-audit")
        try:
            snapshot = json.loads(args.static_coverage_input.read_text(encoding="utf-8"))
            report = evaluate_static_coverage(snapshot)
        except (OSError, json.JSONDecodeError, StaticCoverageInputError) as exc:
            print(f"static coverage evaluation failed: {exc}", file=sys.stderr)
            return 2
        args.static_coverage_output.parent.mkdir(parents=True, exist_ok=True)
        args.static_coverage_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Static coverage report written to {args.static_coverage_output}")
        return 0
    if args.static_coverage_output:
        parser.error("--static-coverage-output requires --static-coverage-input")
    if args.blind_query_bank:
        if not args.blind_output:
            parser.error("--blind-query-bank requires --blind-output")
        if not (args.skip_scenarios and args.skip_audit):
            parser.error("blind execution requires --skip-scenarios --skip-audit")
        try:
            bank = load_query_bank(args.blind_query_bank)
            report = run_query_bank_ollama(bank)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"blind evaluation failed: {exc}", file=sys.stderr)
            return 2
        args.blind_output.parent.mkdir(parents=True, exist_ok=True)
        args.blind_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if bool(args.blind_review_key_from_workbook) != bool(args.blind_review_key_output):
            parser.error("blind review-key export requires both --blind-review-key-from-workbook and --blind-review-key-output")
        if args.blind_review_key_from_workbook:
            key = build_review_key(bank, args.blind_review_key_from_workbook)
            args.blind_review_key_output.parent.mkdir(parents=True, exist_ok=True)
            args.blind_review_key_output.write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Blind human-review key written to {args.blind_review_key_output}")
        print(f"Blind Ollama report written to {args.blind_output}")
        return 0
    if args.blind_output:
        parser.error("--blind-output requires --blind-query-bank")

    print(f"\n=== Route A + KG Quality Eval ({date.today()}) ===")

    scenario_report: dict[str, Any] | None = None
    audit_report: dict[str, Any] | None = None

    if not args.skip_scenarios:
        golden = load_golden(args.golden)
        registry = load_registry(args.registry)
        results = [
            evaluate_case(case)
            for case in golden
            if case.get("scenario_id") and not _should_skip(case)
        ]
        scenario_report = build_scenario_report(results, registry=registry)
        print_scenario_summary(scenario_report)

    if not args.skip_audit:
        audit_results = run_triples_audit()
        audit_report = build_audit_report(audit_results)
        print_audit_summary(audit_report)

    combined: dict[str, Any] = {"eval_date": str(date.today())}
    if scenario_report:
        combined["scenario_eval"] = scenario_report
    if audit_report:
        combined["triples_audit"] = audit_report

    output_path = args.output or (
        REPO_ROOT / f"data/eval/route_a/eval_report_{date.today()}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport written to {output_path}")

    from services.governance._operation_log import safe_repo_path
    from services.governance.eval_run_log import record as record_eval_run

    score_summary: dict[str, Any] = {}
    if scenario_report:
        score_summary["scenario"] = scenario_report.get("overall", {})
    if audit_report:
        score_summary["audit"] = {
            "integrity_failures": len(audit_report.get("integrity_failures", [])),
            "property_failures": len(audit_report.get("property_failures", [])),
        }
    eval_set = (
        safe_repo_path(args.golden, REPO_ROOT)
        if not args.skip_scenarios
        else "route_a_triples_audit"
    )
    record_eval_run(
        eval_set=eval_set,
        model=os.getenv("FAULTDX_ROUTE_A_MODEL", "route_a_pipeline"),
        route="route_a",
        score_summary=score_summary,
        notes=f"report={safe_repo_path(output_path, REPO_ROOT)}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
