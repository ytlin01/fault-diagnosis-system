"""Build gold v2: the reviewed gold set with accepted canonical labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_reviewed_gold import build_gold_v2


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the attestation-reviewed C1STN gold set with the "
            "accepted canonical mapping proposal applied. Unmapped cases "
            "keep their recorded reasons; no cause/action pairs are asserted."
        )
    )
    parser.add_argument("--gold-v1", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    gold_v1 = json.loads(args.gold_v1.read_text(encoding="utf-8-sig"))
    proposal = json.loads(args.proposal.read_text(encoding="utf-8-sig"))
    gold_v2 = build_gold_v2(
        gold_v1,
        proposal,
        gold_v1_path=str(args.gold_v1).replace("\\", "/"),
        gold_v1_sha256=_sha256_file(args.gold_v1),
        proposal_path=str(args.proposal).replace("\\", "/"),
        proposal_sha256=_sha256_file(args.proposal),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(gold_v2, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mapped = sum(1 for case in gold_v2["cases"] if case["review"]["mapping_state"] == "mapped")
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"cases={len(gold_v2['cases'])} mapped={mapped} "
        f"unmapped={len(gold_v2['cases']) - mapped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
