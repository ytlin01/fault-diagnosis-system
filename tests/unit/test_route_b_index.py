from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.retrieval.route_b_index import (
    build_route_b_chunks_from_document,
    rank_chunks_bm25,
    search_route_b_documents,
    tokenize_for_route_b,
)


class RouteBIndexTests(unittest.TestCase):
    def test_vlm_text_is_split_by_sections_and_length(self) -> None:
        payload = {
            "doc_id": "demo_doc",
            "blocks": [
                {
                    "block_id": "b1",
                    "block_type": "vlm_text",
                    "text": (
                        "Visual summary: camera setup screen. "
                        "Extracted text: " + ("servo motor calibration " * 20) +
                        "Candidate entities: servo motor; calibration. "
                        "Review notes: verify visually."
                    ),
                    "serving_eligible": True,
                    "retrieval_eligible": True,
                    "needs_review": True,
                    "asset_ref": "must_not_enter_chunk",
                    "raw_response": "must_not_enter_chunk",
                }
            ],
        }

        chunks = build_route_b_chunks_from_document(
            payload,
            source_name="demo_serving.json",
            source_id="data/serving_unstructured_vlm",
            max_chunk_chars=120,
        )

        labels = {chunk.section_label for chunk in chunks}
        self.assertIn("Visual summary", labels)
        self.assertIn("Extracted text", labels)
        self.assertIn("Candidate entities", labels)
        self.assertGreater(len([chunk for chunk in chunks if chunk.section_label == "Extracted text"]), 1)
        self.assertTrue(all(chunk.block_id == "b1" for chunk in chunks))
        self.assertTrue(all(chunk.needs_review for chunk in chunks))
        self.assertNotIn("asset_ref", json.dumps([chunk.__dict__ for chunk in chunks], ensure_ascii=False))
        self.assertNotIn("raw_response", json.dumps([chunk.__dict__ for chunk in chunks], ensure_ascii=False))

    def test_tokenizer_keeps_model_tokens_and_cjk_ngrams(self) -> None:
        tokens = tokenize_for_route_b("LBAS-GE120-09M 伺服电机异常 TCP/IPv4")

        self.assertIn("lbas-ge120-09m", tokens)
        self.assertIn("ge120", tokens)
        self.assertIn("09m", tokens)
        self.assertIn("tcp/ipv4", tokens)
        self.assertIn("ipv4", tokens)
        self.assertIn("伺服", tokens)
        self.assertIn("电机", tokens)
        self.assertIn("伺服电", tokens)

    def test_bm25_ranks_mixed_language_serving_chunks(self) -> None:
        chunks = build_route_b_chunks_from_document(
            {
                "doc_id": "demo_doc",
                "blocks": [
                    {
                        "block_id": "b1",
                        "block_type": "text",
                        "text": "network setup and generic SOP",
                    },
                    {
                        "block_id": "b2",
                        "block_type": "vlm_text",
                        "text": "Visual summary: 伺服电机异常报警画面. Extracted text: servo motor fault",
                    },
                ],
            },
            source_name="demo_serving.json",
            source_id="data/serving_unstructured_vlm",
        )

        hits = rank_chunks_bm25("伺服电机异常", chunks, top_k=1)

        self.assertEqual(hits[0].chunk.block_id, "b2")
        self.assertEqual(hits[0].chunk.source_type, "serving_document")

    def test_vlm_context_keeps_same_block_sections_for_answering(self) -> None:
        chunks = build_route_b_chunks_from_document(
            {
                "doc_id": "tcp_doc",
                "blocks": [
                    {
                        "block_id": "b1203",
                        "block_type": "vlm_text",
                        "text": (
                            "Visual summary: Windows系统网络属性设置界面，展示TCP/IPv4协议IP配置选项。 "
                            "Extracted text: Internet协议版本4 (TCP/IPv4) 属性，IP地址: 192.168.3.0，"
                            "子网掩码: 255.255.255.0，默认网关和DNS服务器选项。 "
                            "Candidate entities: Internet协议版本4; TCP/IPv4; IP地址; 子网掩码; 默认网关. "
                            "Review notes: 建议人工复核IP地址格式。"
                        ),
                    }
                ],
            },
            source_name="tcp_serving.json",
            source_id="data/serving_unstructured_vlm",
        )

        entity_chunk = next(chunk for chunk in chunks if chunk.section_label == "Candidate entities")

        self.assertIn("视觉摘要", entity_chunk.summary)
        self.assertIn("提取文本", entity_chunk.summary)
        self.assertIn("192.168.3.0", entity_chunk.summary)
        self.assertIn("候选实体", entity_chunk.summary)

    def test_section_weight_prefers_extracted_text_over_entity_list(self) -> None:
        chunks = build_route_b_chunks_from_document(
            {
                "doc_id": "tcp_doc",
                "blocks": [
                    {
                        "block_id": "b1203",
                        "block_type": "vlm_text",
                        "text": (
                            "Visual summary: TCP IPv4配置界面。 "
                            "Extracted text: TCP/IPv4 IP地址 子网掩码 默认网关 DNS服务器 手动设置IP地址。 "
                            "Candidate entities: TCP/IPv4; IP地址; 子网掩码; 默认网关; DNS服务器. "
                            "Review notes: 需要人工复核。"
                        ),
                    }
                ],
            },
            source_name="tcp_serving.json",
            source_id="data/serving_unstructured_vlm",
        )

        hits = rank_chunks_bm25("TCP IPv4 IP地址 子网掩码 默认网关", chunks, top_k=2)

        self.assertEqual(hits[0].chunk.section_label, "Extracted text")

    def test_search_directory_returns_evidence_ready_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "serving"
            source_dir.mkdir()
            _write_json(
                source_dir / "demo_serving.json",
                {
                    "doc_id": "demo_doc",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "block_type": "table",
                            "table": {"rows": [["step", "action"], ["1", "feeder calibration"]]},
                            "serving_eligible": True,
                            "retrieval_eligible": True,
                        },
                        {
                            "block_id": "b2",
                            "block_type": "image",
                            "asset_local_path": "must_not_be_indexed",
                            "serving_eligible": True,
                            "retrieval_eligible": True,
                        },
                    ],
                },
            )

            hits = search_route_b_documents(
                "feeder calibration",
                source_dir=source_dir,
                source_id="data/serving_unstructured_vlm",
                top_k=3,
            )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].chunk.block_type, "table")
        self.assertEqual(hits[0].chunk.anchor, "b1")
        self.assertIn("data/serving_unstructured_vlm:demo_doc:b1:c0000", hits[0].chunk.source_id)

    def test_search_directory_dedupes_multiple_sections_from_same_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "serving"
            source_dir.mkdir()
            _write_json(
                source_dir / "demo_serving.json",
                {
                    "doc_id": "demo_doc",
                    "blocks": [
                        {
                            "block_id": "b1",
                            "block_type": "vlm_text",
                            "text": (
                                "Visual summary: TCP IPv4设置界面。 "
                                "Extracted text: TCP/IPv4 IP地址 子网掩码 默认网关 DNS服务器。 "
                                "Candidate entities: TCP/IPv4; IP地址; 子网掩码; 默认网关. "
                                "Review notes: 需要复核。"
                            ),
                        },
                        {
                            "block_id": "b2",
                            "block_type": "text",
                            "text": "TCP IPv4 网络配置补充说明",
                        },
                    ],
                },
            )

            hits = search_route_b_documents(
                "TCP IPv4 IP地址 子网掩码",
                source_dir=source_dir,
                source_id="data/serving_unstructured_vlm",
                top_k=3,
            )

        block_ids = [hit.chunk.block_id for hit in hits]
        self.assertEqual(block_ids.count("b1"), 1)
        self.assertIn("b2", block_ids)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
