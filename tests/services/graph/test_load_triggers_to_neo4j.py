from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.build_graph.load_triggers_to_neo4j import _build_trigger_rows


def _rec(status: str, component_id: str | None = "C_1", fault_id: str | None = "fault:abc", rule: str = "component_alias_contains") -> dict:
    return {
        "mapping_status": status,
        "component_id": component_id,
        "fault_id": fault_id,
        "evidence": {"rule": rule},
    }


def test_only_mapped_records_loaded_by_default() -> None:
    records = [
        _rec("mapped"),
        _rec("module_only"),
        _rec("unmapped"),
        _rec("ambiguous"),
    ]
    rows = _build_trigger_rows(records, {"mapped"})
    assert len(rows) == 1
    assert rows[0]["component_id"] == "C_1"
    assert rows[0]["fault_id"] == "fault:abc"


def test_allow_statuses_gates_correctly() -> None:
    records = [_rec("mapped"), _rec("module_only"), _rec("unmapped")]
    rows = _build_trigger_rows(records, {"mapped", "module_only"})
    assert len(rows) == 2


def test_records_missing_component_or_fault_are_skipped() -> None:
    records = [
        _rec("mapped", component_id=None),
        _rec("mapped", fault_id=None),
        _rec("mapped"),
    ]
    rows = _build_trigger_rows(records, {"mapped"})
    assert len(rows) == 1


def test_row_carries_required_fields() -> None:
    rows = _build_trigger_rows([_rec("mapped", rule="manual_alias")], {"mapped"})
    assert len(rows) == 1
    row = rows[0]
    assert row["validated"] is False
    assert row["source"] == "diagnostic_asset_bridge_v1"
    assert row["mapping_status"] == "mapped"
    assert row["evidence_rule"] == "manual_alias"


def test_empty_records_returns_empty() -> None:
    assert _build_trigger_rows([], {"mapped"}) == []


def test_module_only_with_missing_component_skipped() -> None:
    rec = _rec("module_only", component_id=None)
    rows = _build_trigger_rows([rec], {"module_only"})
    assert rows == []
