"""
Config loader for the CAD extract pipeline.

Reads configs/cad_extract.yaml (path resolved relative to the repo root,
detected as the first parent directory containing AGENTS.md or as an
explicit override). All pipeline modules import from here instead of
hardcoding values.

Usage
-----
    from services.graph.cad_extract.config import load_config, CadExtractConfig
    cfg = load_config()                         # reads default yaml
    cfg = load_config("path/to/override.yaml")  # explicit path
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # PyYAML — only dep outside stdlib for this module
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyYAML is required for the CAD extract config loader. "
        "Install with: pip install pyyaml"
    ) from exc

_DEFAULT_CONFIG_RELPATH = "configs/cad_extract.yaml"


def _find_repo_root(start: Path) -> Path:
    """Walk upward from *start* until we find AGENTS.md (repo root marker)."""
    for parent in [start, *start.parents]:
        if (parent / "AGENTS.md").exists():
            return parent
    raise FileNotFoundError(
        f"Could not find repo root (AGENTS.md) starting from {start}. "
        "Run from within the FaultDx_main repo."
    )


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and return the raw config dict from *config_path*.

    If *config_path* is None, resolves configs/cad_extract.yaml relative to
    the repo root (detected via AGENTS.md marker).
    """
    if config_path is None:
        repo_root = _find_repo_root(Path(__file__).resolve())
        config_path = repo_root / _DEFAULT_CONFIG_RELPATH
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"CAD extract config not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Typed accessors — thin wrappers over the raw dict so callers get
# IDE completion and type safety without a heavyweight schema library.
# ---------------------------------------------------------------------------

@dataclass
class MateInferenceConfig:
    max_siblings_per_parent: int = 100
    max_total_pairs: int = 200_000
    max_cousin_pairs: int = 100_000
    spatial_grid_cell_mm: float = 100.0
    max_planes_per_instance: int = 60
    max_cyls_per_instance: int = 40
    max_mates_per_instance_per_type: int = 50
    mate_confidence_threshold: float = 0.5
    plane_dist_tol: float = 0.05
    plane_normal_tol: float = 0.01
    axis_parallel_tol: float = 0.01
    axis_offset_tol: float = 0.05
    radius_rel_tol: float = 0.02
    aabb_tol: float = 1.0


@dataclass
class BomMatchConfig:
    fuzzy_cutoff: float = 0.80
    filter_step_noise: bool = True
    strip_rev_suffix: str | None = r"\s+REV[_\-]?[A-Z0-9]+"
    non_mechanical_keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class CadExtractConfig:
    dataset: str = "Y24_C1STN_Di"
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    sample_size: int = 10
    schema_version: str = "3.2"
    schema_file: Path = Path("contracts/schema/diagnostic_schema_v3_2.json")
    station_source: str = "step_root"
    station_id: str | None = None
    mate: MateInferenceConfig = field(default_factory=MateInferenceConfig)
    bom: BomMatchConfig = field(default_factory=BomMatchConfig)

    # Derived paths (computed in __post_init__)
    step_file: Path = field(init=False)
    bom_file: Path = field(init=False)
    output_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.step_file = self.raw_dir / f"{self.dataset}_STP.STEP"
        self.bom_file = self.raw_dir / f"{self.dataset}_BOM.xlsx"
        self.output_dir = self.processed_dir / f"{self.dataset}_matched"


def parse_config(raw: dict[str, Any]) -> CadExtractConfig:
    """Convert the raw YAML dict into a typed CadExtractConfig."""
    paths = raw.get("paths", {})
    mate_raw = raw.get("mate_inference", {})
    bom_raw = raw.get("bom_match", {})
    schema_raw = raw.get("schema", {})
    station_raw = raw.get("station", {})
    cli_raw = raw.get("cli", {})

    mate = MateInferenceConfig(
        max_siblings_per_parent=mate_raw.get("max_siblings_per_parent", 100),
        max_total_pairs=mate_raw.get("max_total_pairs", 200_000),
        max_cousin_pairs=mate_raw.get("max_cousin_pairs", 100_000),
        spatial_grid_cell_mm=mate_raw.get("spatial_grid_cell_mm", 100.0),
        max_planes_per_instance=mate_raw.get("max_planes_per_instance", 60),
        max_cyls_per_instance=mate_raw.get("max_cyls_per_instance", 40),
        max_mates_per_instance_per_type=mate_raw.get("max_mates_per_instance_per_type", 50),
        mate_confidence_threshold=mate_raw.get("mate_confidence_threshold", 0.5),
        plane_dist_tol=mate_raw.get("plane_dist_tol", 0.05),
        plane_normal_tol=mate_raw.get("plane_normal_tol", 0.01),
        axis_parallel_tol=mate_raw.get("axis_parallel_tol", 0.01),
        axis_offset_tol=mate_raw.get("axis_offset_tol", 0.05),
        radius_rel_tol=mate_raw.get("radius_rel_tol", 0.02),
        aabb_tol=mate_raw.get("aabb_tol", 1.0),
    )

    keywords = bom_raw.get("non_mechanical_keywords", [])
    bom = BomMatchConfig(
        fuzzy_cutoff=bom_raw.get("fuzzy_cutoff", 0.80),
        filter_step_noise=bom_raw.get("filter_step_noise", True),
        strip_rev_suffix=bom_raw.get("strip_rev_suffix"),
        non_mechanical_keywords=tuple(keywords),
    )

    return CadExtractConfig(
        dataset=raw.get("dataset", "Y24_C1STN_Di"),
        raw_dir=Path(paths.get("raw_dir", "data/raw")),
        processed_dir=Path(paths.get("processed_dir", "data/processed")),
        sample_size=cli_raw.get("sample_size", 10),
        schema_version=schema_raw.get("version", "3.2"),
        schema_file=Path(schema_raw.get("schema_file", "contracts/schema/diagnostic_schema_v3_2.json")),
        station_source=station_raw.get("source", "step_root"),
        station_id=station_raw.get("station_id") or None,
        mate=mate,
        bom=bom,
    )


def get_config(config_path: str | Path | None = None) -> CadExtractConfig:
    """Load YAML and return a typed CadExtractConfig. One-call convenience."""
    return parse_config(load_config(config_path))
