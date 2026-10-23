"""Dataset manifest generation.

A manifest records metadata about one masking run for a single source:
    - input file(s), row/column counts, md5
    - output file(s), row/column counts
    - masking rules version applied
    - timestamp, environment info
    - review_flag columns (need human review)

The caller supplies the governed manifest directory and portable path labels.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _file_md5(path: Path, chunk_size: int = 8192) -> str:
    """Compute MD5 hex digest for a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _portable_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    return str(value).replace("\\", "/")


def make_run_id() -> str:
    """Return one portable identifier shared by all artifacts from a run."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"maskrun_{timestamp}_{uuid4().hex[:8]}"


def build_manifest(
    *,
    run_id: str,
    source_name: str,
    rules_version: int,
    input_files: list[Path],
    input_file_labels: list[str] | None = None,
    input_row_count: int,
    input_col_count: int,
    output_canonical_path: str | Path | None = None,
    output_serving_path: str | Path | None = None,
    output_row_count: int,
    output_col_count_canonical: int,
    output_col_count_serving: int,
    review_flag_columns: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict:
    """Build a manifest dict (not yet written to disk)."""
    if not run_id.strip():
        raise ValueError("run_id must not be blank")
    labels = input_file_labels or [str(p) for p in input_files]
    if len(labels) != len(input_files):
        raise ValueError(
            "input_file_labels length must match input_files length"
        )

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "source_name": source_name,
        "masking_rules_version": rules_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "files": [
                {"path": label, "md5": _file_md5(p) if p.exists() else "N/A"}
                for p, label in zip(input_files, labels)
            ],
            "row_count": input_row_count,
            "col_count": input_col_count,
        },
        "output": {
            "canonical": {
                "path": _portable_path(output_canonical_path),
                "row_count": output_row_count,
                "col_count": output_col_count_canonical,
            },
            "serving": {
                "path": _portable_path(output_serving_path),
                "row_count": output_row_count,
                "col_count": output_col_count_serving,
            },
        },
        "review_flag_columns": review_flag_columns or [],
    }
    if extra:
        manifest["extra"] = extra
    return manifest


def write_manifest(manifest: dict, output_dir: Path) -> Path:
    """Write manifest dict to JSON file. Returns the written path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    name = manifest["source_name"]
    run_id = manifest["run_id"]
    path = output_dir / f"{name}_manifest_{run_id}.json"
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite masking run manifest: {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return path
