"""
Validate emitted triples against the diagnostic v3.2 KG schema.

This module reads `contracts/schema/diagnostic_schema_v3_2.json` and checks that every
node / edge in a TripleSet conforms to the per-label and per-relationship
rules.

v3.2 vs v3.1 changes
---------------------
- QPL node removed; Station is the top-level device-asset node.
- Module.qpl_id removed; Module.station_id is required (always a real string).
- HAS_MODULE.from is always a Station node — no null-from gap.
- The two phase-1 expected-violation promotions from v3.1 are gone.
  All violations in v3.2 are real errors.

Two kinds of violation
----------------------
* **error** — a real defect in the emitter or schema drift. Must be fixed.
* **expected** — reserved for future known gaps; currently unused in v3.2.

Implementation notes
--------------------
The diagnostic schema is a *definitions* document, not a JSON Schema applied
to triples.json directly. We extract per-label / per-edge specs and validate
each node / edge individually.

The validator is stdlib-only:

    required, type, additionalProperties, enum, minimum, maximum,
    minItems, items, properties

If the schema later grows features beyond this subset (oneOf, $ref, …) swap
this module for `jsonschema.Draft7Validator` rather than extending the
hand-rolled checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "contracts"
    / "schema"
    / "diagnostic_schema_v3_2.json"
)


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    """One schema rule that an emitted node or edge failed."""
    severity: str        # "error" | "expected"
    location: str        # node id, "edge[i]", or "<root>"
    rule: str
    detail: str
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "location": self.location,
            "rule": self.rule,
            "path": self.path,
            "detail": self.detail,
        }


@dataclass
class ValidationReport:
    """Aggregate result of validating one TripleSet."""
    schema_version: str
    nodes_checked: int
    edges_checked: int
    violations: list[Violation] = field(default_factory=list)
    expected_violations: list[Violation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "nodes_checked": self.nodes_checked,
            "edges_checked": self.edges_checked,
            "is_valid": self.is_valid,
            "error_count": len(self.violations),
            "expected_violation_count": len(self.expected_violations),
            "violations": [v.to_dict() for v in self.violations],
            "expected_violations": [v.to_dict() for v in self.expected_violations],
        }


# ---------------------------------------------------------------------------
# Schema-loading helpers
# ---------------------------------------------------------------------------

def load_schema(schema_path: Path = SCHEMA_PATH) -> dict:
    """Read the diagnostic schema JSON. Cheap; not memoized — call site decides."""
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _as_label_set(spec: str | list[str]) -> set[str]:
    return {spec} if isinstance(spec, str) else set(spec)


def _build_relationship_index(schema: dict) -> dict[str, dict]:
    """Flatten `relationships.<layer>.[]` into {edge_type: rule-bundle}."""
    rels: dict[str, dict] = {}
    for _layer, defs in schema["definitions"]["relationships"].items():
        for d in defs:
            rels[d["type"]] = {
                "from_labels": _as_label_set(d["from"]),
                "to_labels":   _as_label_set(d["to"]),
                "properties_schema": {
                    "type": "object",
                    "properties": d.get("properties", {}) or {},
                },
            }
    return rels


# ---------------------------------------------------------------------------
# Mini JSON-Schema engine (stdlib only, v3.2-subset)
# ---------------------------------------------------------------------------

def _is_type(value: Any, type_spec: str | list[str]) -> bool:
    types = [type_spec] if isinstance(type_spec, str) else list(type_spec)
    for t in types:
        if t == "null" and value is None:
            return True
        if t == "string" and isinstance(value, str):
            return True
        # Booleans are a subclass of int; JSON-Schema number/int must reject them.
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "object" and isinstance(value, dict):
            return True
    return False


def _validate_value(value: Any, spec: dict, location: str, path: str) -> list[Violation]:
    out: list[Violation] = []
    if "type" in spec and not _is_type(value, spec["type"]):
        out.append(Violation(
            severity="error", location=location, rule="wrong_type", path=path,
            detail=f"{path!r}={value!r} is not of type {spec['type']!r}",
        ))
        return out

    if "enum" in spec and value not in spec["enum"]:
        out.append(Violation(
            severity="error", location=location, rule="enum_mismatch", path=path,
            detail=f"{path!r}={value!r} not in {spec['enum']}",
        ))

    if "minimum" in spec and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < spec["minimum"]:
            out.append(Violation(
                severity="error", location=location, rule="below_minimum", path=path,
                detail=f"{path!r}={value} < minimum {spec['minimum']}",
            ))
    if "maximum" in spec and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > spec["maximum"]:
            out.append(Violation(
                severity="error", location=location, rule="above_maximum", path=path,
                detail=f"{path!r}={value} > maximum {spec['maximum']}",
            ))

    if isinstance(value, list):
        if "minItems" in spec and len(value) < spec["minItems"]:
            out.append(Violation(
                severity="error", location=location, rule="below_minitems", path=path,
                detail=f"{path!r} has {len(value)} item(s) < minItems {spec['minItems']}",
            ))
        if "items" in spec:
            for i, item in enumerate(value):
                out.extend(_validate_value(item, spec["items"], location, f"{path}[{i}]"))

    return out


def _validate_object(obj: dict, schema: dict, location: str) -> list[Violation]:
    out: list[Violation] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for key in required:
        if key not in obj:
            out.append(Violation(
                severity="error", location=location, rule="missing_required", path=key,
                detail=f"missing required field {key!r}",
            ))

    if additional is False:
        for key in obj:
            if key not in properties:
                out.append(Violation(
                    severity="error", location=location, rule="extra_property", path=key,
                    detail=f"unexpected field {key!r} (additionalProperties: false)",
                ))

    for key, value in obj.items():
        sub = properties.get(key)
        if sub is None:
            continue
        out.extend(_validate_value(value, sub, location, key))

    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate_triples(triples: dict, schema: dict | None = None) -> ValidationReport:
    """Validate a `TripleSet.to_dict()` payload against schema v3.2.

    All violations are real errors — v3.2 has no documented phase-N gaps.
    The `expected_violations` list in the report is always empty.
    """
    if schema is None:
        schema = load_schema()

    report = ValidationReport(
        schema_version=triples.get("schema_version", ""),
        nodes_checked=len(triples.get("nodes", [])),
        edges_checked=len(triples.get("edges", [])),
    )

    expected_version = schema.get("version")
    if expected_version and triples.get("schema_version") != expected_version:
        report.violations.append(Violation(
            severity="error", location="<root>", rule="schema_version_mismatch",
            path="schema_version",
            detail=(
                f"triples.schema_version={triples.get('schema_version')!r} "
                f"does not match schema.version={expected_version!r}"
            ),
        ))

    node_defs = schema["definitions"]["nodes"]
    rel_index = _build_relationship_index(schema)

    id_to_label: dict[str, str] = {}
    duplicate_ids: list[str] = []
    for n in triples.get("nodes", []):
        node_id = n.get("id")
        if not isinstance(node_id, str):
            continue
        if node_id in id_to_label:
            duplicate_ids.append(node_id)
        else:
            id_to_label[node_id] = n.get("label", "")

    for dup in duplicate_ids:
        report.violations.append(Violation(
            severity="error", location=dup, rule="duplicate_id", path="id",
            detail=f"node id {dup!r} appears more than once",
        ))

    # ---- Node validation ---------------------------------------------------
    for n in triples.get("nodes", []):
        label = n.get("label", "")
        node_id = n.get("id") if isinstance(n.get("id"), str) else "<missing>"
        if label not in node_defs:
            report.violations.append(Violation(
                severity="error", location=node_id, rule="unknown_label", path="label",
                detail=f"label {label!r} not in schema definitions.nodes",
            ))
            continue
        props = n.get("properties", {}) or {}
        report.violations.extend(_validate_object(props, node_defs[label], node_id))

    # ---- Edge validation ---------------------------------------------------
    for idx, e in enumerate(triples.get("edges", [])):
        loc = f"edge[{idx}]"
        etype = e.get("type", "")
        if etype not in rel_index:
            report.violations.append(Violation(
                severity="error", location=loc, rule="unknown_edge_type", path="type",
                detail=f"edge type {etype!r} not in schema relationships",
            ))
            continue
        rel = rel_index[etype]

        for endpoint_field, allowed in (("from", rel["from_labels"]), ("to", rel["to_labels"])):
            endpoint_id = e.get(endpoint_field)
            if endpoint_id is None:
                report.violations.append(Violation(
                    severity="error", location=loc, rule="missing_endpoint",
                    path=endpoint_field,
                    detail=f"{etype}.{endpoint_field} is null",
                ))
                continue
            actual_label = id_to_label.get(endpoint_id)
            if actual_label is None:
                report.violations.append(Violation(
                    severity="error", location=loc, rule="dangling_endpoint",
                    path=endpoint_field,
                    detail=f"{etype}.{endpoint_field}={endpoint_id!r} references no node",
                ))
            elif actual_label not in allowed:
                report.violations.append(Violation(
                    severity="error", location=loc, rule="wrong_endpoint_label",
                    path=endpoint_field,
                    detail=(
                        f"{etype}.{endpoint_field} → node {endpoint_id!r} has label "
                        f"{actual_label!r}, schema allows {sorted(allowed)}"
                    ),
                ))

        props = e.get("properties", {}) or {}
        report.violations.extend(_validate_object(props, rel["properties_schema"], loc))

    return report


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def format_summary(report: ValidationReport) -> str:
    return (
        f"validation: nodes={report.nodes_checked} edges={report.edges_checked} "
        f"errors={len(report.violations)} expected={len(report.expected_violations)}"
    )
