"""CLI for first-pass unstructured document ingestion.

Examples:
    python scripts/ingest/run_ingest_unstructured.py --synthetic --dry-run
    python scripts/ingest/run_ingest_unstructured.py --input-file data/raw/documents/demo.docx --dry-run
    python scripts/ingest/run_ingest_unstructured.py --input-dir data/raw/documents

The command writes canonical block JSON only when not in dry-run mode. Raw
assets stay in data/raw or another controlled local/processed asset directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.canonical_document import (
    SUPPORTED_EXTENSIONS,
    build_canonical_document,
    build_synthetic_canonical_document,
    write_canonical_document,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FaultDx unstructured document ingestion preview"
    )
    parser.add_argument(
        "--input-file",
        help="Single docx/pptx/pdf/text/json/3D source to register or parse.",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Directory containing source documents. Raw directories must remain untracked.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "processed" / "unstructured"),
        help="Directory for canonical block JSON output.",
    )
    parser.add_argument(
        "--asset-output-dir",
        default=str(PROJECT_ROOT / "data" / "processed" / "unstructured_assets"),
        help="Directory for extracted Office image assets. Not used during dry-run.",
    )
    parser.add_argument(
        "--no-extract-office-assets",
        action="store_true",
        help="Keep DOCX/PPTX media as placeholders instead of extracting image files.",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Emit a synthetic canonical document covering text/table/image/chart/3D blocks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print canonical JSON without writing output files.",
    )
    parser.add_argument(
        "--apply-name-mapping",
        action="store_true",
        help="Apply local name_mapping.xlsx content rules after reading.",
    )
    parser.add_argument(
        "--name-mapping-file",
        default=None,
        help="Optional local name_mapping.xlsx path. Overrides discovery.",
    )
    parser.add_argument(
        "--name-mapping-text-mode",
        choices=("contains", "configured"),
        default="contains",
        help="How content name_mapping rules apply to unstructured text. Default: contains.",
    )
    parser.add_argument(
        "--no-vlm-candidates",
        action="store_true",
        help="Do not mark image/chart/3D blocks as local VLM enrichment candidates.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    documents = []

    if args.synthetic:
        documents.append(build_synthetic_canonical_document())
    else:
        input_paths = _resolve_input_paths(args)
        registry = None
        if args.apply_name_mapping:
            from services.ingestion.name_mapping import load_name_mapping, resolve_name_mapping_path

            mapping_path = resolve_name_mapping_path(
                input_paths[0].parent,
                Path(args.name_mapping_file) if args.name_mapping_file else None,
            )
            registry = load_name_mapping(mapping_path)

        source_root = Path(args.input_dir).resolve() if args.input_dir else input_paths[0].parent
        asset_output_root = None
        if not args.dry_run and not args.no_extract_office_assets:
            asset_output_root = Path(args.asset_output_dir)
        for input_path in input_paths:
            documents.append(build_canonical_document(
                input_path,
                source_root=source_root,
                asset_output_root=asset_output_root,
                name_mapping_registry=registry,
                mark_vlm_candidates=not args.no_vlm_candidates,
                name_mapping_text_mode=args.name_mapping_text_mode,
            ))

    if args.dry_run:
        print(json.dumps(_preview_payload(documents), ensure_ascii=False, indent=2))
        return

    written = [str(write_canonical_document(document, output_dir)) for document in documents]
    print(json.dumps({"written": written, "count": len(written)}, ensure_ascii=False, indent=2))


def _resolve_input_paths(args: argparse.Namespace) -> list[Path]:
    if args.input_file:
        path = Path(args.input_file)
        if not path.exists():
            raise FileNotFoundError(f"input file not found: {path}")
        return [path]

    if not args.input_dir:
        raise ValueError("Use --synthetic, --input-file, or --input-dir.")

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    all_paths = [
        path for path in sorted(input_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    mineru_primary = _select_mineru_primary_outputs(all_paths)
    mineru_stems = {_strip_mineru_suffix(path.stem) for path in mineru_primary}

    paths: list[Path] = []
    selected_primary = set(mineru_primary)
    for path in all_paths:
        if path in selected_primary:
            paths.append(path)
            continue
        if _is_mineru_auxiliary_output(path):
            continue
        if path.suffix.lower() == ".pdf" and path.stem in mineru_stems:
            continue
        if _has_selected_mineru_primary(path, selected_primary):
            continue
        paths.append(path)

    deduped = list(dict.fromkeys(paths))
    if not deduped:
        raise FileNotFoundError(
            f"no supported unstructured sources found under {input_dir}"
        )
    return deduped


def _select_mineru_primary_outputs(paths: list[Path]) -> list[Path]:
    grouped: dict[Path, list[Path]] = {}
    for path in paths:
        if _is_mineru_primary_candidate(path):
            grouped.setdefault(path.parent, []).append(path)

    selected: list[Path] = []
    for candidates in grouped.values():
        selected.append(sorted(candidates, key=_mineru_primary_rank)[0])
    return selected


def _is_mineru_primary_candidate(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.endswith("_content_list_v2.json")
        or name.endswith("_content_list.json")
        or (path.suffix.lower() == ".md" and any(parent.name.lower() == "auto" for parent in path.parents))
    )


def _mineru_primary_rank(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if name.endswith("_content_list_v2.json"):
        return (0, name)
    if name.endswith("_content_list.json"):
        return (1, name)
    if path.suffix.lower() == ".md":
        return (2, name)
    return (9, name)


def _is_mineru_auxiliary_output(path: Path) -> bool:
    name = path.name.lower()
    if not any(parent.name.lower() == "auto" for parent in path.parents):
        return False
    return (
        name.endswith("_middle.json")
        or name.endswith("_model.json")
        or name.endswith("_origin.json")
        or name.endswith("_span.json")
        or name.endswith("_layout.pdf")
        or name.endswith("_origin.pdf")
        or name.endswith("_span.pdf")
        or name.endswith("_content_list.json")
        or name.endswith(".md")
    )


def _has_selected_mineru_primary(path: Path, selected_primary: set[Path]) -> bool:
    return any(primary.parent == path.parent for primary in selected_primary)


def _strip_mineru_suffix(stem: str) -> str:
    for suffix in ("_content_list_v2", "_content_list", "_middle", "_model", "_origin", "_span", "_layout"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _preview_payload(documents: list[dict]) -> dict:
    return {
        "mode": "dry-run",
        "document_count": len(documents),
        "documents": documents,
    }


if __name__ == "__main__":
    main()

