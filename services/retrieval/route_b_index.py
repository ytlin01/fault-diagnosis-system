"""Route B serving-document chunking and lexical retrieval."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROUTE_B_BLOCK_TYPES = {"text", "table", "vlm_text"}
VLM_SECTION_LABELS = (
    "Visual summary",
    "Extracted text",
    "Candidate entities",
    "Review notes",
)
VLM_CONTEXT_LABELS = {
    "Visual summary": "视觉摘要",
    "Extracted text": "提取文本",
    "Candidate entities": "候选实体",
    "Review notes": "复核备注",
}
VLM_SECTION_SCORE_WEIGHTS = {
    "Visual summary": 1.15,
    "Extracted text": 1.35,
    "Candidate entities": 0.45,
    "Review notes": 0.35,
}
DEFAULT_MAX_CHUNK_CHARS = 800
DEFAULT_CHUNK_OVERLAP = 80
DEFAULT_CONTEXT_CHARS = 1200

_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


@dataclass(frozen=True)
class RouteBDocumentChunk:
    """Evidence-ready retrieval chunk built only from serving-safe blocks."""

    chunk_id: str
    chunk_text: str
    chunk_index: int
    doc_id: str
    block_id: str
    block_type: str
    source_name: str
    source_id: str
    anchor: str | None
    reviewed: bool
    serving_safe: bool
    needs_review: bool
    section_label: str | None = None
    context_text: str | None = None
    evidence_type: str = "document_snippet"
    source_type: str = "serving_document"

    @property
    def summary(self) -> str:
        return truncate_text(self.context_text or self.chunk_text, 720)


@dataclass(frozen=True)
class RouteBSearchHit:
    """Ranked lexical retrieval hit."""

    chunk: RouteBDocumentChunk
    score: float


def search_route_b_documents(
    query_text: str,
    *,
    source_dir: str | Path,
    source_id: str,
    top_k: int,
    warnings: list[str] | None = None,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[RouteBSearchHit]:
    chunks = build_route_b_chunks_from_directory(
        source_dir,
        source_id=source_id,
        warnings=warnings,
        max_chunk_chars=max_chunk_chars,
    )
    ranked_hits = rank_chunks_bm25(query_text, chunks, top_k=max(top_k * 4, top_k))
    return _dedupe_hits_by_block(ranked_hits, top_k=top_k)


def build_route_b_chunks_from_directory(
    source_dir: str | Path,
    *,
    source_id: str,
    warnings: list[str] | None = None,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[RouteBDocumentChunk]:
    source_path = Path(source_dir)
    chunks: list[RouteBDocumentChunk] = []
    for path in sorted(source_path.glob("*.json")):
        payload = _load_json(path, warnings)
        if not isinstance(payload, Mapping):
            continue
        chunks.extend(
            build_route_b_chunks_from_document(
                payload,
                source_name=path.name,
                source_id=source_id,
                max_chunk_chars=max_chunk_chars,
            )
        )
    return chunks


def build_route_b_chunks_from_document(
    document: Mapping[str, Any],
    *,
    source_name: str,
    source_id: str,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[RouteBDocumentChunk]:
    doc_id = str(document.get("doc_id") or Path(source_name).stem)
    chunks: list[RouteBDocumentChunk] = []
    for block in _iter_safe_blocks(document):
        block_type = str(block.get("block_type") or "text")
        block_id = str(block.get("block_id") or block.get("block_index") or "block")
        text = _block_text(block)
        if not text:
            continue
        parts = _split_block_text(block_type, text, max_chunk_chars=max_chunk_chars)
        context_text = _context_text_for_block(block_type, parts)
        for chunk_index, (section_label, chunk_text) in enumerate(parts):
            chunk_id = f"{doc_id}:{block_id}:c{chunk_index:04d}"
            chunks.append(
                RouteBDocumentChunk(
                    chunk_id=chunk_id,
                    chunk_text=chunk_text,
                    chunk_index=chunk_index,
                    doc_id=doc_id,
                    block_id=block_id,
                    block_type=block_type,
                    source_name=source_name,
                    source_id=f"{source_id}:{chunk_id}",
                    anchor=block_id or None,
                    reviewed=False,
                    serving_safe=True,
                    needs_review=bool(block.get("needs_review", False)),
                    section_label=section_label,
                    context_text=context_text,
                )
            )
    return chunks


def rank_chunks_bm25(
    query_text: str,
    chunks: Sequence[RouteBDocumentChunk],
    *,
    top_k: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[RouteBSearchHit]:
    if top_k <= 0:
        return []

    query_tokens = tokenize_for_route_b(query_text)
    if not query_tokens:
        return []

    tokenized_chunks = [tokenize_for_route_b(chunk.chunk_text) for chunk in chunks]
    if not tokenized_chunks:
        return []

    doc_count = len(tokenized_chunks)
    lengths = [len(tokens) for tokens in tokenized_chunks]
    avg_len = sum(lengths) / doc_count if doc_count else 0.0
    if avg_len <= 0:
        return []

    doc_freq: Counter[str] = Counter()
    for tokens in tokenized_chunks:
        doc_freq.update(set(tokens))

    query_counter = Counter(query_tokens)
    hits: list[RouteBSearchHit] = []
    for chunk, tokens, length in zip(chunks, tokenized_chunks, lengths):
        if not tokens:
            continue
        token_counts = Counter(tokens)
        score = 0.0
        for token, query_weight in query_counter.items():
            term_freq = token_counts.get(token, 0)
            if not term_freq:
                continue
            idf = math.log(1 + (doc_count - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
            denominator = term_freq + k1 * (1 - b + b * length / avg_len)
            score += query_weight * idf * (term_freq * (k1 + 1)) / denominator
        score *= _section_score_weight(chunk.section_label)
        if score > 0:
            hits.append(RouteBSearchHit(chunk=chunk, score=score))

    hits.sort(key=lambda hit: (-hit.score, hit.chunk.doc_id, hit.chunk.block_id, hit.chunk.chunk_index))
    return hits[:top_k]


def _dedupe_hits_by_block(hits: Sequence[RouteBSearchHit], *, top_k: int) -> list[RouteBSearchHit]:
    deduped: list[RouteBSearchHit] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        key = (hit.chunk.doc_id, hit.chunk.block_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
        if len(deduped) >= top_k:
            break
    return deduped


def tokenize_for_route_b(value: Any) -> list[str]:
    text = str(value or "").lower()
    tokens: list[str] = []

    for match in _ASCII_TOKEN_RE.finditer(text):
        raw = match.group(0).strip("._/-")
        if len(raw) >= 2:
            tokens.append(raw)
        for part in re.split(r"[._/-]+", raw):
            if len(part) >= 2:
                tokens.append(part)

    for match in _CJK_RE.finditer(text):
        tokens.extend(_cjk_ngrams(match.group(0), 2))
        tokens.extend(_cjk_ngrams(match.group(0), 3))

    return tokens


def truncate_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _section_score_weight(section_label: str | None) -> float:
    if not section_label:
        return 1.0
    return VLM_SECTION_SCORE_WEIGHTS.get(section_label, 1.0)


def _context_text_for_block(block_type: str, parts: list[tuple[str | None, str]]) -> str | None:
    if block_type != "vlm_text" or len(parts) <= 1:
        return None
    sections: dict[str | None, list[str]] = {}
    for section_label, section_text in parts:
        text = str(section_text or "").strip()
        if not text:
            continue
        sections.setdefault(section_label, []).append(text)

    ordered_parts: list[str] = []
    for section_label in VLM_SECTION_LABELS:
        values = sections.get(section_label)
        if not values:
            continue
        label = VLM_CONTEXT_LABELS.get(section_label, section_label)
        ordered_parts.append(f"{label}：{' '.join(values)}")
    if not ordered_parts:
        return None
    return truncate_text(" | ".join(ordered_parts), DEFAULT_CONTEXT_CHARS)


def _iter_safe_blocks(document: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    blocks = document.get("blocks", [])
    if not isinstance(blocks, list):
        return ()
    return (
        block
        for block in blocks
        if isinstance(block, Mapping)
        and block.get("block_type") in ROUTE_B_BLOCK_TYPES
        and bool(block.get("serving_eligible", True))
        and bool(block.get("retrieval_eligible", True))
    )


def _block_text(block: Mapping[str, Any]) -> str:
    value = block.get("text")
    if value not in (None, ""):
        return str(value)
    table = block.get("table")
    if isinstance(table, Mapping):
        rows = table.get("rows")
        if isinstance(rows, list):
            return "\n".join(
                " | ".join(str(cell) for cell in row)
                for row in rows
                if isinstance(row, list)
            )
    return ""


def _split_block_text(
    block_type: str,
    text: str,
    *,
    max_chunk_chars: int,
) -> list[tuple[str | None, str]]:
    if block_type != "vlm_text":
        return [(None, text)]

    sections = _split_vlm_sections(text)
    if not sections:
        sections = [(None, text)]

    chunks: list[tuple[str | None, str]] = []
    for section_label, section_text in sections:
        for part in _split_fixed_length(section_text, max_chunk_chars=max_chunk_chars):
            chunks.append((section_label, part))
    return chunks


def _split_vlm_sections(text: str) -> list[tuple[str | None, str]]:
    pattern = re.compile(
        r"(?P<label>" + "|".join(re.escape(label) for label in VLM_SECTION_LABELS) + r")\s*:",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    sections: list[tuple[str | None, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            sections.append((_canonical_section_label(match.group("label")), section_text))
    return sections


def _split_fixed_length(text: str, *, max_chunk_chars: int) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    if max_chunk_chars <= 0 or len(normalized) <= max_chunk_chars:
        return [normalized]

    chunks: list[str] = []
    step = max(1, max_chunk_chars - min(DEFAULT_CHUNK_OVERLAP, max_chunk_chars // 4))
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + max_chunk_chars)
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start += step
    return [chunk for chunk in chunks if chunk]


def _canonical_section_label(label: str) -> str:
    normalized = " ".join(label.split()).lower()
    for candidate in VLM_SECTION_LABELS:
        if candidate.lower() == normalized:
            return candidate
    return label


def _cjk_ngrams(value: str, size: int) -> list[str]:
    if len(value) < size:
        return [value] if len(value) >= 2 else []
    return [value[index : index + size] for index in range(0, len(value) - size + 1)]


def _load_json(path: Path, warnings: list[str] | None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        if warnings is not None:
            warnings.append(f"Skipped unreadable serving document `{path.name}`: {exc}")
        return None
