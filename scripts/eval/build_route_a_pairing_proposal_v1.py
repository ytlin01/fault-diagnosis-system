"""Build the pairing and abstention proposal v1 from gold v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_pairing_proposal import (
    build_pairing_abstention_proposal,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the deterministic pairing and abstention proposal for "
            "the C1STN gold v2. Pairs the accepted canonical labels per case "
            "with per-pair evidence basis; proposes abstention encodings for "
            "the unmapped cases. Proposal only, nothing reviewed."
        )
    )
    parser.add_argument("--gold-v2", type=Path, required=True)
    parser.add_argument("--mapping-proposal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    gold_v2 = json.loads(args.gold_v2.read_text(encoding="utf-8-sig"))
    mapping_proposal = json.loads(
        args.mapping_proposal.read_text(encoding="utf-8-sig")
    )
    proposal = build_pairing_abstention_proposal(
        gold_v2,
        mapping_proposal,
        gold_v2_path=str(args.gold_v2).replace("\\", "/"),
        gold_v2_sha256=_sha256_file(args.gold_v2),
        mapping_proposal_path=str(args.mapping_proposal).replace("\\", "/"),
        mapping_proposal_sha256=_sha256_file(args.mapping_proposal),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = proposal["summary"]
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"cases={summary['case_count']} "
        f"pairs={summary['proposed_pair_count']} "
        f"(shared={summary['shared_evidence_pair_count']} "
        f"cross={summary['cross_product_only_pair_count']}) "
        f"abstention_required={len(summary['abstention_required_case_ids'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
