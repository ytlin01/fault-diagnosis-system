from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.cad_2d_pipeline_v2.artifacts import (  # noqa: E402
    build_manifest,
    sha256_file,
    sha256_value,
    write_json_pair_exclusive,
)
from services.ingestion.cad_2d_pipeline_v2 import (  # noqa: E402
    load_config,
    validate_projection_semantics,
)


DEFAULT_SOURCE = Path(
    "data/processed/review_pending/route_a/"
    "v2_task015_cad_2d_manual_classification_review_v1/"
    "manual_classification_review_v1.json"
)
DEFAULT_PROJECTION = Path(
    "data/processed/review_pending/route_a/"
    "v2_task015_cad_2d_manual_classification_review_v2/"
    "manual_classification_review_v2.json"
)


def _require_processed(path: Path) -> Path:
    processed = (PROJECT_ROOT / "data" / "processed").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(processed):
        raise ValueError("reviewed ASM extraction paths must remain under data/processed")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract local word geometry from reviewed Task 015 ASM PDFs"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--projection", type=Path, default=DEFAULT_PROJECTION)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/pipelines/cad_2d_pipeline_v2.yaml")
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    source_path = _require_processed(args.source)
    projection_path = _require_processed(args.projection)
    config = load_config(args.config)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    source_sha256 = sha256_file(source_path)
    projection_sha256 = sha256_file(projection_path)
    expected_lineage = config["bom"].get("reviewed_word_bundle_lineage", {})
    if (
        expected_lineage.get("source_review_file_sha256") != source_sha256
        or expected_lineage.get("projection_file_sha256") != projection_sha256
        or
        source.get("schema_version") != "cad_2d_manual_classification_review_v1"
        or source.get("task_id") != "V2-TASK015"
        or projection.get("schema_version")
        != "cad_2d_manual_classification_review_v2"
        or projection.get("task_id") != "V2-TASK015"
        or projection.get("review_state") != "human_decisions_complete"
        or not isinstance(projection.get("source_review"), dict)
        or projection["source_review"].get("schema_version")
        != source.get("schema_version")
        or projection["source_review"].get("artifact_sha256") != source_sha256
    ):
        raise ValueError("projection is not bound to the immutable source review")
    validate_projection_semantics(projection)
    page_index = int(config["bom"]["page_index"])

    source_by_id = {
        str(row.get("part_number") or "").strip(): row
        for row in source.get("records", [])
    }
    asm_records = [
        row for row in projection.get("records", []) if row.get("decision") == "asm"
    ]
    if len(source_by_id) != len(source.get("records", [])):
        raise ValueError("source review identifiers are blank or duplicated")
    projected_by_id = {
        str(row.get("source_record_id") or "").strip(): row
        for row in projection.get("records", [])
    }
    if (
        len(projected_by_id) != len(projection.get("records", []))
        or set(projected_by_id) != set(source_by_id)
    ):
        raise ValueError("projection records disagree with immutable source review")
    for source_id, source_record in source_by_id.items():
        projected = projected_by_id[source_id]
        if (
            projected.get("decision") != source_record.get("decision")
            or projected.get("sequence") != source_record.get("sequence")
            or projected.get("source_pdf_sha256")
            != source_record.get("pdf_sha256")
        ):
            raise ValueError("projection decision or evidence disagrees with source review")
    output_records = []
    exclusions = []
    for record_index, projected in enumerate(asm_records):
        source_record = source_by_id.get(projected.get("source_record_id"))
        if source_record is None:
            raise ValueError("reviewed ASM is absent from immutable source review")
        if source_record.get("pdf_sha256") != projected.get("source_pdf_sha256"):
            raise ValueError("projection PDF digest disagrees with source review")
        pdf_path = _require_processed(Path(source_record["review_pdf_path"]))
        if not pdf_path.is_file() or sha256_file(pdf_path) != projected.get(
            "source_pdf_sha256"
        ):
            raise ValueError("reviewed ASM PDF is missing or failed digest verification")
        with fitz.open(pdf_path) as document:
            if page_index >= document.page_count:
                exclusions.append(
                    {
                        "reason_code": "BOM_PAGE_UNAVAILABLE",
                        "record_index": record_index,
                        "parent_part_number": projected["source_record_id"],
                    }
                )
                continue
            raw_words = document[page_index].get_text("words")
            words = [
                [
                    float(word[0]),
                    float(word[1]),
                    float(word[2]),
                    float(word[3]),
                    str(word[4]),
                ]
                for word in raw_words
                if len(word) >= 5 and str(word[4]).strip()
            ]
            output_records.append(
                {
                    "part_number": projected["source_record_id"],
                    "source_pdf_sha256": projected["source_pdf_sha256"],
                    "page_index": page_index,
                    "page_count": document.page_count,
                    "words": words,
                    "extraction_state": "local_reviewed_asm_word_geometry",
                }
            )

    bundle = {
        "schema_version": "cad_2d_reviewed_asm_words_v1",
        "records": output_records,
        "audit": {
            "stage": "B00",
            "reviewed_asm_count": len(asm_records),
            "output_document_count": len(output_records),
            "exclusion_count": len(exclusions),
            "total_word_count": sum(len(row["words"]) for row in output_records),
            "page_index": page_index,
            "raw_zone_content_accessed": False,
            "processed_pdf_content_accessed": True,
            "external_transmission": False,
        },
        "exclusions": exclusions,
    }
    if sha256_value(bundle) != expected_lineage.get("b00_bundle_result_sha256"):
        raise ValueError("B00 output disagrees with governed bundle digest")
    manifest = build_manifest(
        stage="B00",
        config=config,
        inputs={
            "source_review_sha256": source_sha256,
            "projection_sha256": projection_sha256,
            "page_index": page_index,
        },
        result=bundle,
    )
    preview = {
        "mode": "write" if args.write else "preview",
        "audit": bundle["audit"],
        "manifest": manifest,
        "serving_safe": False,
        "kg_ingestion_eligible": False,
    }
    print(json.dumps(preview, indent=2, sort_keys=True))
    if not args.write:
        return 0
    if args.out is None or args.manifest_out is None:
        parser.error("--write requires --out and --manifest-out")
    write_json_pair_exclusive(
        _require_processed(args.out),
        bundle,
        _require_processed(args.manifest_out),
        manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
