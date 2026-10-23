"""Opt-in Qwen embedding retrieval over a governed Route C index."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from services.retrieval.route_c_case_index import (
    CASE_RETRIEVAL_SOURCE_ID,
    DEFAULT_CASE_MIN_SCORE,
    RouteCCaseSearchHit,
    build_route_c_case_records,
)


DEFAULT_INDEX_DIR = Path("data/processed/indexes/route_c_qwen3_embedding_4b")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3-embedding:4b"
DEFAULT_VECTOR_MIN_SCORE = 0.35


def search_route_c_qwen_cases(
    query_text: str,
    *,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    top_k: int,
    min_score: float = DEFAULT_VECTOR_MIN_SCORE,
    source_id: str = CASE_RETRIEVAL_SOURCE_ID,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    warnings: list[str] | None = None,
) -> list[RouteCCaseSearchHit]:
    """Search the offline Qwen index and return existing Route C hit objects."""
    if top_k <= 0:
        return []
    if source_id != CASE_RETRIEVAL_SOURCE_ID:
        raise ValueError(f"Qwen Route C index blocked source `{source_id}`.")

    directory = Path(index_dir)
    manifest = _load_json(directory / "index_manifest.json")
    if str(manifest.get("embedding_model")) != model:
        raise ValueError(
            f"Embedding model mismatch: index={manifest.get('embedding_model')!r}, requested={model!r}."
        )
    if manifest.get("route_target") != "rag_case_pool":
        raise ValueError("Qwen Route C index has an invalid route target.")

    vectors = np.load(directory / str(manifest.get("vector_file", "vectors.npy")))
    metadata_path = directory / str(manifest.get("metadata_file", "metadata.jsonl"))
    metadata = [
        json.loads(line)
        for line in metadata_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if vectors.ndim != 2 or vectors.shape[0] != len(metadata):
        raise ValueError("Qwen Route C vector and metadata counts do not match.")
    expected_dimensions = int(manifest.get("embedding_dimensions", vectors.shape[1]))
    if vectors.shape[1] != expected_dimensions:
        raise ValueError("Qwen Route C vector dimensions do not match the manifest.")

    index_records = build_route_c_case_records(metadata, source_id=source_id, warnings=warnings)
    by_id = {record.case_id: record for record in index_records}
    query_vector = _embed_query(
        query_text,
        ollama_url=ollama_url,
        model=model,
        dimensions=expected_dimensions,
    )
    if query_vector.shape[0] != vectors.shape[1]:
        raise ValueError(
            f"Query dimension {query_vector.shape[0]} does not match index dimension {vectors.shape[1]}."
        )
    query_vector = query_vector / max(float(np.linalg.norm(query_vector)), 1e-12)
    scores = vectors @ query_vector

    hits: list[RouteCCaseSearchHit] = []
    for row_index, score in enumerate(scores):
        record_id = str(metadata[row_index].get("rag_candidate_id") or "")
        record = by_id.get(record_id)
        if record is not None and float(score) >= min_score:
            hits.append(RouteCCaseSearchHit(record=record, score=float(score)))
    hits.sort(key=lambda hit: (-hit.score, hit.record.case_id))
    return hits[:top_k]


def _embed_query(
    query_text: str,
    *,
    ollama_url: str,
    model: str,
    dimensions: int,
) -> np.ndarray:
    payload = {
        "model": model,
        "input": [str(query_text or "")],
        "dimensions": dimensions,
    }
    request = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/embed",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    embeddings = body.get("embeddings") if isinstance(body, dict) else None
    if not isinstance(embeddings, list) or len(embeddings) != 1:
        raise ValueError("Ollama returned an invalid query embedding response.")
    return np.asarray(embeddings[0], dtype=np.float32)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return payload
