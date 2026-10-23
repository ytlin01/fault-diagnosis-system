"""Build the old-TP-DX canonical mapping (proposal or approved) from the frozen export."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.evaluation.old_tpdx_expert_ranking_mapping import build_mapping


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the old-TP-DX canonical mapping from the frozen chain-row "
            "export and gold v3. Exact normalized text matches only; "
            "unmatched graph texts are counted, never guessed. Pass "
            "--approved only after the data owner has accepted the proposal."
        )
    )
    parser.add_argument("--chain-export", type=Path, required=True)
    parser.add_argument("--gold-v3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--approved",
        action="store_true",
        help="mark the mapping approved (data-owner acceptance recorded in the annotation log)",
    )
    args = parser.parse_args(argv)

    export = json.loads(args.chain_export.read_text(encoding="utf-8-sig"))
    gold_v3 = json.loads(args.gold_v3.read_text(encoding="utf-8-sig"))
    mapping = build_mapping(
        export["chain_rows"],
        gold_v3,
        gold_v3_path=str(args.gold_v3).replace("\\", "/"),
        gold_v3_sha256=_sha256_file(args.gold_v3),
        graph_version=export["graph_version"],
        approved=args.approved,
    )
    if mapping["snapshot_id"] != export["snapshot_id"]:
        raise SystemExit("chain export snapshot digest mismatch; refusing to map")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts = mapping["unmatched_graph_counts"]
    print(
        f"wrote {args.output} sha256={_sha256_file(args.output)} "
        f"approved={mapping['approved']} "
        f"cause_matches={len(mapping['cause_matches'])} "
        f"action_matches={len(mapping['action_matches'])} "
        f"unmatched_causes={counts['unmatched_causes']}/{counts['distinct_causes']} "
        f"unmatched_actions={counts['unmatched_actions']}/{counts['distinct_actions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
