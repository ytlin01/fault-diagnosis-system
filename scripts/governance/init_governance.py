"""Initialize data/governance/source_inventory.csv and populate source_inventory.

Scans the data/ directory to discover all known artifacts and registers them.
Also registers the three legacy directories as legacy_pending_cleanup.

Usage:
    python -m scripts.governance.init_governance              # full run
    python -m scripts.governance.init_governance --dry-run   # preview only
    python -m scripts.governance.init_governance --reset     # rebuild CSV inventory
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Resolve project root so we can import services.*
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.governance import inventory

DATA_DIR = PROJECT_ROOT / "data"
GOVERNANCE_DIR = DATA_DIR / "governance"


# Classification helpers 
def _classify_serving(rel: str) -> dict:
    name = Path(rel).stem.lower()
    if "hive_error_code" in name or "error_code" in name:
        source_type = "error_code"
        route = "route_b"
    elif "dfm_c1stn" in name or "dfm" in name:
        source_type = "system_arch"
        route = "route_a|route_b_candidate_residual"
    elif "sop" in name:
        source_type = "sop"
        route = "route_b"
    elif "synthetic" in name:
        source_type = "synthetic"
        route = "route_b"
    else:
        source_type = "unstructured"
        route = "unknown"

    masked = "masked" if ("masked" in name or "masked" in rel) else "unmasked"
    return {
        "zone": "serving",
        "source_type": source_type,
        "route_eligibility": route,
        "serving_safe": "yes",
        "masking_status": masked,
        "reviewed_status": "reviewed",
    }


def _classify_processed(rel: str) -> dict:
    name = Path(rel).stem.lower()
    parts = rel.split("/")

    if "diagnostic" in rel:
        return {
            "zone": "processed",
            "source_type": "diagnostic",
            "route_eligibility": "route_a",
            "serving_safe": "no",
            "masking_status": "n_a",
            "reviewed_status": "reviewed",
        }
    if "unstructured_masked_vlm" in rel or "masked" in parts:
        return {
            "zone": "processed",
            "source_type": "masked_canonical",
            "route_eligibility": "route_b",
            "serving_safe": "no",
            "masking_status": "masked",
            "reviewed_status": "reviewed",
        }
    if "unstructured_vlm" in rel or "unstructured" in parts:
        return {
            "zone": "processed",
            "source_type": "unstructured_canonical",
            "route_eligibility": "route_b",
            "serving_safe": "no",
            "masking_status": "unmasked",
            "reviewed_status": "reviewed",
        }
    if "aggregates" in rel:
        return {
            "zone": "processed",
            "source_type": "aggregate",
            "route_eligibility": "route_a",
            "serving_safe": "no",
            "masking_status": "pending",
            "reviewed_status": "reviewed",
        }
    if "indexes" in rel:
        return {
            "zone": "processed",
            "source_type": "index",
            "route_eligibility": "route_a",
            "serving_safe": "no",
            "masking_status": "n_a",
            "reviewed_status": "reviewed",
        }
    if "review_pending" in rel:
        return {
            "zone": "processed",
            "source_type": "review_pending",
            "route_eligibility": "unknown",
            "serving_safe": "no",
            "masking_status": "unmasked",
            "reviewed_status": "pending",
        }
    # structured/ (CAD extracts, BOM matches, etc.)
    return {
        "zone": "processed",
        "source_type": "structured_extract",
        "route_eligibility": "route_a",
        "serving_safe": "no",
        "masking_status": "n_a",
        "reviewed_status": "reviewed",
    }


def _classify_eval(rel: str) -> dict:
    return {
        "zone": "eval",
        "source_type": "eval_set",
        "route_eligibility": "n_a",
        "serving_safe": "yes",
        "masking_status": "masked",
        "reviewed_status": "reviewed",
    }


def _source_id_from_path(rel: str) -> str:
    """Derive a unique, stable source_id from a relative path.

    e.g. "data/processed/structured/parts_list.json"
      鈫? "processed__structured__parts_list"
    """
    rel_from_data = rel.removeprefix("data/")
    stem = Path(rel_from_data).stem
    parent = str(Path(rel_from_data).parent).replace("\\", "__").replace("/", "__")
    sid = f"{parent}__{stem}" if parent != "." else stem
    return sid[:100]


# Legacy directories 
LEGACY_DIRS = [
    ("data/processed/Y24_C1STN_Di_matched", "structured_extract",
     "Content migrated to processed/structured/Y24_C1STN_Di_matched/"),
    ("data/processed/diagnostic", "diagnostic",
     "Content migrated to processed/structured/ and processed/indexes/"),
    ("data/processed/unstructured_masked_vlm", "masked_canonical",
     "Superseded by processed/masked/"),
]


# Main 
def run(*, dry_run: bool = False, reset: bool = False) -> None:
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Initializing governance CSV inventory")
    print(f"  Governance dir: {GOVERNANCE_DIR}")
    print(f"  Data dir:       {DATA_DIR}\n")

    if reset and not dry_run:
        inventory_path = GOVERNANCE_DIR / "source_inventory.csv"
        if inventory_path.exists():
            inventory_path.unlink()

    registered = 0
    skipped = 0

    def _record(**kwargs):
        nonlocal registered, skipped
        sid = kwargs["source_id"]
        if not dry_run:
            existing = inventory.get(sid, governance_dir=GOVERNANCE_DIR)
            if existing and not reset:
                skipped += 1
                return
        inventory.record(**kwargs, dry_run=dry_run, governance_dir=GOVERNANCE_DIR)
        registered += 1

    # serving/
    serving_dir = DATA_DIR / "serving"
    for f in sorted(serving_dir.rglob("*.json")):
        if f.name.startswith(".") or ".gitkeep" in f.name:
            continue
        rel = f.relative_to(PROJECT_ROOT).as_posix()
        meta = _classify_serving(rel)
        _record(
            source_id=_source_id_from_path(rel),
            file_path=rel,
            **meta,
            notes="",
        )

    # processed/
    processed_dir = DATA_DIR / "processed"
    for f in sorted(processed_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in (".json", ".xlsx"):
            continue
        if f.name.startswith(".") or ".gitkeep" in f.name:
            continue
        rel = f.relative_to(PROJECT_ROOT).as_posix()
        meta = _classify_processed(rel)
        _record(
            source_id=_source_id_from_path(rel),
            file_path=rel,
            **meta,
            notes="",
        )

    # eval/
    eval_dir = DATA_DIR / "eval"
    for f in sorted(eval_dir.rglob("*.json")):
        if f.name.startswith(".") or ".gitkeep" in f.name:
            continue
        rel = f.relative_to(PROJECT_ROOT).as_posix()
        _record(
            source_id=_source_id_from_path(rel),
            file_path=rel,
            **_classify_eval(rel),
            notes="",
        )

    # Legacy directory stubs
    for legacy_path, stype, note in LEGACY_DIRS:
        _record(
            source_id=legacy_path.replace("/", "_").replace("data_", ""),
            file_path=legacy_path,
            zone="processed",
            source_type=stype,
            route_eligibility="n_a",
            serving_safe="no",
            masking_status="n_a",
            reviewed_status="legacy_pending_cleanup",
            notes=note,
        )

    print()
    print(f"  Registered: {registered}")
    print(f"  Skipped (already exists): {skipped}")
    if dry_run:
        print("\n[DRY-RUN] No files written. Run without --dry-run to apply.")
    else:
        print(f"\n  Output: {GOVERNANCE_DIR / 'source_inventory.csv'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize governance CSV inventory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--reset", action="store_true",
                        help="Rebuild source_inventory.csv from discovered artifacts")
    args = parser.parse_args()
    run(dry_run=args.dry_run, reset=args.reset)
