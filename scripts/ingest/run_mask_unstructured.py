"""Entry point for the unstructured document masking pipeline.

Reads MinerU extraction results or canonical block JSON, applies local regex
masking patterns, and writes controlled canonical and serving artifacts.

Examples:
    python scripts/ingest/run_mask_unstructured.py --input-dir data/raw/minerU_output --dry-run
    python scripts/ingest/run_mask_unstructured.py --file data/processed/unstructured/demo_canonical.json
    python scripts/ingest/run_mask_unstructured.py --file demo.json --canonical-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.governance._operation_log import safe_repo_path
from services.ingestion.lineage import LineageWriter
from services.ingestion.manifest import build_manifest, make_run_id, write_manifest
from services.ingestion.masking_engine import load_rules
from services.ingestion.unstructured import (
    build_serving_payload,
    compile_patterns,
    detect_format,
    read_and_mask_file,
    sanitize_masked_canonical_payload,
    summarize_match_records,
    write_masked_payload,
)


SUPPORTED_INPUT_SUFFIXES = {".json", ".md", ".markdown", ".txt"}


def _load_dotenv() -> None:
    """Load .env file if present (simple key=value parser, no dependency)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key not in os.environ:
                os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FaultDx unstructured document masking pipeline"
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "configs" / "masking_rules.yaml"),
        help="Path to masking_rules.yaml",
    )
    parser.add_argument(
        "--input-dir",
        default=str(PROJECT_ROOT / "data" / "raw" / "minerU_output"),
        help="Directory containing MinerU or canonical unstructured output",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Process a single file instead of the whole input directory",
    )
    parser.add_argument(
        "--canonical-output-dir",
        default=None,
        help=(
            "Masked internal canonical output directory. Defaults to "
            "data/processed/masked/unstructured/vlm for VLM inputs, otherwise "
            "data/processed/masked/unstructured."
        ),
    )
    parser.add_argument(
        "--serving-output-dir",
        default=None,
        help=(
            "Masked external serving output directory. Defaults to "
            "data/processed/serving/unstructured for serving-safe outputs."
        ),
    )
    parser.add_argument(
        "--manifest-dir",
        default=str(PROJECT_ROOT / "data" / "processed" / "canonical" / "unstructured" / "_manifests"),
        help="Manifest output directory",
    )
    parser.add_argument(
        "--lineage-dir",
        default=str(PROJECT_ROOT / "data" / "processed" / "canonical" / "unstructured" / "_lineage"),
        help="Lineage output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview matches and serving policy without writing files",
    )
    parser.add_argument(
        "--canonical-only",
        action="store_true",
        help="Write/preview canonical only and suppress serving output",
    )
    return parser.parse_args()


def main() -> None:
    _load_dotenv()
    args = parse_args()
    rules = load_rules(Path(args.config))
    patterns = compile_patterns(rules)
    run_id = make_run_id()
    input_files = _resolve_input_files(args)
    canonical_output_dir, serving_output_dir = _resolve_output_dirs(args, input_files)

    results: list[dict[str, Any]] = []
    for input_file in input_files:
        masked_payload, records, source_format = read_and_mask_file(input_file, patterns)
        masked_payload, canonical_policy = sanitize_masked_canonical_payload(masked_payload)
        serving_payload, serving_policy = build_serving_payload(
            masked_payload,
            canonical_only=args.canonical_only,
        )
        result = {
            "input_file": str(input_file),
            "format": source_format,
            "match_summary": summarize_match_records(records),
            "canonical_policy": canonical_policy,
            "serving_policy": serving_policy,
            "canonical_output": None,
            "serving_output": None,
        }

        if not args.dry_run:
            canonical_path = _output_path(
                canonical_output_dir,
                input_file,
                suffix="canonical",
                source_format=source_format,
            )
            write_masked_payload(masked_payload, canonical_path, source_format)
            result["canonical_output"] = str(canonical_path)

            if serving_payload is not None:
                serving_path = _output_path(
                    serving_output_dir,
                    input_file,
                    suffix="serving",
                    source_format=source_format,
                )
                write_masked_payload(serving_payload, serving_path, source_format)
                result["serving_output"] = str(serving_path)

        results.append(result)

    if args.dry_run:
        print(json.dumps({
            "mode": "dry-run",
            "patterns_loaded": len(patterns),
            "output_dirs": {
                "canonical": str(canonical_output_dir),
                "serving": str(serving_output_dir),
            },
            "files": results,
        }, ensure_ascii=False, indent=2))
        return

    manifest_results = []
    for result in results:
        portable_result = dict(result)
        for path_field in ("input_file", "canonical_output", "serving_output"):
            portable_result[path_field] = safe_repo_path(
                result.get(path_field),
                PROJECT_ROOT,
            )
        manifest_results.append(portable_result)
    lineage_path = _write_lineage(
        manifest_results,
        Path(args.lineage_dir),
        run_id=run_id,
    )
    manifest = build_manifest(
        run_id=run_id,
        source_name="unstructured",
        rules_version=int(rules.get("version", 0)),
        input_files=input_files,
        input_file_labels=[safe_repo_path(path, PROJECT_ROOT) for path in input_files],
        input_row_count=len(input_files),
        input_col_count=0,
        output_canonical_path=safe_repo_path(canonical_output_dir, PROJECT_ROOT),
        output_serving_path=safe_repo_path(serving_output_dir, PROJECT_ROOT),
        output_row_count=len(results),
        output_col_count_canonical=0,
        output_col_count_serving=0,
        review_flag_columns=[],
        extra={
            "file_results": manifest_results,
            "lineage_path": safe_repo_path(lineage_path, PROJECT_ROOT),
            "canonical_only_requested": args.canonical_only,
        },
    )
    manifest_path = write_manifest(manifest, Path(args.manifest_dir))
    from services.governance.masking_log import record as record_masking_run

    for result in results:
        input_path = Path(result["input_file"])
        record_masking_run(
            source_id=input_path.stem,
            run_id=run_id,
            masking_source_name="unstructured",
            input_source_id=input_path.stem,
            rules_version=rules.get("version", 0),
            masking_action="unstructured_masking",
            input_path=safe_repo_path(input_path, PROJECT_ROOT),
            output_canonical_path=safe_repo_path(
                result["canonical_output"], PROJECT_ROOT
            ),
            output_serving_path=safe_repo_path(result["serving_output"], PROJECT_ROOT),
            manifest_path=safe_repo_path(manifest_path, PROJECT_ROOT),
            lineage_path=safe_repo_path(lineage_path, PROJECT_ROOT),
        )
    print(json.dumps({
        "processed_files": len(results),
        "manifest": str(manifest_path),
        "lineage": str(lineage_path),
        "output_dirs": {
            "canonical": str(canonical_output_dir),
            "serving": str(serving_output_dir),
        },
        "results": results,
    }, ensure_ascii=False, indent=2))


def _resolve_input_files(args: argparse.Namespace) -> list[Path]:
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            raise FileNotFoundError(f"input file not found: {file_path}")
        return [file_path]

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    files = [
        path for path in sorted(input_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES
    ]
    if not files:
        raise FileNotFoundError(
            f"no JSON/Markdown/TXT files found under {input_dir}"
        )
    return files


def _resolve_output_dirs(args: argparse.Namespace, input_files: list[Path]) -> tuple[Path, Path]:
    is_vlm_input = any(_is_vlm_input_path(path) for path in input_files)
    if args.canonical_output_dir:
        canonical_output_dir = Path(args.canonical_output_dir)
    elif is_vlm_input:
        canonical_output_dir = PROJECT_ROOT / "data" / "processed" / "masked" / "unstructured" / "vlm"
    else:
        canonical_output_dir = PROJECT_ROOT / "data" / "processed" / "masked" / "unstructured"

    if args.serving_output_dir:
        serving_output_dir = Path(args.serving_output_dir)
    elif is_vlm_input:
        serving_output_dir = PROJECT_ROOT / "data" / "processed" / "serving" / "unstructured"
    else:
        serving_output_dir = PROJECT_ROOT / "data" / "processed" / "serving" / "unstructured"

    return canonical_output_dir, serving_output_dir


def _output_path(output_dir: Path, input_file: Path, *, suffix: str, source_format: str) -> Path:
    extension = ".json" if source_format == "json" else input_file.suffix
    stem = _output_stem(input_file.stem, suffix=suffix)
    return output_dir / f"{stem}{extension}"


def _output_stem(input_stem: str, *, suffix: str) -> str:
    if input_stem.endswith("_canonical_vlm"):
        base = input_stem[: -len("_canonical_vlm")]
        return f"{base}_vlm_masked_{suffix}"
    if input_stem.endswith("_canonical"):
        base = input_stem[: -len("_canonical")]
        return f"{base}_masked_{suffix}"
    return f"{input_stem}_{suffix}"


def _is_vlm_input_path(path: Path) -> bool:
    normalized_parts = {part.lower() for part in path.parts}
    return "unstructured_vlm" in normalized_parts or path.stem.endswith("_canonical_vlm")


def _write_lineage(
    results: list[dict[str, Any]],
    lineage_dir: Path,
    *,
    run_id: str,
) -> Path:
    with LineageWriter("unstructured", lineage_dir, run_id=run_id) as writer:
        for row_index, result in enumerate(results):
            for pattern_name, pattern_summary in result["match_summary"]["patterns"].items():
                writer.record(
                    row_index=row_index,
                    column_name=pattern_name,
                    level="pattern",
                    action=pattern_summary.get("action", "unknown"),
                    detail=f"matches={pattern_summary.get('matches', 0)}; file={result['input_file']}",
                    view="canonical_and_serving",
                    review_flag=False,
                )
            if result["serving_policy"].get("serving_generated") is not True:
                writer.record(
                    row_index=row_index,
                    column_name="serving_policy",
                    level="policy",
                    action="canonical_only",
                    detail=result["serving_policy"].get("reason") or "serving suppressed",
                    view="serving",
                    review_flag=True,
                )
    return writer.path


if __name__ == "__main__":
    main()
