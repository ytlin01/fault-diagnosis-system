from __future__ import annotations

import unittest

from services.canonicalization import canonicalize_query

_SAMPLE_INDEX = {
    "module": {
        "Tray上料机构": "M_9494198",
        "AE1-387-D274-10000": "M_9494197",
    },
    "component": {
        "D83-CG-Carrier-without-dut-20230210": "C_9494220",
    },
    "subcomponent": {
        "D9X组装": "SC_9494222",
        "D9X-CG": "SC_9494223",
    },
}


class CadAssetIndexTests(unittest.TestCase):
    def test_module_name_hit(self) -> None:
        state = canonicalize_query("Tray上料机构出现异常", asset_index=_SAMPLE_INDEX)
        slot = state.entities["asset"]["module"]
        self.assertEqual(slot.canonical, "M_9494198")
        self.assertEqual(slot.raw, "Tray上料机构")
        self.assertEqual(slot.confidence, "medium")

    def test_component_name_hit(self) -> None:
        state = canonicalize_query(
            "D83-CG-Carrier-without-dut-20230210 发生卡料", asset_index=_SAMPLE_INDEX
        )
        slot = state.entities["asset"]["component"]
        self.assertEqual(slot.canonical, "C_9494220")

    def test_subcomponent_name_hit(self) -> None:
        state = canonicalize_query("D9X组装位置偏移报警", asset_index=_SAMPLE_INDEX)
        slot = state.entities["asset"]["subcomponent"]
        self.assertEqual(slot.canonical, "SC_9494222")
        self.assertEqual(slot.raw, "D9X组装")

    def test_subcomponent_wins_over_module_when_longer(self) -> None:
        # "D9X组装" (4 chars) is longer than any module name that might match
        # — verifies that longest-match wins regardless of level order
        index = {
            "module": {"D9X": "M_FAKE"},
            "component": {},
            "subcomponent": {"D9X组装": "SC_9494222"},
        }
        state = canonicalize_query("D9X组装发生错误", asset_index=index)
        sc_slot = state.entities["asset"]["subcomponent"]
        self.assertEqual(sc_slot.canonical, "SC_9494222")
        # module slot should be empty because subcomponent matched more specifically
        m_slot = state.entities["asset"]["module"]
        self.assertIsNone(m_slot.canonical)

    def test_no_match_returns_empty_slots(self) -> None:
        state = canonicalize_query("完全无关的查询内容", asset_index=_SAMPLE_INDEX)
        for slot_name in ("module", "component", "subcomponent"):
            slot = state.entities["asset"][slot_name]
            self.assertIsNone(slot.canonical)

    def test_no_index_falls_back_to_hardcoded_detect_module(self) -> None:
        state = canonicalize_query("cowling组装一直NG，昨天也是")
        slot = state.entities["asset"]["module"]
        self.assertEqual(slot.canonical, "cowling组装模块")

    def test_no_index_subcomponent_slot_exists_and_is_empty(self) -> None:
        state = canonicalize_query("cowling报错")
        self.assertIn("subcomponent", state.entities["asset"])
        self.assertIsNone(state.entities["asset"]["subcomponent"].canonical)

    def test_empty_index_does_not_error(self) -> None:
        empty_index: dict = {"module": {}, "component": {}, "subcomponent": {}}
        state = canonicalize_query("任意查询", asset_index=empty_index)
        self.assertIsNone(state.entities["asset"]["module"].canonical)

    def test_result_projection_includes_subcomponent_slot(self) -> None:
        state = canonicalize_query("D9X组装报警", asset_index=_SAMPLE_INDEX)
        projection = state.result_projection()
        self.assertIn("subcomponent", projection["entities"]["asset"])
