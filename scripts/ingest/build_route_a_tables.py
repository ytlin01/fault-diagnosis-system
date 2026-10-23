"""Assemble Route A columnar products from Vision Flow SOP canonical blocks.

Reads the canonical JSON produced by run_ingest_unstructured.py and assembles
three Route A tables into flat CSV products under data/processed/:

    1. BOM               (slide 7)        -> vision_sop_bom.csv
    2. CCD config         (slides 8-14)    -> vision_sop_ccd.csv
    3. Fool-Proof List    (slides 36 + 38) -> vision_sop_fool_proof_list.csv

This is the Phase 3 assembly layer. It does NOT touch _blocks_from_pptx; it
operates on the already-extracted table blocks. The Fool-Proof List has a
two-row merged header (Vendor spanning DRI / Add Time) that is flattened into
single-row column names here so downstream column-rule masking can match by
column name (see configs/masking_rules.yaml source vision_sop_fool_proof_list).

Usage:
    python scripts/ingest/build_route_a_tables.py \
        --canonical "data/processed/unstructured/Luster_..._canonical.json"

    # Auto-discover the latest Vision Flow canonical JSON:
    python scripts/ingest/build_route_a_tables.py

CSV files are written UTF-8 with BOM so Excel renders CJK text correctly.
Outputs land in data/processed/ (gitignored) and may contain raw DRI names;
masking happens in Phase 4 via run_mask_structured.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Expected (flat) headers used to pick the right table block per slide.
BOM_HEADER = ["No.", "Item", "Brand", "Model", "Qty"]
CCD_HEADER = [
    "Camera Name",
    "Functional Module",
    "Installation Direction",
    "Fixed Position",
    "Description",
    "Remark",
]


def _norm(cell: str) -> str:
    return (cell or "").strip()


def _header_matches(row: list[str], expected: list[str]) -> bool:
    return [_norm(c) for c in row[: len(expected)]] == expected


def _is_empty_data_row(cells: list[str], index_col: int = 0) -> bool:
    """A data row is empty when only the leading index column carries content."""
    return not any(_norm(c) for i, c in enumerate(cells) if i != index_col)


def _slide_tables(blocks: list[dict], slide: int) -> list[list[list[str]]]:
    return [
        b["table"]["rows"]
        for b in blocks
        if b.get("source_anchor", {}).get("slide") == slide
        and b.get("block_type") == "table"
    ]


def flatten_two_row_header(row0: list[str], row1: list[str]) -> list[str]:
    """Flatten a two-row header into single-row names.

    Top-row merged cells (gridSpan/hMerge) leave blank continuation cells; we
    forward-fill the last seen top value so the sub-row name attaches to the
    right parent. Convention: ``top + " " + sub`` (sub omitted when blank).
        Vendor + DRI       -> "Vendor DRI"
        Vendor + Add Time  -> "Vendor Add Time"   (col blank in row0, filled here)
    """
    cols: list[str] = []
    last_top = ""
    width = max(len(row0), len(row1))
    for i in range(width):
        top = _norm(row0[i]) if i < len(row0) else ""
        if top:
            last_top = top
        else:
            top = last_top  # gridSpan / hMerge continuation
        sub = _norm(row1[i]) if i < len(row1) else ""
        cols.append(f"{top} {sub}".strip() if sub else top)
    return cols


def build_bom(blocks: list[dict]) -> tuple[list[str], list[list[str]]]:
    """Merge slide 7 BOM segments, drop the repeated header and empty rows."""
    segments = [t for t in _slide_tables(blocks, 7) if t and _header_matches(t[0], BOM_HEADER)]
    if not segments:
        raise ValueError("slide 7 BOM table not found")
    header = BOM_HEADER + ["slide"]
    rows: list[list[str]] = []
    for seg in segments:
        for cells in seg[1:]:  # skip per-segment header
            if _is_empty_data_row(cells):
                continue
            rows.append([_norm(c) for c in cells[: len(BOM_HEADER)]] + ["7"])
    return header, rows


def build_ccd(blocks: list[dict]) -> tuple[list[str], list[list[str]]]:
    """Concatenate the CCD config table (block 0) across slides 8-14.

    Each CCD slide also carries a separate hardware-spec table
    (Item/Class/Specifications/Qty); that one is out of Route A scope and is
    skipped by matching on CCD_HEADER.
    """
    header = CCD_HEADER + ["slide"]
    rows: list[list[str]] = []
    for slide in range(8, 15):
        config = [t for t in _slide_tables(blocks, slide) if t and _header_matches(t[0], CCD_HEADER)]
        for seg in config:
            for cells in seg[1:]:  # skip header on every slide
                if _is_empty_data_row(cells):
                    continue
                rows.append([_norm(c) for c in cells[: len(CCD_HEADER)]] + [str(slide)])
    if not rows:
        raise ValueError("no CCD config rows found across slides 8-14")
    return header, rows


def build_fool_proof(blocks: list[dict]) -> tuple[list[str], list[list[str]]]:
    """Merge slide 36 + 38 Fool-Proof List with a flattened two-row header."""
    s36 = _slide_tables(blocks, 36)
    s38 = _slide_tables(blocks, 38)
    if not s36:
        raise ValueError("slide 36 Fool-Proof table not found")
    base = s36[0]
    flat = flatten_two_row_header(base[0], base[1])
    header = flat + ["slide"]
    width = len(flat)
    rows: list[list[str]] = []

    def _emit(table_rows: list[list[str]], slide: int) -> None:
        for cells in table_rows[2:]:  # skip the two header rows
            if _is_empty_data_row(cells):
                continue
            padded = [_norm(c) for c in cells[:width]]
            padded += [""] * (width - len(padded))
            rows.append(padded + [str(slide)])

    _emit(base, 36)
    if s38:
        _emit(s38[0], 38)
    return header, rows


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _discover_canonical() -> Path:
    search_dir = PROJECT_ROOT / "data" / "processed" / "unstructured"
    matches = sorted(
        search_dir.glob("*Vision_Flow*_canonical.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise FileNotFoundError(
            f"no Vision Flow canonical JSON under {search_dir}; "
            "run run_ingest_unstructured.py first or pass --canonical"
        )
    return matches[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble Route A SOP tables")
    parser.add_argument(
        "--canonical",
        default=None,
        help="Path to SOP canonical JSON. Auto-discovers latest if omitted.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "processed"),
        help="Directory for columnar CSV products (default: data/processed/).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    canonical_path = Path(args.canonical) if args.canonical else _discover_canonical()
    output_dir = Path(args.output_dir)
    doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    blocks = doc["blocks"]

    artifacts = {
        "vision_sop_bom.csv": build_bom(blocks),
        "vision_sop_ccd.csv": build_ccd(blocks),
        "vision_sop_fool_proof_list.csv": build_fool_proof(blocks),
    }

    print(f"source canonical: {canonical_path}")
    for filename, (header, rows) in artifacts.items():
        out_path = output_dir / filename
        _write_csv(out_path, header, rows)
        by_slide: dict[str, int] = {}
        for row in rows:
            by_slide[row[-1]] = by_slide.get(row[-1], 0) + 1
        slide_summary = ", ".join(f"slide {s}: {n}" for s, n in sorted(by_slide.items(), key=lambda kv: int(kv[0])))
        print(f"\n{filename}")
        print(f"  header ({len(header)}): {header}")
        print(f"  data rows: {len(rows)}  [{slide_summary}]")
        print(f"  written: {out_path}")


if __name__ == "__main__":
    main()