"""Build a local Route C embedding index through the Ollama /api/embed API."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_ARTIFACT = Path("data/processed/aggregates/rag_fp_case_candidates_v1.json")
DEFAULT_OUTPUT_DIR = Path(
    "data/processed/indexes/route_c_qwen3_embedding_4b"
)
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3-embedding:4b"


def build_index(
    artifact_path: Path,
    output_dir: Path,
    ollama_url: str,
    model: str,
    batch_size: int,
    dimensions: int | None,
) -> dict[str, Any]:
    artifact_bytes = artifact_path.read_bytes()
    artifact = json.loads(artifact_bytes.decode("utf-8"))
    records = artifact.get("candidates")
    if not isinstance(records, list) or not records:
        raise ValueError("Route C artifact must contain a non-empty candidates list.")

    texts: list[str] = []
    valid_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        text = str(record.get("field_fp_normalized") or "").strip()
        candidate_id = str(record.get("rag_candidate_id") or "").strip()
        if not text or not candidate_id:
            continue
        texts.append(text)
        valid_records.append(record)
    if not valid_records:
        raise ValueError("Route C artifact has no vectorizable candidates.")

    vectors: list[list[float]] = []
    for start in range(0, len(texts), max(1, batch_size)):
        batch = texts[start : start + max(1, batch_size)]
        request_payload: dict[str, Any] = {"model": model, "input": batch}
        if dimensions is not None:
            request_payload["dimensions"] = dimensions
        response = _post_json(f"{ollama_url.rstrip('/')}/api/embed", request_payload)
        batch_vectors = response.get("embeddings")
        if not isinstance(batch_vectors, list) or len(batch_vectors) != len(batch):
            raise ValueError(
                f"Ollama returned {len(batch_vectors) if isinstance(batch_vectors, list) else 0} "
                f"embeddings for a batch of {len(batch)}."
            )
        vectors.extend(batch_vectors)
        print(f"embedded {min(start + len(batch), len(texts))}/{len(texts)}")

    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(valid_records):
        raise ValueError(f"Unexpected embedding matrix shape: {matrix.shape}")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / np.maximum(norms, 1e-12)

    output_dir.mkdir(parents=True, exist_ok=True)
    vector_path = output_dir / "vectors.npy"
    metadata_path = output_dir / "metadata.jsonl"
    manifest_path = output_dir / "index_manifest.json"
    np.save(vector_path, matrix)
    with metadata_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in valid_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "manifest_version": "route_c_embedding_index_manifest_v1",
        "source_artifact": artifact_path.as_posix(),
        "source_artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "embedding_provider": "ollama",
        "embedding_model": model,
        "embedding_dimensions": int(matrix.shape[1]),
        "metric": "cosine",
        "normalized": True,
        "record_count": int(matrix.shape[0]),
        "vector_file": vector_path.name,
        "metadata_file": metadata_path.name,
        "query_text_field": "field_fp_normalized",
        "result_payload_fields": ["RC", "PA", "evidence.dt_mins"],
        "route_target": "rag_case_pool",
        "publication_status": "candidate_only",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("Ollama embedding response must be a JSON object.")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--dimensions", type=int, default=None)
    args = parser.parse_args()
    manifest = build_index(
        args.artifact,
        args.output_dir,
        args.ollama_url,
        args.model,
        args.batch_size,
        args.dimensions,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
