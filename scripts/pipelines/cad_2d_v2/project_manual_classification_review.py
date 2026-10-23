from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.cad_2d_pipeline_v2.manual_review import (  # noqa: E402
    project_completed_review,
    validate_projection_semantics,
)
from services.ingestion.cad_2d_pipeline_v2.artifacts import (  # noqa: E402
    sha256_file,
    sha256_value,
    write_json_pair_exclusive,
)


DEFAULT_SOURCE = Path(
    "data/processed/review_pending/route_a/"
    "v2_task015_cad_2d_manual_classification_review_v1/"
    "manual_classification_review_v1.json"
)
def _require_processed(path: Path) -> Path:
    processed = (PROJECT_ROOT / "data" / "processed").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(processed):
        raise ValueError("manual-review source/output must remain under data/processed")
    return resolved


def _verify_source_pdfs(source: object) -> set[str]:
    if not isinstance(source, dict) or not isinstance(source.get("records"), list):
        raise ValueError("source review records must be a list")
    verified: set[str] = set()
    for record in source["records"]:
        if not isinstance(record, dict):
            raise ValueError("source review record must be an object")
        path_value = record.get("review_pdf_path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("source review record is missing review_pdf_path")
        pdf_path = _require_processed(Path(path_value))
        if not pdf_path.is_file():
            raise ValueError("source review PDF is missing")
        actual = sha256_file(pdf_path)
        if actual != record.get("pdf_sha256"):
            raise ValueError("source review PDF digest mismatch")
        verified.add(actual)
    return verified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project immutable Task 015 v1 decisions into governed v2 records"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--identity-overrides", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    source_path = _require_processed(args.source)
    override_path = _require_processed(args.identity_overrides)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    overrides = json.loads(override_path.read_text(encoding="utf-8"))
    if not isinstance(overrides, list):
        raise ValueError("identity-overrides JSON must be a list")
    projection = project_completed_review(
        source,
        source_artifact_sha256=sha256_file(source_path),
        expected_source_artifact_sha256=args.expected_source_sha256,
        verified_pdf_digests=_verify_source_pdfs(source),
        identity_overrides=overrides,
    )
    validate_projection_semantics(projection)

    preview = {
        "mode": "write" if args.write else "preview",
        "record_count": len(projection["records"]),
        "decision_counts": {
            decision: sum(
                row["decision"] == decision for row in projection["records"]
            )
            for decision in ("asm", "prt", "exclude", "unresolved")
        },
        "shared_definition_record_count": sum(
            row["identity_basis"] == "explicit_reviewed_view_group"
            for row in projection["records"]
        ),
        "multi_page_record_count": sum(
            (row.get("view_grouping") or {}).get("rule") == "multi_page_document"
            for row in projection["records"]
        ),
        "projection_sha256": sha256_value(projection),
        "serving_safe": False,
        "kg_ingestion_eligible": False,
        "graph_activation": False,
    }
    print(json.dumps(preview, indent=2, sort_keys=True))
    if not args.write:
        return 0
    if args.out is None or args.manifest_out is None:
        parser.error("--write requires --out and --manifest-out")
    output_path = _require_processed(args.out)
    manifest_path = _require_processed(args.manifest_out)
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError("projection output or manifest already exists")
    output_bytes = (
        json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    manifest = {
        **preview,
        "schema_version": "cad_2d_manual_classification_projection_manifest_v2",
        "task_id": "V2-TASK015",
        "source_artifact_sha256": args.expected_source_sha256,
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
    }
    write_json_pair_exclusive(output_path, projection, manifest_path, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
