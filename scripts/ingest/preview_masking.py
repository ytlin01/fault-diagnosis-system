"""Preview / dry-run / audit tool for masking pipeline.

Three modes:
    1. rules    — print resolved rules for a source (no data needed)
    2. preview  — show before/after for first N rows (needs data)
    3. audit    — scan serving output for residual A-level patterns

Usage:
    python scripts/ingest/preview_masking.py rules    --source y25_downtime
    python scripts/ingest/preview_masking.py preview  --source y25_downtime --rows 3
    python scripts/ingest/preview_masking.py preview  --source y25_downtime --rows 3 --apply-name-mapping
    python scripts/ingest/preview_masking.py inspect  --source y25_downtime --file-patterns "C1STN DT*.xlsx"
    python scripts/ingest/preview_masking.py audit    --scan-dir data/serving_structured
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _load_dotenv() -> None:
    """Load .env file if present."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()


def _parse_csv_arg(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def cmd_rules(args: argparse.Namespace) -> None:
    """Print the resolved masking rules for every column of a source."""
    from services.ingestion.masking_engine import (
        load_rules,
        get_source_config,
        resolve_column_rule,
    )

    rules = load_rules(Path(args.config))
    source_config = get_source_config(rules, args.source)

    print(f"\nSource: {args.source}")
    print(f"File patterns: {source_config.get('file_patterns')}")
    print(f"Sheet selector: {source_config.get('sheet_selector', 'index=0 (default)')}")
    print(f"Output target: {source_config.get('output_target', 'processed (default)')}")

    aliases = source_config.get("column_aliases", {})
    if aliases:
        print(f"\nColumn aliases ({len(aliases)}):")
        for rule_name, alias_list in aliases.items():
            print(f"  {rule_name} <- {alias_list}")

    print()
    print(f"{'Column':<30} {'Level':<6} {'Canonical':<14} {'Serving':<14} {'Review'}")
    print("-" * 80)

    for col_name in source_config.get("column_rules", {}):
        resolved = resolve_column_rule(col_name, source_config, rules)
        review = "  YES" if resolved["review_flag"] else ""
        rename = f" ->({resolved['rename_to']})" if resolved.get("rename_to") else ""
        print(f"{col_name:<30} {resolved['level']:<6} "
              f"{resolved['canonical_action']:<14} "
              f"{resolved['serving_action']:<14} {review}{rename}")


def cmd_inspect(args: argparse.Namespace) -> None:
    """Inspect workbook: list sheets, dimensions, and header row."""
    from services.ingestion.masking_engine import load_rules, get_source_config
    from services.ingestion.structured_masking import (
        _resolve_header_row_config,
        find_source_files,
        inspect_workbook,
    )

    rules = load_rules(Path(args.config))
    source_config = get_source_config(rules, args.source)
    raw_dir = Path(args.raw_dir)
    file_patterns = _parse_csv_arg(args.file_patterns) or source_config.get("file_patterns", [])
    source_files = find_source_files(
        file_patterns,
        raw_dir,
        require_all_patterns=bool(source_config.get("require_all_file_patterns", False)),
    )

    hr = _resolve_header_row_config(args.header_row, source_config.get("header_row", 0))

    for fp in source_files:
        inspect_workbook(fp, header_row=hr, source_config=source_config)

    print("  Tip: header_row is 0-based (0 = first row).")
    print(f"  Current config for '{args.source}': header_row={source_config.get('header_row', '0 (default)')}")
    ss = source_config.get("sheet_selector", {})
    print(f"  Current sheet_selector: mode={ss.get('mode', 'index')}, value={ss.get('value', 0)}")
    print(f"  Effective file_patterns: {file_patterns}")
    print()
    print("  To try a different header_row:")
    print(f"    python scripts/ingest/preview_masking.py inspect --source {args.source} --header-row 1")
    print()


def cmd_preview(args: argparse.Namespace) -> None:
    """Preview: run structured masking in dry-run mode."""
    from services.ingestion.masking_engine import load_rules
    from services.ingestion.structured_masking import run_structured_masking

    rules = load_rules(Path(args.config))
    raw_dir = Path(args.raw_dir)
    mapping_path = Path(args.name_mapping_file) if args.name_mapping_file else None
    file_patterns_override = _parse_csv_arg(args.file_patterns)

    run_structured_masking(
        source_name=args.source,
        rules=rules,
        raw_dir=raw_dir,
        output_base=PROJECT_ROOT / "data",
        dry_run=True,
        preview_rows=args.rows,
        file_patterns_override=file_patterns_override,
        apply_name_mapping=args.apply_name_mapping,
        name_mapping_path=mapping_path,
    )


def cmd_audit(args: argparse.Namespace) -> None:
    """Scan serving output directory for residual A-level patterns."""
    scan_dir = Path(args.scan_dir)
    if not scan_dir.exists():
        print(f"[AUDIT] Directory not found: {scan_dir}")
        return

    patterns = [
        ("email", re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')),
        ("phone_cn", re.compile(r'(?:\+?86[-\s]?)?1[3-9]\d{9}')),
        ("employee_id", re.compile(r'[A-Z]\d{6,8}')),
    ]

    json_files = list(scan_dir.glob("*.json"))
    if not json_files:
        print(f"[AUDIT] No JSON files found in {scan_dir}")
        return

    print(f"\n[AUDIT] Scanning {len(json_files)} file(s) in {scan_dir}")
    print(f"[AUDIT] Checking for: {[p[0] for p in patterns]}")
    print()

    total_findings = 0
    for fp in json_files:
        content = fp.read_text(encoding="utf-8")
        file_findings: list[tuple[str, str]] = []

        for pname, pregex in patterns:
            matches = pregex.findall(content)
            if matches:
                for match in matches[:5]:
                    file_findings.append((pname, match))

        if file_findings:
            print(f"  {fp.name}:")
            for pname, match in file_findings:
                print(f"    [{pname}] {match}")
            total_findings += len(file_findings)

    print()
    if total_findings:
        print(f"[AUDIT] FOUND {total_findings} potential residual PII. Please review.")
    else:
        print("[AUDIT] No residual A-level patterns found. Looks clean.")


def main() -> None:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Masking preview & audit tool")
    parser.add_argument(
        "--config", default=str(PROJECT_ROOT / "configs" / "masking_rules.yaml"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_rules = sub.add_parser("rules", help="Print resolved rules for a source")
    p_rules.add_argument("--source", required=True)

    p_inspect = sub.add_parser(
        "inspect", help="Inspect workbook: list sheets, dimensions, headers"
    )
    p_inspect.add_argument("--source", required=True)
    p_inspect.add_argument(
        "--raw-dir", default=str(PROJECT_ROOT / "data" / "raw"),
    )
    p_inspect.add_argument(
        "--header-row", type=int, default=None,
        help="Override header_row (0-based) for inspection",
    )
    p_inspect.add_argument(
        "--file-patterns",
        type=str,
        default=None,
        help="Override file_patterns: comma-separated glob patterns",
    )

    p_preview = sub.add_parser("preview", help="Preview before/after for N rows")
    p_preview.add_argument("--source", required=True)
    p_preview.add_argument("--rows", type=int, default=5)
    p_preview.add_argument(
        "--raw-dir",
        default=str(PROJECT_ROOT / "data" / "raw"),
    )
    p_preview.add_argument(
        "--file-patterns",
        type=str,
        default=None,
        help="Override file_patterns: comma-separated glob patterns",
    )
    p_preview.add_argument(
        "--apply-name-mapping",
        action="store_true",
        help="Apply local name_mapping.xlsx preprocessing before masking preview",
    )
    p_preview.add_argument(
        "--name-mapping-file",
        default=None,
        help="Optional path to local name_mapping.xlsx",
    )

    p_audit = sub.add_parser("audit", help="Scan serving output for residual PII")
    p_audit.add_argument(
        "--scan-dir",
        default=str(PROJECT_ROOT / "data" / "serving_structured"),
    )

    args = parser.parse_args()
    if args.command == "rules":
        cmd_rules(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "preview":
        cmd_preview(args)
    elif args.command == "audit":
        cmd_audit(args)


if __name__ == "__main__":
    main()
