"""Evaluate reviewed Route C queries against BM25, Qwen vector, and hybrid."""

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

DEFAULT_BANK = Path("data/eval/route_c/route_c_human_query_bank_reviewed_v1.json")
DEFAULT_ARTIFACT = Path("data/processed/aggregates/rag_fp_case_candidates_v1.json")
DEFAULT_INDEX = Path("data/processed/indexes/route_c_qwen3_embedding_4b")
DEFAULT_OUTPUT = DEFAULT_INDEX / "reviewed_query_bank_eval.json"


def evaluate(bank_path: Path, artifact_path: Path, index_dir: Path, output_path: Path, ollama_url: str, batch_size: int, vector_min_score: float, hybrid_min_score: float, lexical_weight: float, vector_weight: float) -> dict[str, Any]:
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    records = artifact["candidates"]
    manifest = json.loads((index_dir / "index_manifest.json").read_text(encoding="utf-8"))
    vectors = _normalize(np.load(index_dir / manifest["vector_file"]))
    metadata = [json.loads(line) for line in (index_dir / manifest["metadata_file"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [str(record["rag_candidate_id"]) for record in metadata]
    queries = bank["cases"]
    query_vectors = _normalize(_embed([str(case["query"]) for case in queries], str(manifest["embedding_model"]), int(manifest["embedding_dimensions"]), ollama_url, batch_size))

    result_sets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    details = []
    for case, query_vector in zip(queries, query_vectors):
        expected = set(case.get("expected_rag_candidate_ids") or [])
        lexical_hits = search_route_c_cases(str(case["query"]), records, top_k=len(records), min_score=0.1)
        lexical_scores = {hit.record.case_id: float(hit.score) for hit in lexical_hits}
        lexical_ranked = [hit.record.case_id for hit in lexical_hits]
        vector_scores = vectors @ query_vector
        vector_by_id = {case_id: float(score) for case_id, score in zip(ids, vector_scores)}
        vector_ranked = [case_id for case_id in sorted(ids, key=lambda item: (-vector_by_id[item], item)) if vector_by_id[case_id] >= vector_min_score]
        max_lexical = max(lexical_scores.values(), default=0.0)
        hybrid_scores = {case_id: lexical_weight * (lexical_scores.get(case_id, 0.0) / max_lexical if max_lexical else 0.0) + vector_weight * vector_by_id[case_id] for case_id in ids}
        hybrid_ranked = [case_id for case_id in sorted(ids, key=lambda item: (-hybrid_scores[item], item)) if hybrid_scores[case_id] >= hybrid_min_score]
        rankings = {"lexical_bm25": lexical_ranked, "qwen_vector": vector_ranked, "hybrid_bm25_qwen": hybrid_ranked}
        row = {"query_id": case["query_id"], "query_type": case["query_type"], "expected": sorted(expected), "rankings": {}}
        for name, ranking in rankings.items():
            top = ranking[:3]
            first = next((rank for rank, candidate_id in enumerate(ranking, start=1) if candidate_id in expected), None) if expected else None
            no_hit_correct = (not ranking) if not expected else None
            metrics = {"top1": bool(expected and ranking and ranking[0] in expected), "top3": bool(expected and any(candidate_id in expected for candidate_id in top)), "first_rank": first, "no_hit_correct": no_hit_correct, "returned": len(ranking)}
            row["rankings"][name] = {"top3": top, "metrics": metrics}
            result_sets[name].append(metrics)
        details.append(row)

    metrics = {name: _summarize(rows, queries) for name, rows in result_sets.items()}
    report = {"evaluation_type": "reviewed_query_bank", "status": bank.get("status"), "query_count": len(queries), "positive_count": sum(bool(case.get("expected_rag_candidate_ids")) for case in queries), "no_hit_count": sum(not case.get("expected_rag_candidate_ids") for case in queries), "thresholds": {"vector_min_score": vector_min_score, "hybrid_min_score": hybrid_min_score, "lexical_min_score": 0.1}, "embedding_model": manifest["embedding_model"], "embedding_dimensions": manifest["embedding_dimensions"], "metrics": metrics, "details": details}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _summarize(rows: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    positive_rows = [row for row, case in zip(rows, cases) if case.get("expected_rag_candidate_ids")]
    no_hit_rows = [row for row, case in zip(rows, cases) if not case.get("expected_rag_candidate_ids")]
    top1 = sum(row["top1"] for row in positive_rows)
    top3 = sum(row["top3"] for row in positive_rows)
    reciprocal = sum(1.0 / row["first_rank"] for row in positive_rows if row["first_rank"])
    no_hit_correct = sum(row["no_hit_correct"] is True for row in no_hit_rows)
    return {"positive_queries": len(positive_rows), "top1_hits": top1, "top1_rate": round(top1 / len(positive_rows), 6) if positive_rows else 0.0, "top3_hits": top3, "top3_rate": round(top3 / len(positive_rows), 6) if positive_rows else 0.0, "mrr": round(reciprocal / len(positive_rows), 6) if positive_rows else 0.0, "no_hit_queries": len(no_hit_rows), "no_hit_correct": no_hit_correct, "no_hit_rate": round(no_hit_correct / len(no_hit_rows), 6) if no_hit_rows else 0.0}


def _embed(texts: list[str], model: str, dimensions: int, ollama_url: str, batch_size: int) -> np.ndarray:
    values: list[list[float]] = []
    for start in range(0, len(texts), max(1, batch_size)):
        batch = texts[start : start + max(1, batch_size)]
        payload = {"model": model, "input": batch, "dimensions": dimensions}
        request = urllib.request.Request(f"{ollama_url.rstrip('/')}/api/embed", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=600) as response:
            values.extend(json.loads(response.read().decode("utf-8"))["embeddings"])
        print(f"embedded reviewed queries {min(start + len(batch), len(texts))}/{len(texts)}")
    return np.asarray(values, dtype=np.float32)


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--vector-min-score", type=float, default=0.35)
    parser.add_argument("--hybrid-min-score", type=float, default=0.35)
    parser.add_argument("--lexical-weight", type=float, default=0.7)
    parser.add_argument("--vector-weight", type=float, default=0.3)
    args = parser.parse_args()
    report = evaluate(args.bank, args.artifact, args.index_dir, args.output, args.ollama_url, args.batch_size, args.vector_min_score, args.hybrid_min_score, args.lexical_weight, args.vector_weight)
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
