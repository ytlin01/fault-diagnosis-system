"""Deterministic canonical-mapping proposal builder for the C1STN gold set.

Maps each accepted case's source-suggested free text to reviewed cause and
repair-action IDs using a fixed, auditable alias table. This module produces
a *proposal only*: every match records its evidence pattern, matched field,
and basis (``catalog_token`` for vocabulary-derived aliases,
``interpretive_alias`` for curated bridges), and anything without evidence
stays explicitly unmapped. Nothing here is reviewed truth.
"""

from __future__ import annotations

from typing import Any, Mapping

PROPOSAL_ID = "v2_task001_c1stn_canonical_mapping_proposal_v1"
ALIAS_TABLE_VERSION = "c1stn_canonical_alias_v1"

NO_SUGGESTION_MARKERS = ("无",)

# field -> gold case path searched for alias evidence
_SEARCH_FIELDS = (
    ("error_description_zh", "source_context.error_description_zh"),
    ("error_description", "source_context.error_description"),
    ("source_suggested_repair_action", "source_context.source_suggested_repair_action"),
    ("query", "query"),
)

# Each alias: (catalog_id, pattern, basis). "catalog_token" aliases come from
# the reviewed catalog display/definition wording; "interpretive_alias" ones
# are curated bridges between source phrasing and catalog semantics and are
# the primary thing domain review must confirm or reject.
_CAUSE_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("cause.sensor.signal_abnormal", "感应器异常", "catalog_token"),
    ("cause.sensor.signal_abnormal", "传感器异常", "catalog_token"),
    ("cause.sensor.signal_abnormal", "信号超时", "interpretive_alias"),
    ("cause.sensor.signal_abnormal", "SensorFail", "catalog_token"),
    ("cause.sensor.wiring_fault", "线路异常", "catalog_token"),
    ("cause.sensor.wiring_fault", "检查线路", "interpretive_alias"),
    ("cause.sensor.position_shift", "感应器位置", "catalog_token"),
    ("cause.sensor.device_failure", "感应器本体", "catalog_token"),
    ("cause.pneumatic.cylinder_stuck", "气缸卡", "catalog_token"),
    ("cause.pneumatic.cylinder_stuck", "气缸未上升到位", "interpretive_alias"),
    ("cause.pneumatic.cylinder_stuck", "气缸未缩回到位", "interpretive_alias"),
    ("cause.pneumatic.cylinder_failure", "气缸本体", "catalog_token"),
    ("cause.pneumatic.air_supply_abnormal", "供气异常", "catalog_token"),
    ("cause.pneumatic.air_supply_abnormal", "气压异常", "catalog_token"),
    ("cause.vacuum.system_fault", "负压", "catalog_token"),
    ("cause.vacuum.system_fault", "真空", "catalog_token"),
    ("cause.safety.emergency_stop_active", "急停", "catalog_token"),
    ("cause.safety.interlock_not_satisfied", "安全门", "catalog_token"),
    ("cause.safety.interlock_not_satisfied", "联锁", "catalog_token"),
    ("cause.motion.axis_drive_fault", "轴驱动", "catalog_token"),
    ("cause.motion.axis_drive_fault", "未上使能", "interpretive_alias"),
    ("cause.motion.axis_position_abnormal", "超负限位", "interpretive_alias"),
    ("cause.motion.axis_position_abnormal", "点位是否异常", "interpretive_alias"),
    ("cause.motion.axis_position_abnormal", "轴位置异常", "catalog_token"),
    ("cause.communication.link_fault", "连接超时", "interpretive_alias"),
    ("cause.communication.link_fault", "断开连接", "interpretive_alias"),
    ("cause.communication.link_fault", "链路异常", "catalog_token"),
    ("cause.communication.cable_fault", "通讯线缆", "catalog_token"),
    ("cause.communication.config_mismatch", "IP是否正确", "interpretive_alias"),
    ("cause.communication.config_mismatch", "通讯参数", "catalog_token"),
    ("cause.vision.camera_alignment_offset", "视觉定位", "interpretive_alias"),
    ("cause.vision.camera_alignment_offset", "相机定位", "catalog_token"),
    ("cause.vision.detection_failure", "图像检测", "catalog_token"),
    ("cause.software.configuration_invalid", "配置参数异常", "catalog_token"),
    ("cause.material.missing_or_removed", "无料", "catalog_token"),
    ("cause.material.missing_or_removed", "人工上料", "interpretive_alias"),
    ("cause.mechanical.tool_wear", "磨损", "catalog_token"),
    ("cause.undetermined.insufficient_evidence", "证据不足", "catalog_token"),
)

_ACTION_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("action.sensor.inspect_wiring", "检查感应器", "catalog_token"),
    ("action.sensor.inspect_wiring", "检查线路", "catalog_token"),
    ("action.sensor.inspect_wiring", "线路或者信号", "interpretive_alias"),
    ("action.sensor.adjust_position", "调整感应器位置", "catalog_token"),
    ("action.sensor.replace", "更换感应器", "catalog_token"),
    ("action.pneumatic.test_cylinder", "测试气缸", "catalog_token"),
    ("action.pneumatic.replace_cylinder", "更换气缸", "catalog_token"),
    ("action.pneumatic.verify_air_supply", "检查供气", "catalog_token"),
    ("action.pneumatic.verify_air_supply", "负压", "interpretive_alias"),
    ("action.safety.inspect_interlock_chain", "检查安全联锁", "catalog_token"),
    ("action.safety.restore_emergency_stop", "恢复急停", "catalog_token"),
    ("action.communication.inspect_cable", "检查通讯线缆", "catalog_token"),
    ("action.communication.verify_configuration", "IP是否正确", "interpretive_alias"),
    ("action.communication.verify_configuration", "核对通讯配置", "catalog_token"),
    ("action.motion.inspect_axis_alarm", "检查轴报警", "catalog_token"),
    ("action.vision.verify_image_and_alignment", "视觉定位", "interpretive_alias"),
    ("action.software.restore_approved_configuration", "恢复批准的配置", "catalog_token"),
    ("action.mechanical.remove_obstruction", "清除机构阻碍", "catalog_token"),
    ("action.evidence.collect_alarm_and_state_snapshot", "补充报警", "catalog_token"),
    ("action.support.escalate_to_equipment_owner", "升级设备负责人", "catalog_token"),
)

_NO_CAUSE_REASON = "no alias evidence found for any reviewed cause"
_NO_ACTION_REASON_TEMPLATE = (
    "source suggestion carries no action verb or maps to no reviewed action; "
    "suggestion text: {text!r}"
)
_EMPTY_SUGGESTION_REASON = (
    "source_suggested_repair_action is a no-content marker; nothing to map"
)


def _case_text_fields(case: Mapping[str, Any]) -> dict[str, str]:
    context = case.get("source_context", {})
    return {
        "error_description_zh": str(context.get("error_description_zh", "")),
        "error_description": str(context.get("error_description", "")),
        "source_suggested_repair_action": str(
            context.get("source_suggested_repair_action", "")
        ),
        "query": str(case.get("query", "")),
    }


def _match(
    aliases: tuple[tuple[str, str, str], ...],
    fields: Mapping[str, str],
    valid_ids: set[str],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for catalog_id, pattern, basis in aliases:
        if catalog_id not in valid_ids:
            continue
        matched_in = [name for name, text in fields.items() if pattern in text]
        if not matched_in:
            continue
        entry = by_id.setdefault(
            catalog_id, {"catalog_id": catalog_id, "evidence": []}
        )
        entry["evidence"].append(
            {"pattern": pattern, "matched_in": matched_in, "basis": basis}
        )
    for entry in by_id.values():
        entry["basis_summary"] = (
            "interpretive"
            if any(ev["basis"] == "interpretive_alias" for ev in entry["evidence"])
            else "catalog_token_only"
        )
    return sorted(by_id.values(), key=lambda item: item["catalog_id"])


def build_mapping_proposal(
    gold: Mapping[str, Any],
    *,
    gold_path: str,
    gold_sha256: str,
) -> dict[str, Any]:
    """Build the canonical mapping proposal from a reviewed gold queue."""
    cases = gold.get("cases", [])
    if not cases:
        raise ValueError("gold queue has no cases")
    cause_ids = {entry["cause_id"] for entry in gold.get("cause_catalog", [])}
    action_ids = {entry["action_id"] for entry in gold.get("repair_action_catalog", [])}
    proposals: list[dict[str, Any]] = []
    for case in cases:
        fields = _case_text_fields(case)
        suggestion = fields["source_suggested_repair_action"]
        empty_suggestion = suggestion.strip() in NO_SUGGESTION_MARKERS
        if empty_suggestion:
            proposed_causes: list[dict[str, Any]] = []
            proposed_actions: list[dict[str, Any]] = []
            cause_reason = _EMPTY_SUGGESTION_REASON
            action_reason = _EMPTY_SUGGESTION_REASON
        else:
            proposed_causes = _match(_CAUSE_ALIASES, fields, cause_ids)
            proposed_actions = _match(_ACTION_ALIASES, fields, action_ids)
            cause_reason = _NO_CAUSE_REASON if not proposed_causes else ""
            action_reason = (
                _NO_ACTION_REASON_TEMPLATE.format(text=suggestion)
                if not proposed_actions
                else ""
            )
        proposals.append(
            {
                "case_id": case["case_id"],
                "scenario_id": case["scenario_id"],
                "proposed_causes": proposed_causes,
                "proposed_actions": proposed_actions,
                "unmapped_reason": {"causes": cause_reason, "actions": action_reason},
                "proposal_state": "proposed_not_reviewed",
            }
        )
    return {
        "schema_version": "route_a_canonical_mapping_proposal_v1",
        "proposal_id": PROPOSAL_ID,
        "alias_table_version": ALIAS_TABLE_VERSION,
        "derived_from": {
            "gold_queue_id": gold.get("queue_id"),
            "gold_path": gold_path,
            "gold_sha256": gold_sha256,
        },
        "review_gate": (
            "Proposal only. Every interpretive_alias bridge requires domain "
            "review before any canonical label is exported to an "
            "expert-ranking run."
        ),
        "cases": proposals,
    }
