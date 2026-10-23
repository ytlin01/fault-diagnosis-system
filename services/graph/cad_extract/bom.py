"""
BOM (XLSX) loader and matcher against the STEP-extracted parts list.

BOM columns: 级别, 编号, BOM.名称, BOM.型号, BOM.数量.

Two subtleties that drive the logic here:

1. BOM 数量 is recorded **per-parent** (indented style). A row at 级别=3 with
   qty=2 nested under a 级别=2 row with qty=3 contributes 6 instances to the
   whole-assembly total. STEP's NAUO count is already whole-assembly, so we
   must expand the BOM along 级别 before comparing against STEP.
2. STEP's parts list contains noise that shouldn't reach the matcher at all —
   qty=0 products (BREP geometry refs with no NAUO edges) and numeric-only
   names like "00"/"01" (SolidWorks config labels).

All threshold constants are passed as keyword args with defaults that match
configs/cad_extract.yaml. Call sites should pass BomMatchConfig values from
the loaded config so thresholds remain overridable without code changes.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any, Callable

import pandas as pd


# ---------------------------------------------------------------------------
# Internal normaliser factory
# ---------------------------------------------------------------------------

def _make_norm(strip_rev_suffix: str | None) -> Callable[[Any], str]:
    """Return a string normalizer compiled for the given suffix pattern."""
    rev_re = re.compile(strip_rev_suffix) if strip_rev_suffix else None

    def _norm(s: Any) -> str:
        if s is None or (isinstance(s, float) and pd.isna(s)):
            return ""
        k = re.sub(r"\s+", " ", str(s).strip().upper())
        if rev_re is not None:
            k = rev_re.sub("", k)
        return k

    return _norm


# Default normalisers matching configs/cad_extract.yaml defaults
_DEFAULT_STRIP_REV_SUFFIX = r"\s+REV[_\-]?[A-Z0-9]+$"
_norm_default = _make_norm(_DEFAULT_STRIP_REV_SUFFIX)


def _is_non_mechanical(name: Any, keywords: tuple[str, ...]) -> bool:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return False
    n = str(name).upper()
    return any(kw.upper() in n for kw in keywords)


# ---------------------------------------------------------------------------
# BOM loader
# ---------------------------------------------------------------------------

def load_bom(
    path: Path,
    *,
    strip_rev_suffix: str | None = _DEFAULT_STRIP_REV_SUFFIX,
) -> dict[str, dict]:
    """
    Return {normalized_型号: {型号, 名称, 编号s, qty, rows}}.

    Dispatches on BOM schema:
      - Indented BOM (has 级别 column):
          Columns: 级别, 编号, BOM.名称, BOM.型号, BOM.数量
          数量 is per-parent; qty is hierarchically expanded via a cumulative-
          multiplier stack indexed by 级别.
      - Flat BOM (no 级别):
          Columns: ID, 产品物料, 图号/物料描述, 数量, 固定物料, 物料/部件
          Each row is one part at whole-assembly total qty, no expansion.
    """
    _norm = _make_norm(strip_rev_suffix)
    df = pd.read_excel(path, engine="openpyxl")
    if "级别" in df.columns:
        return _load_indented_bom(df, _norm)
    return _load_flat_bom(df, _norm)


def _load_indented_bom(df: "pd.DataFrame", _norm: Callable) -> dict[str, dict]:
    out: dict[str, dict] = {}
    stack: list[float] = [1.0]

    for _, row in df.iterrows():
        level_raw = row.get("级别")
        if pd.isna(level_raw):
            continue
        level = int(level_raw)

        if level == 0:
            del stack[1:]
            continue

        while len(stack) > level:
            stack.pop()

        qty_raw = row.get("BOM.数量")
        if pd.isna(qty_raw):
            stack.append(0.0)
            continue

        parent_mult = stack[-1]
        this_total = parent_mult * float(qty_raw)
        stack.append(this_total)

        key = _norm(row.get("BOM.型号"))
        if not key:
            continue

        entry = out.setdefault(key, {
            "型号": row["BOM.型号"],
            "名称": "" if pd.isna(row.get("BOM.名称")) else row["BOM.名称"],
            "编号s": [],
            "qty": 0.0,
            "rows": 0,
        })
        entry["qty"] += this_total
        entry["rows"] += 1
        code = row.get("编号")
        if code is not None and not pd.isna(code):
            entry["编号s"].append(str(code))

    return out


def _load_flat_bom(df: "pd.DataFrame", _norm: Callable) -> dict[str, dict]:
    COL_ID = "图号/物料描述"
    COL_NAME = "名称/规格"
    COL_QTY = "数量"
    COL_CODE = "货品代号"

    missing = [c for c in (COL_ID, COL_NAME, COL_QTY) if c not in df.columns]
    if missing:
        raise ValueError(f"Flat BOM missing expected columns: {missing}. Got {df.columns.tolist()}")

    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        key = _norm(row.get(COL_ID))
        qty_raw = row.get(COL_QTY)
        if not key or pd.isna(qty_raw):
            continue

        entry = out.setdefault(key, {
            "型号": row[COL_ID],
            "名称": "" if pd.isna(row.get(COL_NAME)) else row[COL_NAME],
            "编号s": [],
            "qty": 0.0,
            "rows": 0,
        })
        entry["qty"] += float(qty_raw)
        entry["rows"] += 1
        code = row.get(COL_CODE)
        if code is not None and not pd.isna(code):
            entry["编号s"].append(str(code))
    return out


# ---------------------------------------------------------------------------
# Parts loader
# ---------------------------------------------------------------------------

def load_parts(
    path: Path,
    *,
    filter_noise: bool = True,
    strip_rev_suffix: str | None = _DEFAULT_STRIP_REV_SUFFIX,
) -> tuple[dict[str, dict], list[dict]]:
    """
    Return (parts, step_filtered) from a parts_list.json file.

    parts: {normalized_型号: {型号, 名称, qty}}
    step_filtered: list of raw entries dropped as noise (when filter_noise=True)
        - bom数量 == 0: PRODUCT with no NAUO edges (geometry ref, not assembly)
        - 型号 matches ^\\d+$: numeric-only SolidWorks config labels ("00"/"01"/…)
    """
    _norm = _make_norm(strip_rev_suffix)
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    filtered: list[dict] = []

    numeric_only = re.compile(r"^\d+$")

    for p in raw:
        key = _norm(p.get("bom型号"))
        qty = int(p.get("bom数量", 0))
        if not key:
            continue
        if filter_noise and (qty == 0 or numeric_only.fullmatch(key)):
            filtered.append({
                "型号": p.get("bom型号"),
                "名称": p.get("bom名称"),
                "qty": qty,
                "reason": "qty_zero" if qty == 0 else "numeric_only_name",
            })
            continue
        entry = out.setdefault(key, {
            "型号": p["bom型号"],
            "名称": p["bom名称"],
            "qty": 0,
        })
        entry["qty"] += qty

    return out, filtered


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

def _split_bom_only(
    bom_only_keys: set[str],
    bom: dict[str, dict],
    keywords: tuple[str, ...],
) -> tuple[list[dict], list[dict], dict[str, dict]]:
    non_mech: list[dict] = []
    suspected: list[dict] = []
    suspected_by_key: dict[str, dict] = {}
    for bk in sorted(bom_only_keys):
        entry = bom[bk]
        if _is_non_mechanical(entry.get("名称"), keywords):
            non_mech.append(entry)
        else:
            suspected.append(entry)
            suspected_by_key[bk] = entry
    return non_mech, suspected, suspected_by_key


def match_parts_to_bom(
    parts: dict[str, dict],
    bom: dict[str, dict],
    *,
    fuzzy_cutoff: float = 0.80,
    step_filtered: list[dict] | None = None,
    non_mechanical_keywords: tuple[str, ...] = (),
) -> dict[str, Any]:
    """
    Bucket every product into one of:
      - matched                      exact 型号 match + qty equal
      - qty_mismatch                 exact 型号 match but STEP qty ≠ BOM qty
      - step_only                    in parts list, not in BOM
      - bom_only_non_mechanical      in BOM, non-mechanical (wires/cables/…)
      - bom_only_suspected_missing   in BOM, looks mechanical but absent from STEP
      - fuzzy_candidates             top-3 STEP candidates for each suspected-missing
                                     BOM item (advisory only — buckets are not mutated)
    """
    matched: list[dict] = []
    qty_mismatch: list[dict] = []

    common = set(parts) & set(bom)
    for k in sorted(common):
        p, b = parts[k], bom[k]
        entry = {
            "型号": b["型号"],
            "step_名称": p["名称"],
            "bom_名称": b["名称"],
            "bom_编号s": b.get("编号s", []),
            "step_qty": p["qty"],
            "bom_qty": b["qty"],
        }
        (matched if p["qty"] == b["qty"] else qty_mismatch).append(entry)

    step_only_keys = set(parts) - common
    bom_only_keys = set(bom) - common

    non_mech, suspected, suspected_by_key = _split_bom_only(
        bom_only_keys, bom, non_mechanical_keywords
    )

    step_keys_list = list(step_only_keys)
    fuzzy_candidates: list[dict] = []
    for bk in sorted(suspected_by_key):
        cands = get_close_matches(bk, step_keys_list, n=3, cutoff=fuzzy_cutoff)
        if not cands:
            continue
        fuzzy_candidates.append({
            "from": {
                "source": "bom_only_suspected_missing",
                "型号": bom[bk]["型号"],
                "名称": bom[bk]["名称"],
            },
            "candidates": [
                {
                    "side": "step",
                    "型号": parts[sk]["型号"],
                    "名称": parts[sk]["名称"],
                    "step_qty": parts[sk]["qty"],
                    "similarity": round(SequenceMatcher(None, bk, sk).ratio(), 3),
                }
                for sk in cands
            ],
        })

    step_filtered = step_filtered or []

    return {
        "summary": {
            "total_step_parts": len(parts),
            "total_step_filtered": len(step_filtered),
            "total_bom_parts": len(bom),
            "matched": len(matched),
            "qty_mismatch": len(qty_mismatch),
            "fuzzy_candidates": len(fuzzy_candidates),
            "step_only": len(step_only_keys),
            "bom_only_non_mechanical": len(non_mech),
            "bom_only_suspected_missing": len(suspected),
        },
        "matched": matched,
        "qty_mismatch": qty_mismatch,
        "fuzzy_candidates": fuzzy_candidates,
        "step_only": [parts[k] for k in sorted(step_only_keys)],
        "step_filtered": step_filtered,
        "bom_only_non_mechanical": non_mech,
        "bom_only_suspected_missing": suspected,
        "config": {
            "fuzzy_cutoff": fuzzy_cutoff,
            "non_mechanical_keywords": list(non_mechanical_keywords),
        },
    }
