"""CLI for TASK-005 v1 semantic FP join candidates.

The default provider is local Ollama. Outputs under data/processed/aggregates
are review artifacts, not confirmed KG/text2cypher diagnosis facts.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.aggregation.structured_fp_join import write_json  # noqa: E402
from services.aggregation.structured_fp_join_semantic import (  # noqa: E402
    OllamaEmbeddingProvider,
    build_review_decisions_template,
    build_review_report,
    build_review_summary,
    build_semantic_fp_join,
    build_standard_fp_review,
    build_standard_fp_review_summary,
    build_summary,
    load_inputs,
    load_review_decisions,
    load_rules,
    load_semantic_config,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TASK-005 v1 semantic FP join candidates.")
    parser.add_argument("--processed-dir", default=str(PROJECT_ROOT / "data" / "processed"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "processed" / "aggregates"))
    parser.add_argument("--rules", default=str(PROJECT_ROOT / "configs" / "fp_join_rules.yaml"))
    parser.add_argument("--semantic-config", default=str(PROJECT_ROOT / "configs" / "fp_join_semantic_v1.yaml"))
    parser.add_argument("--output-file", default="structured_fp_join_v1_semantic.json")
    parser.add_argument("--summary-file", default="structured_fp_join_v1_semantic_summary.json")
    parser.add_argument("--review-file", default="structured_fp_join_v1_semantic_review.json")
    parser.add_argument("--review-summary-file", default="structured_fp_join_v1_semantic_review_summary.json")
    parser.add_argument("--review-decisions-file", default="structured_fp_join_v1_semantic_review_decisions.json")
    parser.add_argument("--standard-fp-review-file", default="structured_fp_join_v1_semantic_standard_fp_review.json")
    parser.add_argument("--standard-fp-review-summary-file", default="structured_fp_join_v1_semantic_standard_fp_review_summary.json")
    parser.add_argument("--embedding-cache-file", default="_cache/structured_fp_join_v1_semantic_embeddings.json")
    parser.add_argument("--ollama-host", default=None)
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--ollama-models-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    processed_dir = Path(args.processed_dir)
    output_dir = Path(args.output_dir)
    config = load_semantic_config(Path(args.semantic_config))
    provider_config = config.setdefault("provider", {})
    if args.ollama_host:
        provider_config["host"] = args.ollama_host
    if args.embedding_model:
        provider_config["model"] = args.embedding_model
    if args.ollama_models_dir:
        os.environ["OLLAMA_MODELS"] = args.ollama_models_dir
        provider_config["models_dir"] = args.ollama_models_dir

    review_decisions_path = Path(args.review_decisions_file)
    if not review_decisions_path.is_absolute():
        review_decisions_path = output_dir / review_decisions_path
    review_decisions = load_review_decisions(review_decisions_path)

    cache_path = Path(args.embedding_cache_file)
    if not cache_path.is_absolute():
        cache_path = output_dir / cache_path

    provider = OllamaEmbeddingProvider(
        host=str(provider_config.get("host") or "http://localhost:11434"),
        model=str(provider_config.get("model") or "nomic-embed-text:latest"),
        batch_size=int(provider_config.get("batch_size") or 64),
        timeout_sec=int(provider_config.get("timeout_sec") or 120),
        cache_path=cache_path,
    )

    error_codes, downtime, _, _ = load_inputs(processed_dir)
    rules = load_rules(Path(args.rules))
    payload = build_semantic_fp_join(
        error_codes,
        downtime,
        rules=rules,
        config=config,
        embedding_provider=provider,
        review_decisions=review_decisions,
    )
    summary = build_summary(payload)
    review_report = build_review_report(payload)
    review_summary = build_review_summary(review_report)
    standard_fp_review = build_standard_fp_review(payload)
    standard_fp_review_summary = build_standard_fp_review_summary(standard_fp_review)

    print("TASK-005 v1 semantic FP join summary")
    for key, value in summary["summary"].items():
        print(f"  {key}: {value}")

    if args.dry_run:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    if not review_decisions_path.exists():
        write_json(review_decisions_path, build_review_decisions_template(), pretty=True)
        print(f"Wrote review decisions template: {review_decisions_path}")
    pretty = not args.compact
    write_json(output_dir / args.output_file, payload, pretty=pretty)
    write_json(output_dir / args.summary_file, summary, pretty=True)
    write_json(output_dir / args.review_file, review_report, pretty=pretty)
    write_json(output_dir / args.review_summary_file, review_summary, pretty=True)
    write_json(output_dir / args.standard_fp_review_file, standard_fp_review, pretty=pretty)
    write_json(output_dir / args.standard_fp_review_summary_file, standard_fp_review_summary, pretty=True)
    print(f"Wrote semantic join output: {output_dir / args.output_file}")
    print(f"Wrote semantic summary: {output_dir / args.summary_file}")
    print(f"Wrote semantic review report: {output_dir / args.review_file}")
    print(f"Wrote semantic review summary: {output_dir / args.review_summary_file}")
    print(f"Wrote standard-FP review: {output_dir / args.standard_fp_review_file}")
    print(f"Wrote standard-FP review summary: {output_dir / args.standard_fp_review_summary_file}")


if __name__ == "__main__":
    main()
