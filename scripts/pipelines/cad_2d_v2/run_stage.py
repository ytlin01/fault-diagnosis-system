from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.cad_2d_pipeline_v2 import (
    audit_asm_bom,
    build_drawing_index,
    build_project_owner_output,
    build_relationships,
    combine_bom_candidate_sources,
    extract_asm_bom,
    extract_fields,
    load_config,
    merge_classifications,
    projection_classification_records,
    reuse_historical_bom_candidates,
    validate_b00_word_bundle,
)
from services.ingestion.cad_2d_pipeline_v2.artifacts import (
    build_manifest,
    write_json_pair_exclusive,
)


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _records(value: object, label: str) -> list[dict]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        return value["records"]
    raise ValueError(f"{label} input must be a JSON list or a stage bundle")


def _field_records(value: object) -> list[dict]:
    if isinstance(value, dict) and "records" not in value:
        if not all(isinstance(fields, dict) for fields in value.values()):
            raise ValueError("A03 field mapping values must be objects")
        return [
            {"part_number": identifier, **value[identifier]}
            for identifier in sorted(value, key=lambda item: item.casefold())
        ]
    return _records(value, "A03 fields")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview-first CAD 2D v2 stage runner")
    parser.add_argument("stage", choices=("A01", "A02", "A03", "B01", "B02", "C01", "C02"))
    parser.add_argument("--config", default="configs/pipelines/cad_2d_pipeline_v2.yaml")
    parser.add_argument("--primary", required=True, help="Primary JSON input")
    parser.add_argument("--secondary", help="Secondary JSON input for A01/A03/B01")
    parser.add_argument("--tertiary", help="Tertiary JSON input for combined B01 words or C01 findings")
    parser.add_argument("--tertiary-manifest", help="Manifest required for combined B01 word bundle")
    parser.add_argument("--overrides", help="Governed manual overrides JSON for C01")
    parser.add_argument(
        "--corrections",
        help="Governed BOM corrections JSON for combined B01",
    )
    parser.add_argument("--out", help="Output bundle path; required with --write")
    parser.add_argument("--manifest-out", help="Manifest path; required with --write")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    primary_raw = _load(args.primary)
    secondary_raw = _load(args.secondary) if args.secondary else None
    tertiary_raw = _load(args.tertiary) if args.tertiary else None
    tertiary_manifest = _load(args.tertiary_manifest) if args.tertiary_manifest else None
    overrides = _load(args.overrides) if args.overrides else []
    corrections = _load(args.corrections) if args.corrections else []
    if args.stage == "A01":
        try:
            reviewed = (
                projection_classification_records(primary_raw)
                if isinstance(primary_raw, dict)
                and primary_raw.get("schema_version")
                == "cad_2d_manual_classification_review_v2"
                else _records(primary_raw, "A01 reviewed")
            )
            full = _records(secondary_raw, "A01 full")
        except ValueError as exc:
            parser.error(str(exc))
        result = merge_classifications(
            reviewed,
            full,
            config,
            allow_reviewed_additions=(
                isinstance(primary_raw, dict)
                and primary_raw.get("schema_version")
                == "cad_2d_manual_classification_review_v2"
            ),
        )
        inputs = {"review_projection_or_records": primary_raw, "full": full}
    elif args.stage == "A02":
        try:
            primary = _records(primary_raw, "A02 primary")
        except ValueError as exc:
            parser.error(str(exc))
        result = extract_fields(primary, config)
        inputs = {"documents": primary}
    elif args.stage == "A03":
        try:
            primary = _records(primary_raw, "A03 classifications")
            secondary = _field_records(secondary_raw)
        except ValueError as exc:
            parser.error(str(exc))
        result = build_drawing_index(primary, secondary, config)
        inputs = {"classifications": primary, "fields": secondary}
    elif args.stage == "B01":
        try:
            primary = _records(primary_raw, "B01 drawing index")
        except ValueError as exc:
            parser.error(str(exc))
        if (
            isinstance(secondary_raw, dict)
            and "records" not in secondary_raw
            and tertiary_raw is not None
        ):
            try:
                tertiary, word_exclusions = validate_b00_word_bundle(
                    tertiary_raw, tertiary_manifest, config
                )
            except ValueError as exc:
                parser.error(str(exc))
            if not isinstance(corrections, list):
                parser.error("B01 --corrections must be a JSON list")
            result = combine_bom_candidate_sources(
                primary,
                secondary_raw,
                tertiary,
                config,
                word_exclusions=word_exclusions,
                corrections=corrections,
            )
            inputs = {
                "drawing_index": primary,
                "historical_structured_bom": secondary_raw,
                "word_documents": tertiary,
                "word_exclusions": word_exclusions,
                "word_bundle_manifest": tertiary_manifest,
                "corrections": corrections,
            }
        elif isinstance(secondary_raw, dict) and "records" not in secondary_raw:
            result = reuse_historical_bom_candidates(primary, secondary_raw, config)
            inputs = {
                "drawing_index": primary,
                "historical_structured_bom": secondary_raw,
            }
        else:
            try:
                secondary = _records(secondary_raw, "B01 word documents")
            except ValueError as exc:
                parser.error(str(exc))
            result = extract_asm_bom(primary, secondary, config)
            inputs = {"drawing_index": primary, "word_documents": secondary}
    elif args.stage == "B02":
        try:
            primary = _records(primary_raw, "B02 drawing index")
            secondary = _records(secondary_raw, "B02 BOM parents")
        except ValueError as exc:
            parser.error(str(exc))
        source_findings = (
            secondary_raw.get("exclusions", [])
            if isinstance(secondary_raw, dict)
            else []
        )
        if not isinstance(source_findings, list):
            parser.error("B02 BOM bundle exclusions must be a list")
        result = audit_asm_bom(
            primary,
            secondary,
            config,
            source_findings=source_findings,
        )
        inputs = {
            "drawing_index": primary,
            "bom_parents": secondary,
            "source_findings": source_findings,
        }
    elif args.stage == "C01":
        try:
            primary = _records(primary_raw, "C01 drawing index")
            secondary = _records(secondary_raw, "C01 BOM parents")
            tertiary = _records(tertiary_raw, "C01 findings")
        except ValueError as exc:
            parser.error(str(exc))
        if not isinstance(overrides, list):
            parser.error("C01 --overrides must be a JSON list")
        source_findings = (
            secondary_raw.get("exclusions", [])
            if isinstance(secondary_raw, dict)
            else []
        )
        if not isinstance(source_findings, list):
            parser.error("C01 BOM bundle exclusions must be a list")
        result = build_relationships(
            primary,
            secondary,
            tertiary,
            config,
            overrides=overrides,
            source_findings=source_findings,
        )
        inputs = {
            "drawing_index": primary,
            "bom_parents": secondary,
            "findings": tertiary,
            "source_findings": source_findings,
            "overrides": overrides,
        }
    else:
        try:
            primary = _records(primary_raw, "C02 drawing index")
            secondary = _records(secondary_raw, "C02 relationships")
        except ValueError as exc:
            parser.error(str(exc))
        result = build_project_owner_output(primary, secondary, config)
        inputs = {"drawing_index": primary, "relationships": secondary}

    bundle = result.as_dict()
    manifest = build_manifest(stage=args.stage, config=config, inputs=inputs, result=bundle)
    print(json.dumps({"mode": "write" if args.write else "preview", "audit": result.audit, "manifest": manifest}, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.write:
        return 0
    if not args.out or not args.manifest_out:
        parser.error("--write requires --out and --manifest-out")
    write_json_pair_exclusive(args.out, bundle, args.manifest_out, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
