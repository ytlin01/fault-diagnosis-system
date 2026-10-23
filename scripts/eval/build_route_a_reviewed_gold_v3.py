"""Build gold v3: the reviewed gold set with asserted pairing and abstention."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_reviewed_gold import build_gold_v3


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the C1STN gold set with the accepted pairing and "
            "abstention proposal applied. Each case carries its accepted "
            "cause/action pairs and abstention encoding with the acceptance "
            "reference; the queue pairing_state becomes asserted."
        )
    )
    parser.add_argument("--gold-v2", type=Path, required=True)
    parser.add_argument("--pairing-proposal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    gold_v2 = json.loads(args.gold_v2.read_text(encoding="utf-8-sig"))
    proposal = json.loads(args.pairing_proposal.read_text(encoding="utf-8-sig"))
    gold_v3 = build_gold_v3(
        gold_v2,
        proposal,
        gold_v2_path=str(args.gold_v2).replace("\\", "/"),
        gold_v2_sha256=_sha256_file(args.gold_v2),
        proposal_path=str(args.pairing_proposal).replace("\\", "/"),
        proposal_sha256=_sha256_file(args.pairing_proposal),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(gold_v3, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pair_states = [
        case["review"]["pairing"]["pairing_state"] for case in gold_v3["cases"]
    ]
    with_pairs = pair_states.count("pairs_asserted")
    abstention_required = sum(
        1
        for case in gold_v3["cases"]
        if case["review"]["abstention"]["expected"] == "required"
    )
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"cases={len(gold_v3['cases'])} cases_with_pairs={with_pairs} "
        f"abstention_required={abstention_required}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
