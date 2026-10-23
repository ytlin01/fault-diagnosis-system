from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.build_graph.build_node_name_index import build_index


def test_duplicate_component_names_get_qualified_aliases(tmp_path: Path) -> None:
    triples = {
        "nodes": [
            {"id": "M_1", "label": "Module", "properties": {"module_id": "M_1", "name": "上料模块"}},
            {"id": "M_2", "label": "Module", "properties": {"module_id": "M_2", "name": "锁付模块"}},
            {"id": "C_1", "label": "Component", "properties": {"component_id": "C_1", "name": "安装板"}},
            {"id": "C_2", "label": "Component", "properties": {"component_id": "C_2", "name": "安装板"}},
        ],
        "edges": [
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_1"},
            {"type": "HAS_COMPONENT", "from": "M_2", "to": "C_2"},
        ],
    }
    triples_path = tmp_path / "triples.json"
    triples_path.write_text(json.dumps(triples, ensure_ascii=False), encoding="utf-8")

    index, _stats = build_index(triples_path)

    # Bare name kept for first (sorted) occurrence via setdefault
    assert "安装板" in index["component"]
    # Hierarchy-qualified slash aliases
    assert index["component"]["上料模块/安装板"] == "C_1"
    assert index["component"]["锁付模块/安装板"] == "C_2"
    assert index["component"]["上料模块 安装板"] == "C_1"
    # Underscore-scoped keys (019A addition)
    assert index["component"]["上料模块_安装板"] == "C_1"
    assert index["component"]["锁付模块_安装板"] == "C_2"
    assert index["__metadata__"]["collisions"]["component"]["安装板"] == ["C_1", "C_2"]


def test_duplicate_subcomponent_names_use_component_and_module_context(tmp_path: Path) -> None:
    triples = {
        "nodes": [
            {"id": "M_1", "label": "Module", "properties": {"module_id": "M_1", "name": "视觉模块"}},
            {"id": "C_1", "label": "Component", "properties": {"component_id": "C_1", "name": "相机组件"}},
            {"id": "C_2", "label": "Component", "properties": {"component_id": "C_2", "name": "光源组件"}},
            {"id": "SC_1", "label": "SubComponent", "properties": {"subcomponent_id": "SC_1", "name": "安装板"}},
            {"id": "SC_2", "label": "SubComponent", "properties": {"subcomponent_id": "SC_2", "name": "安装板"}},
        ],
        "edges": [
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_1"},
            {"type": "HAS_COMPONENT", "from": "M_1", "to": "C_2"},
            {"type": "HAS_SUBCOMPONENT", "from": "C_1", "to": "SC_1"},
            {"type": "HAS_SUBCOMPONENT", "from": "C_2", "to": "SC_2"},
        ],
    }
    triples_path = tmp_path / "triples.json"
    triples_path.write_text(json.dumps(triples, ensure_ascii=False), encoding="utf-8")

    index, _stats = build_index(triples_path)

    # Bare name kept for first (sorted) occurrence via setdefault
    assert "安装板" in index["subcomponent"]
    # Hierarchy-qualified slash aliases
    assert index["subcomponent"]["相机组件/安装板"] == "SC_1"
    assert index["subcomponent"]["光源组件/安装板"] == "SC_2"
    assert index["subcomponent"]["视觉模块/相机组件/安装板"] == "SC_1"
    assert index["subcomponent"]["视觉模块/光源组件/安装板"] == "SC_2"
    # Underscore-scoped keys (019A addition) — immediate parent
    assert index["subcomponent"]["相机组件_安装板"] == "SC_1"
    assert index["subcomponent"]["光源组件_安装板"] == "SC_2"
