"""Entry point — Structured data masking pipeline.

Usage:
    # Dry-run (preview headers + first N rows, no files written):
    python scripts/ingest/run_mask_structured.py --source y25_downtime --dry-run
    python scripts/ingest/run_mask_structured.py --source y25_downtime --dry-run --rows 10

    # Full run (writes canonical + serving JSON, manifest, lineage):
    python scripts/ingest/run_mask_structured.py --source y25_downtime

    # Enable local name mapping before masking:
    python scripts/ingest/run_mask_structured.py --source y25_downtime --apply-name-mapping

    # Temporarily override file patterns:
    python scripts/ingest/run_mask_structured.py --source y25_downtime --file-patterns "C1STN DT*.xlsx"

    # List available sources:
    python scripts/ingest/run_mask_structured.py --list-sources

    # Override raw data directory:
    python scripts/ingest/run_mask_structured.py --source y25_downtime --raw-dir ./my_data

Prerequisites:
    - FAULTDX_MASKING_SALT must be set in .env or environment when source uses tokenize/hash
    - Raw data files in data/raw/ (or --raw-dir)
    - Python packages: pyyaml, openpyxl
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


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


def _parse_csv_arg(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _resolve_governance_ids(source_name: str, source_config: dict) -> dict[str, str]:
    """Validate configured inventory identifiers for governance-log joins."""
    configured = source_config.get("governance_ids", {})
    if not configured:
        return {
            "input_source_id": source_name,
            "canonical_source_id": "",
            "serving_source_id": "",
        }
    required = (
        "input_source_id",
        "canonical_source_id",
        "serving_source_id",
    )
    missing = [
        key for key in required
        if not str(configured.get(key, "")).strip()
    ]
    if missing:
        raise ValueError(
            f"Source '{source_name}' has incomplete governance_ids: "
            f"{', '.join(missing)}"
        )
    return {key: str(configured[key]) for key in required}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FaultDx structured data masking pipeline"
    )
    parser.add_argument(
        "--source",
        help="Source name as defined in masking_rules.yaml (e.g. y25_downtime)",
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "configs" / "masking_rules.yaml"),
        help="Path to masking_rules.yaml",
    )
    parser.add_argument(
        "--raw-dir",
        default=str(PROJECT_ROOT / "data" / "raw"),
        help="Directory containing raw data files (default: data/raw/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode: print header report + first N rows without writing files",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=5,
        help="Number of rows to preview in dry-run mode (default: 5)",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List all available source names from config and exit",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect workbook: list sheets, dimensions, and headers (no masking)",
    )
    parser.add_argument(
        "--header-row",
        type=int,
        default=None,
        help="Override header_row (0-based) for inspect or masking",
    )
    parser.add_argument(
        "--sheets",
        type=str,
        default=None,
        help="Override sheet selection: comma-separated sheet names "
             '(e.g. "CG DT L1 Raw Data,CG DT L2 Raw Data")',
    )
    parser.add_argument(
        "--columns",
        type=str,
        default=None,
        help="Override columns_keep: comma-separated column names to retain "
             '(e.g. "Date,shift,Vendor,DT(Mins)")',
    )
    parser.add_argument(
        "--file-patterns",
        type=str,
        default=None,
        help="Override file_patterns: comma-separated glob patterns "
             '(e.g. "C1STN DT*.xlsx,C1STN Error list*.xlsx")',
    )
    parser.add_argument(
        "--apply-name-mapping",
        action="store_true",
        help="Apply local name_mapping.xlsx preprocessing before masking",
    )
    parser.add_argument(
        "--name-mapping-file",
        default=None,
        help="Optional path to local name_mapping.xlsx (default: <raw-dir>/name_mapping.xlsx)",
    )
    return parser.parse_args()


def main() -> None:
    _load_dotenv()
    args = parse_args()

    from services.ingestion.masking_engine import get_source_config, load_rules

    rules = load_rules(Path(args.config))
    file_patterns_override = _parse_csv_arg(args.file_patterns)

    if args.list_sources:
        sources = rules.get("sources", {})
        print(f"Available sources ({len(sources)}):")
        for name, cfg in sources.items():
            patterns = cfg.get("file_patterns", [])
            target = cfg.get("output_target", "processed")
            print(f"  {name:<30} patterns={patterns}  target={target}")
        return

    if args.inspect:
        if not args.source:
            print("[ERROR] --source is required with --inspect.")
            sys.exit(1)
        from services.ingestion.structured_masking import (
            _resolve_header_row_config,
            find_source_files,
            inspect_workbook,
        )
        source_config = get_source_config(rules, args.source)
        file_patterns = file_patterns_override or source_config.get("file_patterns", [])
        raw_dir = Path(args.raw_dir)
        source_files = find_source_files(
            file_patterns,
            raw_dir,
            require_all_patterns=bool(source_config.get("require_all_file_patterns", False)),
        )
        hr = _resolve_header_row_config(args.header_row, source_config.get("header_row", 0))
        for fp in source_files:
            inspect_workbook(fp, header_row=hr, source_config=source_config)
        return

    if not args.source:
        print("[ERROR] --source is required. Use --list-sources to see options.")
        sys.exit(1)

    source_config = get_source_config(rules, args.source)
    governance_ids = _resolve_governance_ids(args.source, source_config)
    sheets_override = _parse_csv_arg(args.sheets)
    columns_override = _parse_csv_arg(args.columns)
    mapping_path = Path(args.name_mapping_file) if args.name_mapping_file else None

    from services.ingestion.structured_masking import run_structured_masking

    result = run_structured_masking(
        source_name=args.source,
        rules=rules,
        raw_dir=Path(args.raw_dir),
        output_base=PROJECT_ROOT / "data",
        dry_run=args.dry_run,
        preview_rows=args.rows,
        sheets_override=sheets_override,
        columns_override=columns_override,
        header_row_override=args.header_row,
        file_patterns_override=file_patterns_override,
        apply_name_mapping=args.apply_name_mapping,
        name_mapping_path=mapping_path,
    )

    if not args.dry_run:
        result.print_summary()
        from services.governance._operation_log import safe_repo_path
        from services.governance.masking_log import record as record_masking_run

        record_masking_run(
            source_id=governance_ids["input_source_id"],
            run_id=result.run_id,
            masking_source_name=args.source,
            input_source_id=governance_ids["input_source_id"],
            canonical_source_id=governance_ids["canonical_source_id"],
            serving_source_id=governance_ids["serving_source_id"],
            rules_version=rules.get("version", 0),
            masking_action="structured_masking",
            input_path=";".join(
                safe_repo_path(path, PROJECT_ROOT) for path in result.input_files
            ),
            output_canonical_path=safe_repo_path(result.canonical_path, PROJECT_ROOT),
            output_serving_path=safe_repo_path(result.serving_path, PROJECT_ROOT),
            manifest_path=safe_repo_path(result.manifest_path, PROJECT_ROOT),
            lineage_path=safe_repo_path(result.lineage_path, PROJECT_ROOT),
        )


if __name__ == "__main__":
    main()
