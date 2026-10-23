"""Local Diagnosis Workbench bridge for TASK-014.

This server is intentionally small and local-first. It serves the static
Workbench UI, loads serving-safe Route A/B/C smoke outputs, stores feedback as
JSONL, and stores lightweight conversation history for internal review.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import mimetypes
import os
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC_DIR = Path(__file__).resolve().parent
ROUTE_A_DIR = REPO_ROOT / "data" / "eval" / "route_a"
ROUTE_A_FIXTURES_PATH = ROUTE_A_DIR / "route_a_serving_safe_fixtures_v1.json"
STATE_DIR = REPO_ROOT / "tmp" / "diagnosis_workbench"
FEEDBACK_LOG_PATH = STATE_DIR / "feedback_v1.jsonl"
CONVERSATIONS_PATH = STATE_DIR / "conversations_v1.json"

PROMPT_VERSION = "answer_assembly_v1"
KG_OR_INDEX_VERSION = "route_abc_smoke_v1"
FIELD_UI_DEFAULT_SOURCES = (
    "reviewed_diagnostic_chain_v1",
    "asset_kg_v1",
    "data/serving_unstructured_vlm",
    "rag_fp_case_candidates_v1",
    "error_codes_standardized_serving",
)
ALLOWED_FEEDBACK_TAGS = {
    "answer_wrong",
    "evidence_insufficient",
    "route_wrong",
    "overclaim",
    "not_useful",
}
BAD_CASE_TAGS = {
    "answer_wrong",
    "evidence_insufficient",
    "route_wrong",
    "overclaim",
}
ROUTE_LABELS = {
    "route_a_structured": "结构化诊断",
    "route_b_document": "文档证据",
    "route_c_case_governance": "相似案例",
    "fallback": "Fallback",
}
ROUTE_TO_STATUS_WARNING = {
    "route_b_document": "当前为文档证据路径：结果是 evidence_only，只能作为文档依据，不能当作已确认诊断。",
    "route_c_case_governance": "当前为相似案例路径：结果是 candidate，采取行动前需要人工确认。",
    "fallback": "当前上下文不足，系统未进入可服务诊断路径。",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="FaultDx Diagnosis Workbench local bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--provider", default=None, help="stub (default) | ollama — overrides FAULTDX_PROVIDER_TYPE")
    args = parser.parse_args()
    if args.provider:
        os.environ["FAULTDX_PROVIDER_TYPE"] = args.provider

    server = ThreadingHTTPServer((args.host, args.port), WorkbenchHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Diagnosis Workbench: {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Diagnosis Workbench.")
    finally:
        server.server_close()


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "FaultDxDiagnosisWorkbench/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/samples":
                self._send_json(sample_catalog())
                return
            if parsed.path == "/api/conversations":
                self._send_json(list_conversations())
                return
            if parsed.path == "/":
                self._send_file(STATIC_DIR / "index.html")
                return
            candidate = (STATIC_DIR / parsed.path.lstrip("/")).resolve()
            if STATIC_DIR.resolve() not in candidate.parents and candidate != STATIC_DIR.resolve():
                self._send_error(404, "File not found")
                return
            self._send_file(candidate)
        except Exception as exc:  # pragma: no cover - HTTP safety net.
            self._send_error(500, str(exc))

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/run":
                envelope = run_workbench_case(payload)
                self._send_json(envelope)
                return
            if parsed.path == "/api/ask":
                envelope = ask_field_question(payload)
                self._send_json(envelope)
                return
            if parsed.path == "/api/feedback":
                record = save_feedback(payload)
                self._send_json({"ok": True, "feedback": record})
                return
            if parsed.path == "/api/conversations":
                self._send_json(create_conversation(payload))
                return
            if parsed.path == "/api/conversations/add-turn":
                self._send_json(add_conversation_turn(payload))
                return
            if parsed.path == "/api/conversations/rename":
                self._send_json(rename_conversation(payload))
                return
            self._send_error(404, "API route not found")
        except Exception as exc:  # pragma: no cover - HTTP safety net.
            self._send_error(400, str(exc))

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/conversations":
                query = parse_qs(parsed.query)
                conversation_id = str((query.get("id") or [""])[0])
                self._send_json(delete_conversation(conversation_id))
                return
            self._send_error(404, "API route not found")
        except Exception as exc:  # pragma: no cover - HTTP safety net.
            self._send_error(400, str(exc))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _send_json(self, payload: Mapping[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(404, "File not found")
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status=status)


def sample_catalog() -> dict[str, Any]:
    return {
        "route_a": [
            {"id": path.name, "label": path.stem, "kind": "route_a_file"}
            for path in sorted(ROUTE_A_DIR.glob("*.json"))
        ],
        "route_b": [
            {"id": "RB-QB-001", "label": "Route B normal evidence", "kind": "query_bank"},
            {"id": "RB-QB-002", "label": "Route B no hit", "kind": "query_bank"},
            {"id": "RB-SAFE-001", "label": "Route B fixture evidence", "kind": "fixture"},
        ],
        "route_c": [
            {"id": "RC-QB-001", "label": "Route C normal candidate", "kind": "query_bank"},
            {"id": "RC-QB-002", "label": "Route C no hit", "kind": "query_bank"},
            {"id": "RC-SAFE-001", "label": "Route C fixture candidate", "kind": "fixture"},
        ],
    }


def run_workbench_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    route = str(payload.get("route") or "a").lower()
    sample_id = str(payload.get("sample_id") or "")
    sample_kind = str(payload.get("sample_kind") or "query_bank")
    provider = _stub_provider()

    if route == "a":
        answer = _load_route_a_answer(sample_id)
    elif route in {"b", "c"}:
        import scripts.cli_route_abc as cli_route_abc

        if sample_kind == "fixture" or sample_id.startswith(("RB-SAFE-", "RC-SAFE-")):
            fixture_name = "route_b" if route == "b" else "route_c"
            answer = cli_route_abc._run_fixture(fixture_name, sample_id, 0, provider)
        else:
            answer = cli_route_abc._run_query_bank(route, sample_id, provider)
    else:
        raise ValueError(f"Unsupported route: {route}")

    return build_workbench_envelope(answer)


def _match_demo_shortcut(query_text: str) -> dict[str, Any] | None:
    normalized = re.sub(r"\s+", " ", query_text).strip().lower()
    if not normalized:
        return None
    if _is_route_b_demo_query(normalized):
        return run_workbench_case({"route": "b", "sample_id": "RB-QB-001", "sample_kind": "query_bank"})
    if _is_route_c_demo_query(normalized):
        return run_workbench_case({"route": "c", "sample_id": "RC-QB-001", "sample_kind": "query_bank"})
    return None


def _is_route_b_demo_query(normalized: str) -> bool:
    return (
        "tcp ipv4" in normalized
        and (
            "sop" in normalized
            or "文档" in normalized
            or "ip 地址设置" in normalized
            or "ip address settings" in normalized
        )
    )


def _is_route_c_demo_query(normalized: str) -> bool:
    return (
        "cowling" in normalized
        and (
            "案例" in normalized
            or "相似" in normalized
            or "ng" in normalized
            or "missing pin positioning" in normalized
        )
    )


def ask_field_question(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Run one field-operator question through the existing route graph.

    The UI does not expose router choices. Route selection remains a backend
    decision and is reflected only as answer boundary metadata.
    """

    query_text = str(payload.get("query_text") or payload.get("text") or "").strip()
    if not query_text:
        raise ValueError("query_text is required")
    shortcut_envelope = _match_demo_shortcut(query_text)
    if shortcut_envelope is not None:
        shortcut_envelope["meta"]["input_mode"] = "field_chat_zh"
        shortcut_envelope["meta"]["demo_shortcut_used"] = True
        return shortcut_envelope
    fixture_answer = _load_route_a_fixture_by_query(query_text)
    if fixture_answer is not None:
        envelope = build_workbench_envelope(fixture_answer)
        envelope["meta"]["input_mode"] = "field_chat_zh"
        envelope["meta"]["route_a_demo_fixture"] = True
        return envelope
    contextual_query = _contextual_query(query_text, str(payload.get("conversation_id") or ""))
    from services.providers.llm import build_provider
    from services.reasoning.route_graph import run_route_graph_dry_run

    state = run_route_graph_dry_run(
        {
            "query_text": contextual_query,
            "language": "zh-CN",
            "available_sources": list(FIELD_UI_DEFAULT_SOURCES),
            "_provider": build_provider(),
        }
    )
    answer = dict(state.get("api_response") or {})
    # Keep the user's actual wording visible even if the bridge expanded context
    # for a short follow-up.
    query = answer.get("query")
    if isinstance(query, dict):
        query["text"] = query_text
    envelope = build_workbench_envelope(answer)
    envelope["meta"]["input_mode"] = "field_chat_zh"
    if contextual_query != query_text:
        envelope["meta"]["contextual_query_used"] = True
    return envelope


def build_workbench_envelope(answer: Mapping[str, Any]) -> dict[str, Any]:
    decision = _mapping(answer.get("decision"))
    route_family = str(decision.get("route_family") or "fallback")
    answer_id = stable_answer_id(answer)
    query_id = stable_query_id(answer)
    warnings = safety_warnings(answer)
    return {
        "answer": dict(answer),
        "meta": {
            "answer_id": answer_id,
            "query_id": query_id,
            "route_label": ROUTE_LABELS.get(route_family, route_family),
            "prompt_version": PROMPT_VERSION,
            "kg_or_index_version": KG_OR_INDEX_VERSION,
        },
        "warnings": warnings,
    }


def safety_warnings(answer: Mapping[str, Any]) -> list[str]:
    decision = _mapping(answer.get("decision"))
    route_family = str(decision.get("route_family") or "fallback")
    status = str(decision.get("status") or "")
    warnings = [str(item) for item in answer.get("warnings") or []]
    if route_family in ROUTE_TO_STATUS_WARNING:
        warnings.append(ROUTE_TO_STATUS_WARNING[route_family])
    if status == "candidate":
        warnings.append("candidate 结果不是 reviewed 诊断事实。")
    if status == "evidence_only":
        warnings.append("evidence_only 结果需要人工结合现场上下文解释。")
    if not answer.get("diagnosis_results"):
        warnings.append("本次回答没有组装到 diagnosis_results。")
    return _dedupe(warnings)


def save_feedback(payload: Mapping[str, Any], path: Path = FEEDBACK_LOG_PATH) -> dict[str, Any]:
    record = build_feedback_record(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def build_feedback_record(payload: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    rating = str(payload.get("rating") or "")
    if rating not in {"thumbs_up", "thumbs_down"}:
        raise ValueError("rating must be thumbs_up or thumbs_down")
    tags = [str(item) for item in payload.get("feedback_tags") or []]
    tags = [tag for tag in tags if tag in ALLOWED_FEEDBACK_TAGS]
    correct_answer = str(payload.get("correct_answer") or "").strip()
    bad_case_candidate = (
        rating == "thumbs_down"
        or bool(correct_answer)
        or bool(BAD_CASE_TAGS.intersection(tags))
    )
    created_at = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "feedback_id": f"fb_{uuid.uuid4().hex[:12]}",
        "query_id": str(payload.get("query_id") or ""),
        "answer_id": str(payload.get("answer_id") or ""),
        "route_used": str(payload.get("route_used") or ""),
        "rating": rating,
        "feedback_tags": tags,
        "free_text": str(payload.get("free_text") or "").strip(),
        "correct_answer": correct_answer,
        "expected_route": str(payload.get("expected_route") or "").strip(),
        "bad_case_candidate": bad_case_candidate,
        "created_by_role": str(payload.get("created_by_role") or "tester"),
        "api_version": str(payload.get("api_version") or "1.0.0-draft"),
        "prompt_version": str(payload.get("prompt_version") or PROMPT_VERSION),
        "kg_or_index_version": str(payload.get("kg_or_index_version") or KG_OR_INDEX_VERSION),
        "created_at": created_at,
    }


def list_conversations(path: Path = CONVERSATIONS_PATH) -> dict[str, Any]:
    return _load_conversation_state(path)


def create_conversation(payload: Mapping[str, Any], path: Path = CONVERSATIONS_PATH) -> dict[str, Any]:
    state = _load_conversation_state(path)
    title = str(payload.get("title") or "New diagnosis thread").strip()[:80]
    now = _now()
    conversation = {
        "conversation_id": f"conv_{uuid.uuid4().hex[:12]}",
        "title": title or "New diagnosis thread",
        "created_at": now,
        "updated_at": now,
        "turns": [],
    }
    state["conversations"].insert(0, conversation)
    _save_conversation_state(state, path)
    return {"ok": True, "conversation": conversation}


def _auto_title(query_text: str) -> str | None:
    """Call the configured LLM to generate a short conversation title (≤20 chars).
    Returns None on any failure so callers can fall back silently."""
    from services.providers.llm import build_provider, ProviderRequest
    try:
        provider = build_provider()
        if provider.provider_type == "stub":
            return None
        prompt = f"用不超过15个汉字概括以下故障诊断问题的主题，只输出主题词，不加标点：\n{query_text}"
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(provider.generate, ProviderRequest(prompt=prompt))
            resp = future.result(timeout=5)
        title = resp.text.strip().split("\n")[0][:20]
        return title or None
    except Exception:
        return None


def _update_title_async(conversation_id: str, first_query: str, path: Path) -> None:
    """Background thread: update conversation title via LLM after the 2nd turn."""
    title = _auto_title(first_query)
    if not title:
        return
    try:
        state = _load_conversation_state(path)
        conv = _find_conversation(state, conversation_id)
        conv["title"] = title
        conv["updated_at"] = _now()
        _save_conversation_state(state, path)
    except Exception:
        pass


def add_conversation_turn(payload: Mapping[str, Any], path: Path = CONVERSATIONS_PATH) -> dict[str, Any]:
    conversation_id = str(payload.get("conversation_id") or "")
    envelope = _mapping(payload.get("envelope"))
    answer = _mapping(envelope.get("answer"))
    meta = _mapping(envelope.get("meta"))
    query = _mapping(answer.get("query"))
    decision = _mapping(answer.get("decision"))
    summary = _mapping(answer.get("summary"))
    turn = {
        "turn_id": f"turn_{uuid.uuid4().hex[:12]}",
        "query_text": str(query.get("text") or ""),
        "answer_id": str(meta.get("answer_id") or stable_answer_id(answer)),
        "query_id": str(meta.get("query_id") or stable_query_id(answer)),
        "route_family": str(decision.get("route_family") or ""),
        "answer_type": str(decision.get("answer_type") or ""),
        "status": str(decision.get("status") or ""),
        "headline": str(summary.get("headline") or ""),
        "answer": dict(answer),
        "warnings": list(envelope.get("warnings") or []),
        "created_at": _now(),
    }
    state = _load_conversation_state(path)
    conversation = _find_conversation(state, conversation_id)
    conversation["turns"].append(turn)
    conversation["updated_at"] = turn["created_at"]
    turns_count = len(conversation["turns"])
    if turns_count == 1 and turn["query_text"]:
        conversation["title"] = _default_title(turn["query_text"])
    elif turns_count == 2:
        first_query = conversation["turns"][0].get("query_text", "")
        if first_query:
            threading.Thread(
                target=_update_title_async,
                args=(conversation["conversation_id"], first_query, path),
                daemon=True,
            ).start()
    _save_conversation_state(state, path)
    return {"ok": True, "conversation": conversation, "turn": turn}


def rename_conversation(payload: Mapping[str, Any], path: Path = CONVERSATIONS_PATH) -> dict[str, Any]:
    conversation_id = str(payload.get("conversation_id") or "")
    title = str(payload.get("title") or "").strip()[:80]
    if not title:
        raise ValueError("title is required")
    state = _load_conversation_state(path)
    conversation = _find_conversation(state, conversation_id)
    conversation["title"] = title
    conversation["updated_at"] = _now()
    _save_conversation_state(state, path)
    return {"ok": True, "conversation": conversation}


def delete_conversation(conversation_id: str, path: Path = CONVERSATIONS_PATH) -> dict[str, Any]:
    if not conversation_id:
        raise ValueError("conversation id is required")
    state = _load_conversation_state(path)
    before = len(state["conversations"])
    state["conversations"] = [
        item for item in state["conversations"] if item.get("conversation_id") != conversation_id
    ]
    if len(state["conversations"]) == before:
        raise ValueError(f"conversation not found: {conversation_id}")
    _save_conversation_state(state, path)
    return {"ok": True, "deleted": conversation_id}


def stable_answer_id(answer: Mapping[str, Any]) -> str:
    decision = _mapping(answer.get("decision"))
    query = _mapping(answer.get("query"))
    seed = "|".join(
        [
            str(query.get("text") or ""),
            str(decision.get("route_family") or ""),
            str(decision.get("answer_type") or ""),
            str(decision.get("status") or ""),
            json.dumps(answer.get("diagnosis_results") or [], ensure_ascii=False, sort_keys=True),
        ]
    )
    return "ans_" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]


def stable_query_id(answer: Mapping[str, Any]) -> str:
    query = _mapping(answer.get("query"))
    seed = "|".join([str(query.get("text") or ""), str(query.get("received_at") or "")])
    return "qry_" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]


def _load_route_a_answer(sample_id: str) -> dict[str, Any]:
    candidates = {path.name: path for path in ROUTE_A_DIR.glob("*.json")}
    if sample_id not in candidates:
        raise ValueError(f"Unknown Route A sample: {sample_id}")
    return json.loads(candidates[sample_id].read_text(encoding="utf-8"))


def _load_route_a_fixture_by_query(query_text: str) -> dict[str, Any] | None:
    if not ROUTE_A_FIXTURES_PATH.exists():
        return None
    normalized = re.sub(r"\s+", " ", query_text).strip().lower()
    payload = json.loads(ROUTE_A_FIXTURES_PATH.read_text(encoding="utf-8"))
    for item in payload.get("fixtures") or []:
        fixture_query = re.sub(r"\s+", " ", str(item.get("query") or "")).strip().lower()
        if fixture_query != normalized:
            continue
        answer = item.get("api_or_route_output")
        if isinstance(answer, Mapping):
            return dict(answer)
    return None


def _contextual_query(query_text: str, conversation_id: str) -> str:
    if not conversation_id or len(query_text) >= 16:
        return query_text
    try:
        conversation = _find_conversation(_load_conversation_state(CONVERSATIONS_PATH), conversation_id)
    except Exception:
        return query_text
    turns = conversation.get("turns") or []
    if not turns:
        return query_text
    last = turns[-1]
    previous_query = str(last.get("query_text") or "").strip()
    previous_headline = str(last.get("headline") or "").strip()
    if not previous_query and not previous_headline:
        return query_text
    context = "；".join(item for item in (previous_query, previous_headline) if item)
    return f"上一轮上下文：{context}。现场追问：{query_text}"


def _load_conversation_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "diagnosis_workbench_conversations_v1", "conversations": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("conversations"), list):
        raise ValueError(f"Invalid conversation state: {path}")
    payload.setdefault("schema_version", "diagnosis_workbench_conversations_v1")
    return payload


def _save_conversation_state(state: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_conversation(state: Mapping[str, Any], conversation_id: str) -> dict[str, Any]:
    conversations = state.get("conversations") or []
    for item in conversations:
        if isinstance(item, dict) and item.get("conversation_id") == conversation_id:
            return item
    raise ValueError(f"conversation not found: {conversation_id}")


def _stub_provider() -> Any:
    from services.providers.llm import StubProvider

    return StubProvider()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _default_title(query: str) -> str:
    title = re.sub(r"\s+", " ", query).strip()
    alarm_code = _extract_alarm_code(title)
    upper_title = title.upper()

    if alarm_code and any(token in title for token in ("报警", "故障", "报错", "含义", "处理", "诊断", "什么意思")):
        suffix = "处理建议" if any(token in title for token in ("处理", "排查", "下一步")) else "报警诊断"
        return _truncate_title(f"{alarm_code} {suffix}", 18)

    if "SOP" in upper_title or any(token in title for token in ("文档", "配置", "设置")):
        subject = _extract_title_subject(title, {"查询", "相关", "SOP", "文档", "配置", "设置", "步骤"})
        return _truncate_title(f"{subject} 文档查询" if subject else "文档查询", 18)

    if any(token in title for token in ("案例", "相似", "经验")):
        subject = _extract_title_subject(title, {"类似", "案例", "相似", "有哪些", "经验", "看看"})
        return _truncate_title(f"{subject} 案例参考" if subject else "案例参考", 18)

    if any(token in title for token in ("下一步", "继续", "追问")):
        subject = _extract_title_subject(title, {"继续", "追问", "下一步", "怎么", "如何"})
        return _truncate_title(f"{subject} 现场追问" if subject else "现场追问", 18)

    subject = _extract_title_subject(title, {"请问", "帮我", "看看", "一下", "是什么", "什么意思", "怎么办", "如何", "怎么"})
    return _truncate_title(subject or title or "现场诊断对话", 18)


def _extract_alarm_code(text: str) -> str | None:
    match = re.search(r"\b[A-Z0-9]{3,}(?:-[A-Z0-9]{2,})+\b", text.upper())
    return match.group(0) if match else None


def _extract_title_subject(text: str, stop_words: set[str]) -> str:
    subject = re.sub(r"[？?！!。，“”\"'：:；;（）()]", " ", text)
    subject = re.sub(r"\s+", " ", subject).strip()
    if not subject:
        return ""

    if re.search(r"[A-Za-z]", subject):
        parts = [part for part in subject.split(" ") if part and part.lower() not in {word.lower() for word in stop_words}]
        return " ".join(parts[:4]).strip()

    for word in stop_words:
        subject = subject.replace(word, " ")
    subject = re.sub(r"\s+", " ", subject).strip()
    return subject


def _truncate_title(title: str, limit: int) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    return title[:limit] + ("…" if len(title) > limit else "")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    main()
