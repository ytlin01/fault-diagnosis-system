#!/usr/bin/env python3
"""Build a deterministic Schema 4.2 candidate from an explicit input bundle.

The builder is preview/fail-closed by default.  ``--allow-exclusions`` is an
explicit acknowledgement that the output is a review candidate with governed
exclusions, never a complete graph candidate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from services.governance.tpdx_schema_v4_2 import SchemaV42SemanticError, validate_v4_2_semantics
from services.ingestion.tpdx_schema_v4_2_migration import (
    MIGRATION_VERSION,
    MigrationError,
    canonical_json_bytes,
    migrate_v4_1_payload,
)


class CandidateBuildError(ValueError):
    """Raised when a candidate cannot be written safely."""


def _sha256_bytes(value: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBuildError(f"unable to read JSON input {path}: {exc}") from exc


def _write_json_stable(path: Path, value: Any) -> str:
    """Write stable pretty JSON, refusing a conflicting existing artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        existing = path.read_bytes()
        if _sha256_bytes(existing) != _sha256_bytes(rendered.encode("utf-8")):
            raise CandidateBuildError(f"refusing to overwrite conflicting artifact {path}")
    else:
        path.write_text(rendered, encoding="utf-8", newline="\n")
    return _sha256_bytes(canonical_json_bytes(value))


def _validate_candidate(candidate: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if schema.get("$id") != "tpdx_kg_schema_v4_2":
        raise CandidateBuildError("--schema must identify tpdx_kg_schema_v4_2")
    if schema.get("x-contract-status") != "FROZEN":
        raise CandidateBuildError("--schema must be the FROZEN Schema 4.2 contract")
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise CandidateBuildError("jsonschema is required for candidate validation") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(candidate), key=str)
    if errors:
        raise CandidateBuildError("candidate failed JSON Schema validation: " + str(errors[0]))
    try:
        validate_v4_2_semantics(candidate)
    except SchemaV42SemanticError as exc:
        raise CandidateBuildError(f"candidate failed semantic validation: {exc}") from exc


def _validate_source(payload: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if schema.get("$id") != "tpdx_kg_schema_v4_1":
        raise CandidateBuildError("--rollback-schema must identify tpdx_kg_schema_v4_1")
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise CandidateBuildError("jsonschema is required for source validation") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=str)
    if errors:
        raise CandidateBuildError("Schema 4.1 input failed validation: " + str(errors[0]))


def _code_fingerprint() -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        Path(__file__).resolve().parents[2]
        / "services/ingestion/tpdx_schema_v4_2_migration.py",
        Path(__file__).resolve().parents[2]
        / "services/graph/tpdx_schema_v4_2_import.py",
    )
    material = b"".join(
        str(path.relative_to(Path(__file__).resolve().parents[2])).replace("\\", "/").encode()
        + b"\0"
        + path.read_bytes()
        + b"\0"
        for path in paths
    )
    return {
        "version": MIGRATION_VERSION,
        "sha256": _sha256_bytes(material),
    }


def build_candidate(
    *,
    input_path: Path,
    candidate_path: Path,
    exclusions_path: Path,
    lineage_path: Path,
    manifest_path: Path,
    schema_path: Path,
    rollback_schema_path: Path,
    pairings_path: Path | None = None,
    config_path: Path | None = None,
    allow_exclusions: bool = False,
) -> dict[str, Any]:
    """Build candidate/evidence artifacts and return the deterministic manifest."""

    payload = _load_json(input_path)
    pairings: list[Mapping[str, Any]] = []
    if pairings_path is not None:
        loaded_pairings = _load_json(pairings_path)
        if not isinstance(loaded_pairings, list):
            raise CandidateBuildError("pairings JSON must be an array")
        pairings = loaded_pairings
    config: Any = {}
    if config_path is not None:
        config = _load_json(config_path)

    schema = _load_json(schema_path)
    rollback_schema = _load_json(rollback_schema_path)
    _validate_source(payload, rollback_schema)
    try:
        result = migrate_v4_1_payload(payload, pairings=pairings)
    except MigrationError as exc:
        raise CandidateBuildError(str(exc)) from exc
    _validate_candidate(result.candidate, schema)

    candidate_digest = _sha256_bytes(canonical_json_bytes(result.candidate))
    exclusions_digest = _sha256_bytes(canonical_json_bytes(list(result.exclusions)))
    lineage_digest = _sha256_bytes(canonical_json_bytes(list(result.lineage)))
    validation = {
        "json_schema": "passed",
        "semantic": "passed",
        "migration_version": MIGRATION_VERSION,
        "exclusion_count": len(result.exclusions),
    }
    blocked = bool(result.exclusions) and not allow_exclusions
    status = (
        "blocked_by_exclusions"
        if blocked
        else "candidate_with_exclusions"
        if result.exclusions
        else "complete_candidate"
    )

    outputs: dict[str, Any] = {
        "candidate": {
            "path": str(candidate_path),
            "sha256": candidate_digest,
            "written": not blocked,
        },
        "exclusions": {
            "path": str(exclusions_path),
            "sha256": exclusions_digest,
        },
        "lineage": {
            "path": str(lineage_path),
            "sha256": lineage_digest,
        },
    }
    manifest: dict[str, Any] = {
        "manifest_version": "tpdx_schema_v4_2_candidate_run_v1",
        "run_status": status,
        "source_schema_version": "4.1",
        "target_schema_version": "4.2",
        "input": {
            "path": str(input_path),
            "sha256": _sha256_bytes(canonical_json_bytes(payload)),
        },
        "pairings": {
            "path": str(pairings_path) if pairings_path else None,
            "sha256": _sha256_bytes(canonical_json_bytes(pairings)),
        },
        "config": {
            "path": str(config_path) if config_path else None,
            "sha256": _sha256_bytes(canonical_json_bytes(config)),
        },
        "code": _code_fingerprint(),
        "schema_v4_2": {
            "path": str(schema_path),
            "sha256": _sha256_file(schema_path),
            "contract_status": schema.get("x-contract-status"),
        },
        "schema_v4_1_rollback_baseline": {
            "path": str(rollback_schema_path),
            "sha256": _sha256_file(rollback_schema_path),
            "contract_status": rollback_schema.get("x-contract-status"),
        },
        "outputs": outputs,
        "validation": validation,
        "counts": {
            "nodes": len(result.candidate["nodes"]),
            "edges": len(result.candidate["edges"]),
            "exclusions": len(result.exclusions),
            "lineage_records": len(result.lineage),
        },
        "rollback": {
            "schema_version": "4.1",
            "parallel_has_step_publication": False,
            "switch_back_required_before_activation": True,
        },
    }

    _write_json_stable(exclusions_path, list(result.exclusions))
    _write_json_stable(lineage_path, list(result.lineage))
    if not blocked:
        _write_json_stable(candidate_path, result.candidate)
    _write_json_stable(manifest_path, manifest)
    if blocked:
        raise CandidateBuildError(
            f"candidate blocked by {len(result.exclusions)} governed exclusions; "
            "rerun with --allow-exclusions only to produce a non-complete review candidate"
        )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--candidate-out", type=Path, required=True)
    parser.add_argument("--exclusions-out", type=Path, required=True)
    parser.add_argument("--lineage-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--rollback-schema", type=Path, required=True)
    parser.add_argument("--pairings", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--allow-exclusions",
        action="store_true",
        help="write a review candidate even when governed exclusions exist",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = build_candidate(
            input_path=args.input,
            candidate_path=args.candidate_out,
            exclusions_path=args.exclusions_out,
            lineage_path=args.lineage_out,
            manifest_path=args.manifest_out,
            schema_path=args.schema,
            rollback_schema_path=args.rollback_schema,
            pairings_path=args.pairings,
            config_path=args.config,
            allow_exclusions=args.allow_exclusions,
        )
    except CandidateBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
