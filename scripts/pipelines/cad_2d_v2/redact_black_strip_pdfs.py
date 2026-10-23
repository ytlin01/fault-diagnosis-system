from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.cad_2d_pipeline_v2.artifacts import (  # noqa: E402
    sha256_value,
)
from services.ingestion.cad_2d_pipeline_v2.redaction import (  # noqa: E402
    MASK_RECTS,
    redact_pdf,
)


def _require_input(path: Path, *, input_zone: str) -> Path:
    allowed_root = (PROJECT_ROOT / "data" / input_zone).resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_root):
        raise ValueError(
            f"{input_zone} redaction inputs must remain under {allowed_root}"
        )
    return resolved


def _require_processed(path: Path) -> Path:
    processed = (PROJECT_ROOT / "data" / "processed").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(processed):
        raise ValueError(f"redaction outputs must remain under {processed}")
    return resolved


def _portable(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Destructively redact Task015 black-strip regions in processed PDFs"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        action="append",
        dest="input_dirs",
        help=(
            "Processed input partition; repeat for multiple partitions. "
            "Defaults to masked_2d and masked_2d_review only."
        ),
    )
    parser.add_argument(
        "--input-zone",
        choices=("processed", "raw"),
        default="processed",
        help=(
            "Governed source zone. Raw mode must be selected explicitly and requires "
            "one or more --input-dir values."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "data/processed/masked/CAD/"
            "v2_task015_destructive_redaction_v1"
        ),
    )
    parser.add_argument(
        "--inventory-out",
        type=Path,
        default=Path(
            "data/processed/masked/CAD/"
            "v2_task015_destructive_redaction_v1/_lineage/"
            "destructive_redaction_inventory_v1.json"
        ),
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=Path(
            "data/processed/masked/CAD/"
            "v2_task015_destructive_redaction_v1/_manifests/"
            "destructive_redaction_run_manifest_v1.json"
        ),
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    if args.input_zone == "raw" and not args.input_dirs:
        raise ValueError("raw input mode requires an explicit --input-dir")
    requested_input_dirs = args.input_dirs or [
        Path("data/processed/masked/CAD/masked_2d"),
        Path("data/processed/masked/CAD/masked_2d_review"),
    ]
    input_dirs = tuple(
        _require_input(path, input_zone=args.input_zone)
        for path in requested_input_dirs
    )
    output_dir = _require_processed(args.output_dir)
    inventory_out = _require_processed(args.inventory_out)
    manifest_out = _require_processed(args.manifest_out)
    source_items = sorted(
        (
            (source, Path(input_dir.name) / source.relative_to(input_dir))
            for input_dir in input_dirs
            for source in input_dir.rglob("*.pdf")
        ),
        key=lambda item: item[1].as_posix(),
    )
    if not source_items:
        raise ValueError("no processed PDFs found")
    if len({relative.as_posix() for _, relative in source_items}) != len(source_items):
        raise ValueError("input partitions produce duplicate relative output paths")
    if any(
        output_dir == input_dir or output_dir.is_relative_to(input_dir)
        for input_dir in input_dirs
    ):
        raise ValueError("output directory must not be inside an input directory")

    preview = {
        "mode": "write" if args.write else "preview",
        "input_dirs": [_portable(path) for path in input_dirs],
        "input_zone": args.input_zone,
        "output_dir": _portable(output_dir),
        "input_pdf_count": len(source_items),
        "rectangles_pdf_points_top_left": [list(rect) for rect in MASK_RECTS],
        "raw_content_accessed": bool(args.write and args.input_zone == "raw"),
        "serving_safe": False,
        "graph_activation": False,
    }
    if not args.write:
        print(json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if output_dir.exists() or inventory_out.exists() or manifest_out.exists():
        raise FileExistsError("output, inventory, or manifest already exists")

    records = []
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        for source, relative in source_items:
            destination = output_dir / relative.parent / f"{source.stem}_redacted.pdf"
            result = redact_pdf(source, destination)
            records.append(
                {
                    "source_path": _portable(source),
                    "output_path": _portable(destination),
                    **result,
                }
            )
    except Exception:
        (output_dir / "_INCOMPLETE_DO_NOT_USE").write_text(
            "Redaction run failed. This directory is non-serving and incomplete.\n",
            encoding="utf-8",
        )
        raise

    inventory = {
        "schema_version": "cad_2d_destructive_redaction_inventory_v1",
        "task_id": "V2-TASK015",
        "run_state": "candidate_verified_locally",
        "sensitivity": "confidential_engineering_redacted_candidate",
        "serving_safe": False,
        "input_zone": args.input_zone,
        "input_scopes": [_portable(path) for path in input_dirs],
        "raw_content_accessed": args.input_zone == "raw",
        "output_scope": _portable(output_dir),
        "records": records,
    }
    inventory["inventory_sha256"] = sha256_value(inventory)
    total_pages = sum(record["verification"]["page_count"] for record in records)
    manifest = {
        "schema_version": "cad_2d_destructive_redaction_run_manifest_v1",
        "task_id": "V2-TASK015",
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "method": {
            "library": "PyMuPDF",
            "operation": "add_redact_annot_then_apply_redactions",
            "full_rewrite": True,
            "garbage_collection": 4,
            "document_scrub": True,
            "rectangles_pdf_points_top_left": [list(rect) for rect in MASK_RECTS],
        },
        "input_pdf_count": len(source_items),
        "output_pdf_count": len(records),
        "page_count": total_pages,
        "words_intersecting_before": sum(
            record["words_intersecting_before"] for record in records
        ),
        "words_intersecting_after": sum(
            record["verification"]["words_intersecting_redactions"]
            for record in records
        ),
        "minimum_redaction_black_ratio": min(
            record["verification"]["minimum_redaction_black_ratio"]
            for record in records
        ),
        "failed_output_count": sum(
            not record["verification"]["passed"] for record in records
        ),
        "annotation_count_after": sum(
            record["verification"]["annotation_count"] for record in records
        ),
        "widget_count_after": sum(
            record["verification"]["widget_count"] for record in records
        ),
        "embedded_file_count_after": sum(
            record["verification"]["embedded_file_count"] for record in records
        ),
        "optional_content_group_count_after": sum(
            record["verification"]["optional_content_group_count"]
            for record in records
        ),
        "metadata_value_count_after": sum(
            record["verification"]["metadata_value_count"] for record in records
        ),
        "inventory_sha256": inventory["inventory_sha256"],
        "permission_boundary": {
            "input_zone": args.input_zone,
            "processed_content_only": args.input_zone == "processed",
            "raw_content_accessed": args.input_zone == "raw",
            "external_transmission": False,
        },
        "governance_decision": {
            "serving_safe": False,
            "promotion_state": "pending_independent_visual_and_security_review",
            "graph_activation": False,
        },
    }
    manifest["manifest_sha256"] = sha256_value(manifest)
    _write_exclusive(inventory_out, inventory)
    _write_exclusive(manifest_out, manifest)
    print(
        json.dumps(
            {
                **preview,
                "inventory_out": _portable(inventory_out),
                "manifest_out": _portable(manifest_out),
                "output_pdf_count": len(records),
                "page_count": total_pages,
                "words_intersecting_before": manifest["words_intersecting_before"],
                "words_intersecting_after": manifest["words_intersecting_after"],
                "failed_output_count": manifest["failed_output_count"],
                "minimum_redaction_black_ratio": manifest[
                    "minimum_redaction_black_ratio"
                ],
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
