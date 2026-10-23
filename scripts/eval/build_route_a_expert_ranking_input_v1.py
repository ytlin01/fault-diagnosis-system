"""Assemble the old-KG expert-ranking input from gold v3 and live retrieval."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.canonicalization.prekg import canonicalize_query
from services.evaluation.route_a_candidate_ranking import build_expert_ranking_input
from services.graph.text2cypher.templates import INTENT_DIAGNOSTIC_CHAIN
from services.retrieval.route_a_executor import execute_text2cypher


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen old-KG retrieval path per gold v3 case "
            "(canonicalize -> execute_text2cypher(diagnostic_chain)), apply "
            "the frozen ranking rule through the approved mapping, and "
            "assemble the expert-ranking input. Read-only against Neo4j."
        )
    )
    parser.add_argument("--gold-v3", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--chain-export", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    gold_v3 = json.loads(args.gold_v3.read_text(encoding="utf-8-sig"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8-sig"))
    export = json.loads(args.chain_export.read_text(encoding="utf-8-sig"))
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    if not mapping.get("approved"):
        raise SystemExit("mapping is not approved; refusing to assemble scored input")
    if mapping.get("snapshot_id") != export["snapshot_id"]:
        raise SystemExit("mapping and chain export snapshot digests disagree")

    retrieval_outputs: dict[str, dict] = {}
    for case in gold_v3["cases"]:
        canonical = canonicalize_query(case["query"]).as_dict()
        retrieval = execute_text2cypher(canonical, intent=INTENT_DIAGNOSTIC_CHAIN)
        retrieval_outputs[case["case_id"]] = retrieval
        if retrieval["warnings"]:
            print(f"note: {case['case_id']} retrieval warnings: {retrieval['warnings']}")

    payload = build_expert_ranking_input(
        gold_v3,
        mapping,
        retrieval_outputs,
        candidate_id=config["candidate_id"],
        graph_version=config["graph_version"],
        snapshot_id=export["snapshot_id"],
        data_maturity=config["data_maturity"],
        config_path=str(args.config).replace("\\", "/"),
        config_digest="sha256:" + _sha256_file(args.config),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    abstained = sum(1 for case in payload["cases"] if case["abstained"])
    with_results = sum(1 for case in payload["cases"] if case["ranked_results"])
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"cases={len(payload['cases'])} with_ranked_results={with_results} "
        f"abstained={abstained} snapshot_id={payload['candidate']['snapshot_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
