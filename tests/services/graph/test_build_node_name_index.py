from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.build_graph.build_node_name_index import build_index


def _write_triples(tmp_path: Path, triples: dict) -> Path:
    p = tmp_path / "triples.json"
    p.write_text(json.dumps(triples, ensure_ascii=False), encoding="utf-8")
    return p


def test_duplicate_components_different_modules_get_scoped_keys(tmp_path: Path) -> None:
    """Two same-name Components under different Modules → each gets underscore scoped key;
    bare name is kept for the first (sorted) occurrence."""
    triples = {
        "nodes": [
            {"id": "M_1", "label": "Module", "properties": {"module_id": "M_1", "name": "Cowling组装"}},
            {"id": "M_2", "label": "Module", "properties": {"module_id": "M_2", "name": "底盘组装"}},
            {"id": "C_1", "label": "Component", "properties": {"component_id": "C_1", "name": "安装板"}},
            {"id": "C_2", "label": "Component", "properties": {"component_id": "C_2", "name": "安装板"}},
        ],
        "edges": [
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_1"},
            {"type": "HAS_COMPONENT", "from": "M_2", "to": "C_2"},
        ],
    }
    path = _write_triples(tmp_path, triples)
    index, stats = build_index(path)

    # Underscore-scoped keys address each component precisely
    assert index["component"]["Cowling组装_安装板"] == "C_1"
    assert index["component"]["底盘组装_安装板"] == "C_2"
    # Bare name retained for first sorted occurrence
    assert "安装板" in index["component"]
    # Collision recorded in metadata
    assert "安装板" in index["__metadata__"]["collisions"]["component"]
    # scoped_count reflects two scoped keys written
    assert stats["Component"]["scoped_count"] == 2


def test_unique_name_has_no_scoped_key(tmp_path: Path) -> None:
    """A Component with a unique name gets the bare name as the primary key
    and no underscore-scoped key is generated."""
    triples = {
        "nodes": [
            {"id": "M_1", "label": "Module", "properties": {"module_id": "M_1", "name": "上料模块"}},
            {"id": "C_1", "label": "Component", "properties": {"component_id": "C_1", "name": "独特压块"}},
        ],
        "edges": [
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_1"},
        ],
    }
    path = _write_triples(tmp_path, triples)
    index, stats = build_index(path)

    assert index["component"]["独特压块"] == "C_1"
    # No underscore-scoped key for a unique name
    assert "上料模块_独特压块" not in index["component"]
    assert stats["Component"]["scoped_count"] == 0
    assert "component" not in index["__metadata__"]["collisions"]


def test_orphan_duplicate_component_falls_back_to_bare_name(
    tmp_path: Path, capsys
) -> None:
    """Two Components with the same name but no parent edges → no parent name
    available; bare name kept, warning printed to stdout."""
    triples = {
        "nodes": [
            {"id": "C_1", "label": "Component", "properties": {"component_id": "C_1", "name": "连接板"}},
            {"id": "C_2", "label": "Component", "properties": {"component_id": "C_2", "name": "连接板"}},
        ],
        "edges": [],
    }
    path = _write_triples(tmp_path, triples)
    index, stats = build_index(path)

    # Bare name kept even with no parent info
    assert "连接板" in index["component"]
    # No scoped key possible without parent
    assert stats["Component"]["scoped_count"] == 0
    # Warning emitted to stdout
    captured = capsys.readouterr()
    assert "WARN" in captured.out
    assert "连接板" in captured.out


def test_nauo_raw_id_alias_added_as_secondary(tmp_path: Path) -> None:
    """NAUO raw id (node id without typed prefix) is added as a secondary alias
    when it differs from the name property."""
    triples = {
        "nodes": [
            {"id": "C_42", "label": "Component", "properties": {"component_id": "C_42", "name": "压块组件"}},
        ],
        "edges": [],
    }
    path = _write_triples(tmp_path, triples)
    index, stats = build_index(path)

    # Primary key is the display name
    assert index["component"]["压块组件"] == "C_42"
    # Raw id alias (strips "C_" prefix)
    assert index["component"]["42"] == "C_42"
    assert stats["Component"]["alias_count"] == 1
