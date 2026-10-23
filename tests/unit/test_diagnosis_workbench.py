from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from apps.ui.diagnosis_workbench.server import (
    add_conversation_turn,
    ask_field_question,
    build_feedback_record,
    build_workbench_envelope,
    create_conversation,
    delete_conversation,
    list_conversations,
    rename_conversation,
    run_workbench_case,
    save_feedback,
)


class DiagnosisWorkbenchTests(unittest.TestCase):
    def test_feedback_marks_bad_case_for_thumbs_down_and_correct_answer(self) -> None:
        base = {
            "query_id": "qry_demo",
            "answer_id": "ans_demo",
            "route_used": "route_b_document",
            "api_version": "1.0.0-draft",
            "prompt_version": "answer_assembly_v1",
            "kg_or_index_version": "route_abc_smoke_v1",
        }
        now = datetime(2026, 5, 20, tzinfo=timezone.utc)

        positive = build_feedback_record({**base, "rating": "thumbs_up"}, now=now)
        self.assertFalse(positive["bad_case_candidate"])

        thumbs_down = build_feedback_record({**base, "rating": "thumbs_down"}, now=now)
        self.assertTrue(thumbs_down["bad_case_candidate"])

        corrected = build_feedback_record(
            {**base, "rating": "thumbs_up", "correct_answer": "Use Route A"},
            now=now,
        )
        self.assertTrue(corrected["bad_case_candidate"])

        tagged = build_feedback_record(
            {**base, "rating": "thumbs_up", "feedback_tags": ["overclaim", "unknown_tag"]},
            now=now,
        )
        self.assertTrue(tagged["bad_case_candidate"])
        self.assertEqual(tagged["feedback_tags"], ["overclaim"])

    def test_feedback_jsonl_writer_appends_controlled_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feedback.jsonl"
            record = save_feedback(
                {
                    "query_id": "qry_demo",
                    "answer_id": "ans_demo",
                    "route_used": "route_c_case_governance",
                    "rating": "thumbs_down",
                },
                path=path,
            )

            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["feedback_id"], record["feedback_id"])
        self.assertTrue(record["bad_case_candidate"])

    def test_conversation_history_create_add_rename_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversations.json"
            created = create_conversation({"title": "Shift A smoke"}, path=path)
            conversation_id = created["conversation"]["conversation_id"]
            envelope = build_workbench_envelope(_minimal_answer("route_b_document", "document_evidence", "evidence_only"))

            updated = add_conversation_turn(
                {"conversation_id": conversation_id, "envelope": envelope},
                path=path,
            )
            renamed = rename_conversation(
                {"conversation_id": conversation_id, "title": "Route B evidence review"},
                path=path,
            )
            deleted = delete_conversation(conversation_id, path=path)
            remaining = list_conversations(path=path)

        self.assertEqual(len(updated["conversation"]["turns"]), 1)
        self.assertEqual(updated["turn"]["status"], "evidence_only")
        self.assertEqual(renamed["conversation"]["title"], "Route B evidence review")
        self.assertEqual(deleted["deleted"], conversation_id)
        self.assertEqual(remaining["conversations"], [])

    def test_first_turn_sets_summary_title_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversations.json"
            created = create_conversation({"title": "新的现场诊断对话"}, path=path)
            conversation_id = created["conversation"]["conversation_id"]
            answer = _minimal_answer("route_a_structured", "confirmed_diagnosis", "reviewed")
            answer["query"]["text"] = "M03CVMA-02-03 报警是什么意思？"
            envelope = build_workbench_envelope(answer)

            updated = add_conversation_turn(
                {"conversation_id": conversation_id, "envelope": envelope},
                path=path,
            )

        self.assertEqual(updated["conversation"]["title"], "M03CVMA-02-03 报警诊断")

    def test_route_samples_build_workbench_envelopes_without_promotion(self) -> None:
        # The Route A synthesis-output samples were moved out of the serving
        # eval directory into legacy/data/eval/route_a/ (worktree deletion at
        # data/eval/route_a/, byte-identical restore under legacy/). Load the
        # legacy sample directly and build the envelope the same way
        # run_workbench_case does for route "a".
        legacy_sample = (
            Path(__file__).resolve().parents[2]
            / "legacy" / "data" / "eval" / "route_a"
            / "synthesis_out_EC查询直接命中.json"
        )
        route_a_answer = json.loads(legacy_sample.read_text(encoding="utf-8"))
        route_a = build_workbench_envelope(route_a_answer)
        route_b = run_workbench_case({"route": "b", "sample_id": "RB-QB-001", "sample_kind": "query_bank"})
        route_c = run_workbench_case({"route": "c", "sample_id": "RC-QB-001", "sample_kind": "query_bank"})

        self.assertEqual(route_a["answer"]["decision"]["status"], "reviewed")
        self.assertEqual(route_b["answer"]["decision"]["answer_type"], "document_evidence")
        self.assertEqual(route_b["answer"]["decision"]["status"], "evidence_only")
        self.assertIn("evidence_only", " ".join(route_b["warnings"]))
        self.assertEqual(route_c["answer"]["decision"]["answer_type"], "case_reference")
        self.assertEqual(route_c["answer"]["decision"]["status"], "candidate")
        self.assertIn("candidate", " ".join(route_c["warnings"]).lower())

        route_b_text = json.dumps(route_b["answer"], ensure_ascii=False)
        route_c_text = json.dumps(route_c["answer"], ensure_ascii=False)
        self.assertNotIn("confirmed_diagnosis", route_b_text)
        self.assertNotIn('"status": "reviewed"', route_b_text)
        self.assertNotIn("confirmed_diagnosis", route_c_text)
        self.assertNotIn('"status": "reviewed"', route_c_text)

    def test_field_question_auto_routes_without_user_route_choice(self) -> None:
        route_a = ask_field_question({"query_text": "M03CVMA-02-03 报警是什么意思？"})
        route_b = ask_field_question({"query_text": "查询 TCP IPv4 IP 地址设置相关的 SOP 文档"})
        route_c = ask_field_question({"query_text": "cowling 组装一直 NG，类似案例有哪些？"})

        self.assertEqual(route_a["meta"]["input_mode"], "field_chat_zh")
        self.assertEqual(route_a["answer"]["decision"]["route_family"], "route_a_structured")
        self.assertEqual(route_b["meta"]["input_mode"], "field_chat_zh")
        self.assertEqual(route_b["answer"]["decision"]["route_family"], "route_b_document")
        self.assertEqual(route_b["answer"]["decision"]["status"], "evidence_only")
        self.assertEqual(route_c["answer"]["decision"]["route_family"], "route_c_case_governance")
        self.assertEqual(route_c["answer"]["decision"]["status"], "candidate")


def _minimal_answer(route_family: str, answer_type: str, status: str) -> dict:
    return {
        "contract_version": "1.0.0-draft",
        "query": {
            "text": "demo query",
            "normalized_text": "demo query",
            "language": "en",
            "received_at": "2026-05-20T00:00:00+08:00",
        },
        "decision": {
            "route_family": route_family,
            "route": "document_evidence_retrieval",
            "answer_type": answer_type,
            "status": status,
            "requires_review": False,
        },
        "entities": {"asset": {}, "diagnostic": {}, "observation": {}},
        "knowledge_context": {"used_sources": []},
        "summary": {"headline": "Demo", "user_safe_summary": "Demo summary"},
        "diagnosis_results": [],
        "root_cause": "",
        "root_cause_actions": [],
    }


if __name__ == "__main__":
    unittest.main()
