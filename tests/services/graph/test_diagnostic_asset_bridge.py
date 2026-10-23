from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.graph.diagnostic_asset_bridge import (
    build_asset_catalog,
    build_bridge_record,
    load_alias_config,
    normalize_for_match,
)


def _catalog() -> dict:
    index_data = {
        "module": {
            "Cowling组装": "M_1",
        },
        "component": {
            "CCD4": "C_4",
            "电批": "C_5",
        },
        "subcomponent": {},
    }
    triples_data = {
        "nodes": [
            {"id": "M_1", "label": "Module", "properties": {"module_id": "M_1", "name": "Cowling组装"}},
            {"id": "C_4", "label": "Component", "properties": {"component_id": "C_4", "name": "CCD4", "module_id": "M_1"}},
            {"id": "C_5", "label": "Component", "properties": {"component_id": "C_5", "name": "电批", "module_id": "M_1"}},
        ],
        "edges": [
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_4", "properties": {}},
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_5", "properties": {}},
        ],
    }
    alias_config = {
        "module_aliases": {"M_1": ["Cowling组装"]},
        "component_aliases": {"C_4": ["CCD4"], "C_5": ["电批"]},
    }
    return build_asset_catalog(index_data, triples_data, alias_config=alias_config)


def test_normalize_for_match_strips_common_separators() -> None:
    assert normalize_for_match("Cowling_定位侧 CCD4") == "cowling定位侧ccd4"


def test_build_bridge_record_maps_unique_component_hit() -> None:
    record = {
        "mapping_id": "x1",
        "EC": "V020441-01",
        "standard_fp": "Cowling定位侧CCD4抓边异常",
        "field_fp_variants": [],
    }
    result = build_bridge_record(record, _catalog())
    assert result["mapping_status"] == "mapped"
    assert result["component_id"] == "C_4"
    assert result["module_id"] == "M_1"


def test_build_bridge_record_returns_module_only_when_no_component_hit() -> None:
    record = {
        "mapping_id": "x2",
        "EC": "E99OOOO-02-03",
        "standard_fp": "Cowling组装工位异常",
        "field_fp_variants": [],
    }
    result = build_bridge_record(record, _catalog())
    assert result["mapping_status"] == "module_only"
    assert result["component_id"] is None
    assert result["module_id"] == "M_1"


def test_build_bridge_record_prefers_more_specific_component_alias() -> None:
    record = {
        "mapping_id": "x3",
        "EC": "W99RBRT-16-03",
        "standard_fp": "Cowling电批CCD4同时异常",
        "field_fp_variants": [],
    }
    result = build_bridge_record(record, _catalog())
    assert result["mapping_status"] == "mapped"
    assert result["component_id"] == "C_4"


def test_load_alias_config_returns_defaults_when_missing(tmp_path: Path) -> None:
    cfg = load_alias_config(tmp_path / "missing.yaml")
    assert cfg == {"module_aliases": {}, "component_aliases": {}}


def test_build_bridge_record_prefers_more_specific_module_alias() -> None:
    index_data = {
        "module": {},
        "component": {},
        "subcomponent": {},
    }
    triples_data = {
        "nodes": [
            {"id": "M_1", "label": "Module", "properties": {"module_id": "M_1", "name": "摄像头装配体"}},
            {"id": "M_2", "label": "Module", "properties": {"module_id": "M_2", "name": "摄像头装配体2"}},
        ],
        "edges": [],
    }
    alias_config = {
        "module_aliases": {
            "M_1": ["定位ccd"],
            "M_2": ["螺丝定位ccd", "ccd5"],
        },
        "component_aliases": {},
    }
    catalog = build_asset_catalog(index_data, triples_data, alias_config=alias_config)
    record = {
        "mapping_id": "x4",
        "EC": "V020552-01",
        "standard_fp": "Cowling螺丝定位CCD5抓边异常",
        "field_fp_variants": [],
    }
    result = build_bridge_record(record, catalog)
    assert result["mapping_status"] == "module_only"
    assert result["module_id"] == "M_2"
