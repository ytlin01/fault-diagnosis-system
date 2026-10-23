"""Compare Route C BM25, Qwen vector, and hybrid self-retrieval quality."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.retrieval.route_c_case_index import search_route_c_cases


DEFAULT_ARTIFACT = Path("data/processed/aggregates/rag_fp_case_candidates_v1.json")
DEFAULT_INDEX_DIR = Path("data/processed/indexes/route_c_qwen3_embedding_4b")
DEFAULT_OUTPUT = DEFAULT_INDEX_DIR / "effect_eval.json"


def evaluate(artifact_path: Path, index_dir: Path, output_path: Path, ollama_url: str, batch_size: int, lexical_weight: float, vector_weight: float) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    records = artifact["candidates"]
    manifest = json.loads((index_dir / "index_manifest.json").read_text(encoding="utf-8"))
    vectors = np.load(index_dir / manifest["vector_file"])
    metadata = [json.loads(line) for line in (index_dir / manifest["metadata_file"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    queries = [str(record["field_fp_normalized"]) for record in records]
    expected_by_text: dict[str, set[str]] = defaultdict(set)
    for record in records:
        expected_by_text[str(record["field_fp_normalized"])].add(str(record["rag_candidate_id"]))
    query_vectors = _normalize(_embed_batches(queries, model=str(manifest["embedding_model"]), dimensions=int(manifest["embedding_dimensions"]), ollama_url=ollama_url, batch_size=batch_size))
    vectors = _normalize(vectors)
    id_by_row = [str(record["rag_candidate_id"]) for record in metadata]
    rankings: dict[str, list[list[str]]] = {"lexical_bm25": [], "qwen_vector": [], "hybrid_bm25_qwen": []}
    expected_sets: list[set[str]] = []
    for query, query_vector in zip(queries, query_vectors):
        lexical_hits = search_route_c_cases(query, records, top_k=len(records), min_score=0.0)
        lexical_scores = {hit.record.case_id: float(hit.score) for hit in lexical_hits}
        max_lexical = max(lexical_scores.values(), default=0.0)
        vector_scores = vectors @ query_vector
        vector_by_id = {case_id: float(score) for case_id, score in zip(id_by_row, vector_scores)}
        lexical_ids = [hit.record.case_id for hit in lexical_hits]
        vector_ids = sorted(id_by_row, key=lambda case_id: (-vector_by_id[case_id], case_id))
        hybrid_ids = sorted(id_by_row, key=lambda case_id: (-(lexical_weight * (lexical_scores.get(case_id, 0.0) / max_lexical if max_lexical else 0.0) + vector_weight * vector_by_id[case_id]), case_id))
        rankings["lexical_bm25"].append(lexical_ids)
        rankings["qwen_vector"].append(vector_ids)
        rankings["hybrid_bm25_qwen"].append(hybrid_ids)
        expected_sets.append(expected_by_text[query])
    metrics = {name: _metrics(ranking, expected_sets) for name, ranking in rankings.items()}
    report = {
        "evaluation_type": "self_retrieval_smoke",
        "warning": "Exact source-phenomenon queries are not a substitute for human paraphrase evaluation.",
        "artifact": artifact_path.as_posix(),
        "index": index_dir.as_posix(),
        "embedding_model": manifest["embedding_model"],
        "embedding_dimensions": manifest["embedding_dimensions"],
        "query_count": len(queries),
        "duplicate_aware": True,
        "hybrid_weights": {"lexical": lexical_weight, "vector": vector_weight},
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _metrics(rankings: list[list[str]], expected_sets: list[set[str]]) -> dict[str, float | int]:
    top1 = top3 = 0
    reciprocal_sum = 0.0
    for ranking, expected in zip(rankings, expected_sets):
        if ranking and ranking[0] in expected:
            top1 += 1
        first_rank = next((rank for rank, case_id in enumerate(ranking, start=1) if case_id in expected), None)
        if first_rank is not None:
            if first_rank <= 3:
                top3 += 1
            reciprocal_sum += 1.0 / first_rank
    total = len(expected_sets)
    return {"queries": total, "top1_hits": top1, "top1_rate": round(top1 / total, 6) if total else 0.0, "top3_hits": top3, "top3_rate": round(top3 / total, 6) if total else 0.0, "mrr": round(reciprocal_sum / total, 6) if total else 0.0}


def _embed_batches(texts: list[str], *, model: str, dimensions: int, ollama_url: str, batch_size: int) -> np.ndarray:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), max(1, batch_size)):
        batch = texts[start : start + max(1, batch_size)]
        payload = {"model": model, "input": batch, "dimensions": dimensions}
        request = urllib.request.Request(f"{ollama_url.rstrip('/')}/api/embed", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=600) as response:
            vectors.extend(json.loads(response.read().decode("utf-8"))["embeddings"])
        print(f"embedded queries {min(start + len(batch), len(texts))}/{len(texts)}")
    return np.asarray(vectors, dtype=np.float32)


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lexical-weight", type=float, default=0.7)
    parser.add_argument("--vector-weight", type=float, default=0.3)
    args = parser.parse_args()
    report = evaluate(args.artifact, args.index_dir, args.output, args.ollama_url, args.batch_size, args.lexical_weight, args.vector_weight)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
