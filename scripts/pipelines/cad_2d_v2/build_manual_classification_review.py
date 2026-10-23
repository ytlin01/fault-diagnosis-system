from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.cad_2d_pipeline_v2.artifacts import (  # noqa: E402
    sha256_file,
    sha256_value,
)
from services.ingestion.cad_2d_pipeline_v2.review_queue import (  # noqa: E402
    build_manual_classification_records,
)


DEFAULT_HANDOFF = Path(
    "data/processed/review_pending/route_a/"
    "v2_task015_cad_2d_cleaned_handoff/cad2d_handoff_b5e6f06e"
)
DEFAULT_PDF_ROOT = Path(
    "data/processed/masked/CAD/v2_task015_destructive_redaction_v1"
)
DEFAULT_OUTPUT = Path(
    "data/processed/review_pending/route_a/"
    "v2_task015_cad_2d_manual_classification_review_v1"
)


def _require_processed(path: Path) -> Path:
    processed = (PROJECT_ROOT / "data" / "processed").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(processed):
        raise ValueError(f"review paths must remain under {processed}")
    return resolved


def _portable(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the Task015 A02-only manual classification review package"
    )
    parser.add_argument("--handoff-root", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    handoff_root = _require_processed(args.handoff_root)
    pdf_root = _require_processed(args.pdf_root)
    output_dir = _require_processed(args.output_dir)
    if output_dir == handoff_root or output_dir == pdf_root:
        raise ValueError("review output must be separate from its inputs")

    classification_path = (
        handoff_root
        / "run_results/intermediate_json/A01_classification/drawing_class_merged.json"
    )
    title_fields_path = (
        handoff_root
        / "run_results/intermediate_json/A02_title_fields/title_fields.json"
    )
    classifications = json.loads(classification_path.read_text(encoding="utf-8"))
    title_fields = json.loads(title_fields_path.read_text(encoding="utf-8"))
    records = build_manual_classification_records(
        classifications,
        title_fields,
        pdf_root.rglob("*.pdf"),
    )
    preview = {
        "mode": "write" if args.write else "preview",
        "output_dir": _portable(output_dir),
        "review_record_count": len(records),
        "missing_title_count": sum(not record["drawing_title"] for record in records),
        "missing_project_count": sum(
            not record["project_name"] for record in records
        ),
        "source_partitions": sorted({record["source_partition"] for record in records}),
        "raw_content_accessed": False,
        "serving_safe": False,
    }
    if not args.write:
        print(json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if output_dir.exists():
        raise FileExistsError(f"review output already exists: {output_dir}")

    pdf_output = output_dir / "pdfs"
    pdf_output.mkdir(parents=True, exist_ok=False)
    queue_records = []
    for record in records:
        source_pdf = record.pop("source_pdf")
        destination = pdf_output / source_pdf.name
        if destination.exists():
            raise ValueError("review PDF filenames are not unique")
        shutil.copyfile(source_pdf, destination)
        source_sha = sha256_file(source_pdf)
        if sha256_file(destination) != source_sha:
            raise ValueError("copied review PDF failed digest verification")
        queue_records.append(
            {
                **record,
                "source_pdf_path": _portable(source_pdf),
                "review_pdf_path": _portable(destination),
                "pdf_sha256": source_sha,
            }
        )

    queue = {
        "schema_version": "cad_2d_manual_classification_review_v1",
        "task_id": "V2-TASK015",
        "review_state": "pending_human_decisions",
        "allowed_decisions": ["asm", "prt", "exclude", "unresolved"],
        "instructions": (
            "Open each review_pdf_path and fill decision, confidence, reviewer, "
            "review_reason, and reviewed_at. Do not alter part_number or PDF paths."
        ),
        "records": queue_records,
    }
    queue["template_sha256"] = sha256_value(queue)
    queue_path = output_dir / "manual_classification_review_v1.json"
    _write_json(queue_path, queue)

    instructions = """# V2-TASK015 manual ASM/PRT review

Review all PDFs under `pdfs/`. Record decisions in
`manual_classification_review_v1.json` using `asm`, `prt`, `exclude`, or
`unresolved`. Use `exclude` only with a review reason; empty drawings must use
the exact human review reason `empty drawing`.

For `asm`, `prt`, and `unresolved`, fill `confidence`, `reviewer`,
`review_reason`, and `reviewed_at`. For `exclude`, leave confidence empty and
fill reviewer, review reason, and reviewed_at. Do not edit `part_number`, paths,
or PDF hashes. Missing title or project values are valid review observations;
do not invent them.

This package is confidential, non-serving, and not KG-ingestion eligible.
"""
    (output_dir / "REVIEW_INSTRUCTIONS.md").write_text(
        instructions, encoding="utf-8", newline="\n"
    )
    manifest = {
        "schema_version": "cad_2d_manual_classification_review_manifest_v1",
        "task_id": "V2-TASK015",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification_input": _portable(classification_path),
        "classification_input_sha256": sha256_file(classification_path),
        "title_fields_input": _portable(title_fields_path),
        "title_fields_input_sha256": sha256_file(title_fields_path),
        "pdf_input_root": _portable(pdf_root),
        "output_root": _portable(output_dir),
        "review_record_count": len(queue_records),
        "copied_pdf_count": len(queue_records),
        "missing_title_count": preview["missing_title_count"],
        "missing_project_count": preview["missing_project_count"],
        "template_sha256": queue["template_sha256"],
        "copy_digest_verification": "passed",
        "raw_content_accessed": False,
        "serving_safe": False,
        "kg_ingestion_eligible": False,
    }
    manifest["manifest_sha256"] = sha256_value(manifest)
    _write_json(output_dir / "_manifest.json", manifest)
    print(json.dumps({**preview, "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
