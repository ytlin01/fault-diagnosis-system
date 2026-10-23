from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.ingestion.cad_2d_pipeline_v2.artifacts import sha256_file, sha256_value
from services.ingestion.cad_2d_pipeline_v2.redaction import MASK_RECTS

try:
    import pdfplumber
except ModuleNotFoundError:  # Optional local PDF-audit dependency.
    pdfplumber = None  # type: ignore[assignment]


METHOD_COMMIT = "a1bb774a467ab9fd04adf111fa026763c355eb35"
METHOD_BLOB = "4f6ac56f3cb3d4b6b8fab40b0ab8a91e795dc337"
METHOD_SCRIPT = "scripts/mask_2d_drawings.py"


def _portable(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _require_processed_path(path: Path, repository_root: Path) -> None:
    processed_root = (repository_root / "data" / "processed").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(processed_root):
        raise ValueError(
            f"Task 015 black-strip manifest reads are restricted to {processed_root}"
        )


def _overlaps(word: dict[str, Any], box: tuple[float, float, float, float]) -> bool:
    return not (
        float(word["x1"]) < box[0]
        or float(word["x0"]) > box[2]
        or float(word["bottom"]) < box[1]
        or float(word["top"]) > box[3]
    )


def _is_matching_black_curve(
    curve: dict[str, Any], box: tuple[float, float, float, float], tolerance: float = 0.05
) -> bool:
    if curve.get("fill") is not True:
        return False
    color = curve.get("non_stroking_color")
    if not isinstance(color, (list, tuple)) or len(color) < 3:
        return False
    if any(abs(float(value)) > 0.001 for value in color[:3]):
        return False
    observed = (
        float(curve.get("x0", -1)),
        float(curve.get("top", -1)),
        float(curve.get("x1", -1)),
        float(curve.get("bottom", -1)),
    )
    return all(abs(actual - expected) <= tolerance for actual, expected in zip(observed, box))


def _scan_pdf(path: Path, repository_root: Path) -> dict[str, Any]:
    if pdfplumber is None:
        raise RuntimeError(
            "pdfplumber is required; use the approved bundled PDF runtime"
        )
    stat = path.stat()
    record: dict[str, Any] = {
        "path": _portable(path, repository_root),
        "file_name": path.name,
        "source_key": path.stem.removesuffix("_masked"),
        "size_bytes": stat.st_size,
        "last_write_time_utc": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "sha256": sha256_file(path),
        "page_count": 0,
        "expected_black_rectangles": 0,
        "detected_black_rectangles": 0,
        "pages_with_complete_black_overlay": 0,
        "words_intersecting_mask_regions": 0,
        "pages_with_words_under_overlay": 0,
        "parse_error": None,
    }
    try:
        with pdfplumber.open(path) as document:
            record["page_count"] = len(document.pages)
            record["expected_black_rectangles"] = len(document.pages) * len(MASK_RECTS)
            for page in document.pages:
                words = page.extract_words() or []
                drawings = list(page.curves) + list(page.rects)
                detected = sum(
                    1
                    for box in MASK_RECTS
                    if any(_is_matching_black_curve(drawing, box) for drawing in drawings)
                )
                hidden_words = sum(
                    1 for word in words if any(_overlaps(word, box) for box in MASK_RECTS)
                )
                record["detected_black_rectangles"] += detected
                record["pages_with_complete_black_overlay"] += int(
                    detected == len(MASK_RECTS)
                )
                record["words_intersecting_mask_regions"] += hidden_words
                record["pages_with_words_under_overlay"] += int(hidden_words > 0)
    except Exception as exc:  # reason-coded evidence; never suppress the failure
        record["parse_error"] = f"{type(exc).__name__}: {exc}"
    return record


def _load_expected_keys(classification_path: Path) -> set[str]:
    payload = json.loads(classification_path.read_text(encoding="utf-8"))
    drawings = payload.get("drawings") if isinstance(payload, dict) else None
    if not isinstance(drawings, list):
        raise ValueError("classification payload must contain a drawings list")
    keys: set[str] = set()
    for index, row in enumerate(drawings):
        if not isinstance(row, dict) or not str(row.get("drawing_number", "")).strip():
            raise ValueError(f"classification drawings[{index}] has no drawing_number")
        key = str(row["drawing_number"])
        if key in keys:
            raise ValueError(f"duplicate classification drawing_number: {key}")
        keys.add(key)
    return keys


def _write_manifest(path: Path, value: Any, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if force else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_manifests(
    *,
    input_dir: Path,
    classification_path: Path,
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if pdfplumber is None:
        raise RuntimeError(
            "pdfplumber is required; use the approved bundled PDF runtime"
        )
    _require_processed_path(input_dir, repository_root)
    _require_processed_path(classification_path, repository_root)
    pdfs = sorted(input_dir.rglob("*.pdf"), key=lambda path: path.as_posix())
    if not pdfs:
        raise ValueError(f"no PDFs found in {input_dir}")

    records = [_scan_pdf(path, repository_root) for path in pdfs]
    expected_keys = _load_expected_keys(classification_path)
    observed_keys = {record["source_key"] for record in records}
    missing_keys = sorted(expected_keys - observed_keys)
    unexpected_keys = sorted(observed_keys - expected_keys)

    inventory_payload: dict[str, Any] = {
        "schema_version": "cad_2d_masked_pdf_inventory_v1",
        "task_id": "V2-TASK015",
        "sensitivity": "cad_protected_non_serving",
        "serving_safe": False,
        "input_scope": _portable(input_dir, repository_root),
        "content_scope": "processed_masked_outputs_only_raw_not_accessed",
        "records": records,
        "coverage": {
            "classification_expected_count": len(expected_keys),
            "processed_masked_pdf_count": len(records),
            "matched_expected_count": len(expected_keys & observed_keys),
            "missing_expected_count": len(missing_keys),
            "unexpected_output_count": len(unexpected_keys),
            "missing_expected_keys": missing_keys,
            "unexpected_output_keys": unexpected_keys,
        },
    }
    inventory_digest = sha256_value(inventory_payload)
    inventory_payload["inventory_sha256"] = inventory_digest

    parsed = [record for record in records if record["parse_error"] is None]
    total_pages = sum(record["page_count"] for record in parsed)
    complete_overlay_pages = sum(
        record["pages_with_complete_black_overlay"] for record in parsed
    )
    pages_with_under_text = sum(
        record["pages_with_words_under_overlay"] for record in parsed
    )
    total_under_words = sum(
        record["words_intersecting_mask_regions"] for record in parsed
    )
    total_bytes = sum(record["size_bytes"] for record in records)

    run_manifest: dict[str, Any] = {
        "schema_version": "cad_2d_black_strip_masking_run_manifest_v1",
        "task_id": "V2-TASK015",
        "manifest_state": "historical_reconstruction",
        "method_identity": "cad_tool_black_strip_overlay_v1",
        "method_family": "visual_pdf_overlay_not_n_masking_pipeline",
        "implementation": {
            "git_ref": "feature/cad_tool",
            "commit": METHOD_COMMIT,
            "script_path": METHOD_SCRIPT,
            "script_blob": METHOD_BLOB,
            "library": "PyMuPDF",
            "operation": "page.draw_rect with solid black fill",
            "template_scope": "fixed A3 landscape Di template",
            "rectangles_pdf_points_top_left": [list(rect) for rect in MASK_RECTS],
            "historical_output_convention": "data/processed/masked/masked_2d/<stem>_masked.pdf",
        },
        "permission_and_read_boundary": {
            "inspected_scope": "data/processed only",
            "raw_content_accessed": False,
            "external_transmission": False,
        },
        "output_inventory": {
            "inventory_schema_version": inventory_payload["schema_version"],
            "inventory_sha256": inventory_digest,
            "processed_masked_pdf_count": len(records),
            "total_bytes": total_bytes,
            "classification_expected_count": len(expected_keys),
            "missing_expected_count": len(missing_keys),
            "unexpected_output_count": len(unexpected_keys),
        },
        "verification": {
            "parser": f"pdfplumber {pdfplumber.__version__}",
            "parsed_file_count": len(parsed),
            "parse_error_count": len(records) - len(parsed),
            "page_count": total_pages,
            "pages_with_complete_black_overlay": complete_overlay_pages,
            "pages_without_complete_black_overlay": total_pages - complete_overlay_pages,
            "pages_with_extractable_words_intersecting_mask_regions": pages_with_under_text,
            "extractable_word_count_intersecting_mask_regions": total_under_words,
        },
        "governance_decision": {
            "masking_claim": "black strips visually cover fixed title-block regions",
            "destructive_redaction_verified": False,
            "underlying_content_removal": "not_performed_by_historical_script",
            "serving_safe": False,
            "review_status": "masking_verification_failed_visual_overlay",
            "promotion_state": "blocked",
            "required_action": (
                "rerun with destructive redaction or flatten/rasterize under an approved "
                "governed process, then verify hidden text, vectors, annotations, layers, "
                "attachments, metadata, and filename risk"
            ),
        },
    }
    unsigned_digest = sha256_value(run_manifest)
    run_manifest["manifest_id"] = f"cad2d_black_strip_{unsigned_digest[:16]}"
    run_manifest["manifest_sha256"] = sha256_value(run_manifest)
    return inventory_payload, run_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build non-serving Task 015 manifests for historical black-strip PDFs"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/processed/masked/CAD"),
    )
    parser.add_argument(
        "--classification",
        type=Path,
        default=Path(
            "data/processed/index/CAD/drawings_v1/legacy_indexes/"
            "drawing_classification.json"
        ),
    )
    parser.add_argument(
        "--inventory-out",
        type=Path,
        default=Path(
            "data/processed/index/CAD/governance/"
            "black_strip_masked_pdf_inventory.json"
        ),
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path(
            "data/processed/index/CAD/governance/"
            "black_strip_masking_run_manifest.json"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace manifests generated by an earlier reconstruction run",
    )
    args = parser.parse_args(argv)
    repository_root = Path(__file__).resolve().parents[3]
    inventory, manifest = build_manifests(
        input_dir=args.input_dir,
        classification_path=args.classification,
        repository_root=repository_root,
    )
    _write_manifest(args.inventory_out, inventory, force=args.force)
    _write_manifest(args.manifest_out, manifest, force=args.force)
    print(
        json.dumps(
            {
                "inventory_out": args.inventory_out.as_posix(),
                "manifest_out": args.manifest_out.as_posix(),
                "processed_masked_pdf_count": manifest["output_inventory"][
                    "processed_masked_pdf_count"
                ],
                "missing_expected_count": manifest["output_inventory"][
                    "missing_expected_count"
                ],
                "verification": manifest["verification"],
                "governance_decision": manifest["governance_decision"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
