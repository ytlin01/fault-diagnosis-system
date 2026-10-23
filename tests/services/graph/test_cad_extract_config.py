"""
PR-1 smoke tests: config loader and typed CadExtractConfig.

These tests do not require any STEP or BOM files.
The full 15-test synthetic-STEP suite is added in PR-2.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from services.graph.cad_extract.config import (
    BomMatchConfig,
    CadExtractConfig,
    MateInferenceConfig,
    get_config,
    load_config,
    parse_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "cad_extract.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_config — typed round-trip
# ---------------------------------------------------------------------------

def test_parse_config_dataset_override():
    cfg = parse_config({"dataset": "TEST_MACHINE_01"})
    assert cfg.dataset == "TEST_MACHINE_01"
    assert cfg.step_file == Path("data/raw/TEST_MACHINE_01_STP.STEP")
    assert cfg.bom_file == Path("data/raw/TEST_MACHINE_01_BOM.xlsx")
    assert cfg.output_dir == Path("data/processed/TEST_MACHINE_01_matched")


def test_parse_config_mate_thresholds():
    raw = {
        "mate_inference": {
            "max_mates_per_instance_per_type": 25,
            "mate_confidence_threshold": 0.7,
            "aabb_tol": 2.0,
        }
    }
    cfg = parse_config(raw)
    assert cfg.mate.max_mates_per_instance_per_type == 25
    assert cfg.mate.mate_confidence_threshold == 0.7
    assert cfg.mate.aabb_tol == 2.0


def test_parse_config_bom_keywords():
    raw = {
        "bom_match": {
            "non_mechanical_keywords": ["电缆", "线缆", "USB"],
            "fuzzy_cutoff": 0.85,
        }
    }
    cfg = parse_config(raw)
    assert "电缆" in cfg.bom.non_mechanical_keywords
    assert cfg.bom.fuzzy_cutoff == 0.85


def test_parse_config_strip_rev_suffix_none():
    cfg = parse_config({"bom_match": {"strip_rev_suffix": None}})
    assert cfg.bom.strip_rev_suffix is None


def test_parse_config_schema_version():
    cfg = parse_config({"schema": {"version": "3.2"}})
    assert cfg.schema_version == "3.2"


# ---------------------------------------------------------------------------
# load_config — YAML round-trip via temp file
# ---------------------------------------------------------------------------

def test_load_config_from_file(tmp_path):
    yaml_path = _write_yaml(tmp_path, """
        dataset: "UNIT_TEST"
        mate_inference:
          mate_confidence_threshold: 0.6
        bom_match:
          fuzzy_cutoff: 0.90
    """)
    raw = load_config(yaml_path)
    assert raw["dataset"] == "UNIT_TEST"
    assert raw["mate_inference"]["mate_confidence_threshold"] == 0.6


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# get_config — one-call convenience
# ---------------------------------------------------------------------------

def test_get_config_returns_typed(tmp_path):
    yaml_path = _write_yaml(tmp_path, """
        dataset: "TYPED_TEST"
        schema:
          version: "3.2"
          schema_file: "contracts/schema/diagnostic_schema_v3_2.json"
        station:
          source: "step_root"
    """)
    cfg = get_config(yaml_path)
    assert isinstance(cfg, CadExtractConfig)
    assert cfg.dataset == "TYPED_TEST"
    assert cfg.schema_version == "3.2"
    assert cfg.station_source == "step_root"


# ---------------------------------------------------------------------------
# CadExtractConfig — derived path invariants
# ---------------------------------------------------------------------------

def test_derived_paths_are_consistent():
    cfg = parse_config({"dataset": "MY_DS"})
    assert cfg.step_file.name == "MY_DS_STP.STEP"
    assert cfg.bom_file.name == "MY_DS_BOM.xlsx"
    assert cfg.output_dir.name == "MY_DS_matched"


def test_default_mate_config_matches_yaml_defaults():
    """Typed defaults must stay in sync with configs/cad_extract.yaml values."""
    default_mate = MateInferenceConfig()
    assert default_mate.max_mates_per_instance_per_type == 50
    assert default_mate.mate_confidence_threshold == 0.5
    assert default_mate.max_siblings_per_parent == 100
    assert default_mate.spatial_grid_cell_mm == 100.0
