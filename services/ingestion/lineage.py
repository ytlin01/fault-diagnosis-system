"""Per-row, per-field lineage / audit logging.

Each masking run produces a JSONL file where every line records:
    - source_name, row_index
    - column_name, original_level (A/B/C)
    - action_taken (tokenize / drop / generalize / …)
    - action_detail (e.g. "tokenize→TOK_abc123")
    - view (canonical | serving)
    - review_flag (bool)

The caller supplies the governed lineage directory and one shared run ID.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TextIO


class LineageWriter:
    """Streaming JSONL writer for lineage records."""

    def __init__(self, source_name: str, output_dir: Path, *, run_id: str):
        if not run_id.strip():
            raise ValueError("run_id must not be blank")
        self.source_name = source_name
        self.run_id = run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        self._path = output_dir / f"{source_name}_lineage_{run_id}.jsonl"
        self._fh: TextIO | None = None

    @property
    def path(self) -> Path:
        return self._path

    def open(self) -> "LineageWriter":
        if self._path.exists():
            raise FileExistsError(
                f"Refusing to overwrite masking run lineage: {self._path}"
            )
        self._fh = open(self._path, "w", encoding="utf-8")
        return self

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "LineageWriter":
        return self.open()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def record(
        self,
        *,
        row_index: int,
        column_name: str,
        level: str,
        action: str,
        detail: str,
        view: str,
        review_flag: bool = False,
    ) -> None:
        """Write one lineage record."""
        if self._fh is None:
            raise RuntimeError("LineageWriter is not open. Use as context manager.")
        entry = {
            "run_id": self.run_id,
            "source": self.source_name,
            "row": row_index,
            "column": column_name,
            "level": level,
            "action": action,
            "detail": detail,
            "view": view,
            "review_flag": review_flag,
        }
        self._fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
