from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.cad_2d_pipeline_v2 import (  # noqa: E402
    audit_asm_bom,
    compare_legacy_triples,
    load_cleaned_handoff,
    load_config,
)
from services.ingestion.cad_2d_pipeline_v2.artifacts import (  # noqa: E402
    write_json_exclusive,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a cleaned CAD 2D handoff and emit identifier-safe evidence"
    )
    parser.add_argument("--source-root", required=True)
    parser.add_argument(
        "--config", default="configs/pipelines/cad_2d_pipeline_v2.yaml"
    )
    parser.add_argument(
        "--legacy-triples",
        help="Optional historical triples JSON for aggregate comparison only",
    )
    parser.add_argument(
        "--evidence-out",
        help="Exclusive-create path for sanitized evidence; omitted for preview",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    snapshot = load_cleaned_handoff(args.source_root)
    b02 = audit_asm_bom(
        snapshot.drawing_index,
        snapshot.bom_parents,
        config,
        source_findings=snapshot.source_findings,
    )
    evidence = dict(snapshot.evidence)
    evidence["current_v2_b02"] = b02.audit
    evidence["c01_gate"] = {
        "state": "blocked" if b02.audit["blocking_finding_count"] else "eligible_for_candidate_build",
        "unresolved_blocking_finding_count": b02.audit["blocking_finding_count"],
        "requires_governed_override_or_corrected_source": bool(
            b02.audit["blocking_finding_count"]
        ),
    }
    if args.legacy_triples:
        triples = json.loads(Path(args.legacy_triples).read_text(encoding="utf-8"))
        evidence["legacy_triples_comparison"] = compare_legacy_triples(
            triples, snapshot.drawing_index
        )

    mode = "write_evidence" if args.evidence_out else "preview"
    print(
        json.dumps(
            {
                "mode": mode,
                "snapshot_id": evidence["snapshot_id"],
                "counts": evidence["counts"],
                "current_v2_b02": evidence["current_v2_b02"],
                "c01_gate": evidence["c01_gate"],
                "legacy_triples_comparison": evidence.get("legacy_triples_comparison"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    if args.evidence_out:
        write_json_exclusive(args.evidence_out, evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
