#!/usr/bin/env python3
"""V2-TASK016 review-label validator.

Validates review_labels.jsonl (one JSON object per line) against
review_labels.schema.json plus the publish rules from
review_labels_guide.md (fill workflow step 2):

  1. per-record JSON Schema validation;
  2. placeholder detection: any string containing REPLACE_ME marks the
     record as pending (scaffold not yet filled by the domain reviewer);
  3. structural checks: well-formed material row anchor, unique label_id,
     no exact duplicate anchors;
  4. publish gates: leakage.status must not be 'unchecked'; only
     'reviewed'/'adjudicated' maturity is scoring-eligible;
  5. leakage heuristic: warns when a sensitive column NAME appears in any
     free-text field. This is a name-based heuristic only -- the
     value-level check against the source workbook remains the domain
     reviewer's responsibility (guide, leakage rules).

Usage:
    python validate_review_labels.py [labels.jsonl]

Exit codes:
    0  no invalid records (pending / calibration-only allowed)
    1  one or more records invalid or unparseable
    2  prerequisites missing (label file, schema, jsonschema module)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("ERROR: the 'jsonschema' package is required (pip install jsonschema)")
    sys.exit(2)

BASE = Path(__file__).resolve().parent
SCHEMA_PATH = BASE / "review_labels.schema.json"
LABELS_PATH = BASE / "review_labels.jsonl"

MARKER = "REPLACE_ME"
SCORING_MATURITY = {"reviewed", "adjudicated"}

# Sensitive column names from configs/pipelines/replacement_extract.yaml as
# cited by review_labels_guide.md. Longest-first so reports name the exact
# column; '廠商' also matches the shorter prefix forms.
SENSITIVE_TERMS = [
    "廠商代碼", "廠商 PN", "廠商PN", "品牌", "設備名稱", "設備型號",
    "聯繫人", "備註", "專案", "製程", "物料", "單價", "耗材QPL", "廠商",
]

# material source-row anchor: raw__...#工作表1!r<N> (+r<M> for the merge pair)
ANCHOR_RE = re.compile(
    r"^raw__C1STN_bom_material__L_ReplacementList#工作表1!r\d+(\+r\d+)*$"
)

TEXT_FIELDS = [
    "anchor", "scope", "labels_source", "source_basis", "note",
    "leakage.note", "applicability.reason",
]


def iter_strings(obj, path="$"):
    """Yield (json_path, value) for every string leaf and every dict key."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", str(k)
            yield from iter_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def marker_fields(rec):
    return [p for p, s in iter_strings(rec) if MARKER in s]


def sensitive_hits(rec):
    hits = []
    for p, s in iter_strings(rec):
        for term in SENSITIVE_TERMS:
            if term in s:
                hits.append((p, term))
                break
    return hits


def anchor_rows(anchor):
    return re.findall(r"r(\d+)", anchor.split("#", 1)[-1])


def main() -> int:
    labels_path = Path(sys.argv[1]) if len(sys.argv) > 1 else LABELS_PATH
    if not labels_path.is_file():
        print(f"ERROR: label file not found: {labels_path}")
        return 2
    if not SCHEMA_PATH.is_file():
        print(f"ERROR: schema not found: {SCHEMA_PATH}")
        return 2

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    records = []       # (lineno, record)
    statuses = {}      # lineno -> status
    messages = []      # (lineno, severity, text)
    seen_ids = {}
    seen_anchors = {}
    seen_rows = {}

    for lineno, line in enumerate(labels_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            statuses[lineno] = "invalid"
            messages.append((lineno, "invalid", f"not valid JSON: {exc.msg}"))
            continue
        records.append((lineno, rec))
        rid = rec.get("label_id", f"<line {lineno}>")

        # 1) pending placeholder detection
        mf = marker_fields(rec)
        if mf:
            statuses[lineno] = "pending"
            messages.append((lineno, "pending", "fill " + ", ".join(mf)))
            continue

        # 2) schema validation
        errors = sorted(validator.iter_errors(rec), key=lambda e: list(e.absolute_path))
        if errors:
            statuses[lineno] = "invalid"
            for e in errors:
                loc = "/".join(str(x) for x in e.absolute_path) or "<root>"
                messages.append((lineno, "invalid", f"{rid}: schema: {loc}: {e.message}"))
            continue

        # 3) structural checks
        struct_bad = False
        if rec.get("surface") == "material" and not ANCHOR_RE.match(rec.get("anchor", "")):
            statuses[lineno] = "invalid"
            messages.append((lineno, "invalid", f"{rid}: anchor not a well-formed material source-row anchor"))
            struct_bad = True
        if rec["label_id"] in seen_ids:
            statuses[lineno] = "invalid"
            messages.append((lineno, "invalid", f"{rid}: duplicate label_id (first at line {seen_ids[rec['label_id']]})"))
            struct_bad = True
        else:
            seen_ids[rec["label_id"]] = lineno
        if rec["anchor"] in seen_anchors:
            statuses[lineno] = "invalid"
            messages.append((lineno, "invalid", f"{rid}: duplicate anchor (first at line {seen_anchors[rec['anchor']]})"))
            struct_bad = True
        else:
            seen_anchors[rec["anchor"]] = lineno
        for row in anchor_rows(rec["anchor"]):
            if row in seen_rows and seen_rows[row] != lineno:
                messages.append((lineno, "warning",
                                 f"{rid}: row r{row} also appears in line {seen_rows[row]} "
                                 "(expected for the merge record vs its member rows)"))
            else:
                seen_rows.setdefault(row, lineno)
        if struct_bad:
            continue

        # 4) publish gates
        leakage_status = rec.get("leakage", {}).get("status", "")
        maturity = rec.get("label_maturity", "")
        if leakage_status == "unchecked":
            statuses[lineno] = "not-publishable"
            messages.append((lineno, "not-publishable",
                             f"{rid}: leakage.status is 'unchecked' (never publishable; re-check against the sensitive-column list)"))
        elif maturity not in SCORING_MATURITY:
            statuses[lineno] = "calibration-only"
            messages.append((lineno, "calibration-only",
                             f"{rid}: label_maturity '{maturity}' is not scoring-eligible "
                             "(only reviewed/adjudicated enter the domain scorecards)"))
        else:
            statuses[lineno] = "publishable"
            if rec.get("label_independence", {}).get("overlap") is False:
                messages.append((lineno, "warning",
                                 f"{rid}: overlap=false asserted -- confirm the labeling basis is NOT the source workbook"))

        # 5) sensitive-name heuristic (warnings only)
        for p, term in sensitive_hits(rec):
            messages.append((lineno, "warning",
                             f"{rid}: sensitive column name '{term}' appears at {p} -- confirm no sensitive VALUE is exposed"))

    # summary
    order = ["pending", "publishable", "calibration-only", "not-publishable", "invalid"]
    counts = {s: 0 for s in order}
    for st in statuses.values():
        counts[st] += 1
    print(f"V2-TASK016 label validation -- {labels_path.name}")
    print(f"  records:         {sum(counts.values())}")
    for s in order:
        print(f"  {s:16s} {counts[s]}")
    warn = sum(1 for _, sev, _ in messages if sev == "warning")
    print(f"  warnings:        {warn}")
    if messages:
        print("\nPer-record messages:")
        for lineno, sev, text in messages:
            print(f"  line {lineno:3d} [{sev:15s}] {text}")
    print("\nReminder: leakage scan here is a name-based heuristic; the value-level")
    print("check against the 13 sensitive columns stays with the domain reviewer.")
    return 1 if counts["invalid"] else 0


if __name__ == "__main__":
    sys.exit(main())
