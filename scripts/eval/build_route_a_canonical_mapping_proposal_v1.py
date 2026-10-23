"""Build the V2-TASK001 canonical-mapping proposal from the reviewed gold set."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.route_a_canonical_mapping import build_mapping_proposal


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically propose canonical cause/action mappings for "
            "the attestation-reviewed C1STN gold set. Output is a proposal "
            "for domain review, never reviewed truth."
        )
    )
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    gold = json.loads(args.gold.read_text(encoding="utf-8-sig"))
    proposal = build_mapping_proposal(
        gold,
        gold_path=str(args.gold).replace("\\", "/"),
        gold_sha256=_sha256_file(args.gold),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mapped_causes = sum(1 for case in proposal["cases"] if case["proposed_causes"])
    mapped_actions = sum(1 for case in proposal["cases"] if case["proposed_actions"])
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"cases={len(proposal['cases'])} "
        f"cases_with_causes={mapped_causes} cases_with_actions={mapped_actions}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
