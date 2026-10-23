"""Run local VLM metadata enrichment for unstructured canonical documents.

This script reads existing canonical JSON, resolves local MinerU image/table
assets, calls a local Ollama VLM, and writes an enriched canonical copy. It is
not part of the default ingestion or masking path.

Examples:
    python scripts/ingest/run_enrich_unstructured_vlm.py --file data/processed/unstructured/HIVE_Error_Code_8f5115f98988_canonical.json --dry-run
    python scripts/ingest/run_enrich_unstructured_vlm.py --file data/processed/unstructured/HIVE_Error_Code_8f5115f98988_canonical.json --model qwen2.5vl:7b --limit 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.local_vlm import (  # noqa: E402
    DEFAULT_LOCAL_VLM_PROMPT,
    OllamaLocalVlmClient,
    collect_local_vlm_targets,
    enrich_document_with_local_vlm,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FaultDx local VLM enrichment for unstructured canonical JSON"
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "configs" / "local_vlm.yaml"),
        help="Path to local VLM runtime config YAML.",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("FAULTDX_LOCAL_VLM_PROFILE"),
        help="Config profile to use, for example e2a or e3. Defaults to config default_profile.",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Process a single canonical JSON file",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Process canonical JSON files under this directory",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for enriched canonical JSON copies",
    )
    parser.add_argument(
        "--asset-root",
        action="append",
        default=None,
        help="Root directory used to resolve asset://local image refs. Can be repeated.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Local Ollama VLM model name",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Ollama endpoint. Localhost/127.0.0.1 only unless --allow-non-local-endpoint is set.",
    )
    parser.add_argument(
        "--allow-non-local-endpoint",
        action="store_true",
        default=None,
        help="Allow a non-local endpoint. Use only for approved, internal,脱敏-safe providers.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max VLM targets per document. Use 0 for all targets.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        help="Per-image Ollama request timeout",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Optional UTF-8 prompt file. Defaults to the built-in FaultDx metadata prompt.",
    )
    parser.add_argument(
        "--existing-text-limit",
        type=int,
        default=None,
        help="Max existing extracted text characters included in each VLM prompt",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run blocks that already have local_vlm.executed=true",
    )
    parser.add_argument(
        "--include-raw-response",
        action="store_true",
        help="Store full Ollama raw responses, including large context token arrays. Off by default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and print candidate targets without calling the model or writing files",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input canonical JSON instead of writing to --output-dir",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = _apply_config_defaults(parse_args())
    if not args.dry_run:
        _validate_endpoint(args.endpoint, allow_non_local=args.allow_non_local_endpoint)

    input_files = _resolve_input_files(args)
    asset_roots = _asset_roots(args)
    prompt = _load_prompt(args.prompt_file)
    limit = None if args.limit <= 0 else args.limit

    dry_run_results: list[dict[str, Any]] = []
    write_results: list[dict[str, Any]] = []
    client = None
    if not args.dry_run:
        client = OllamaLocalVlmClient(
            model=args.model,
            endpoint=args.endpoint,
            timeout_seconds=args.timeout_seconds,
        )

    for input_file in input_files:
        document = _read_json(input_file)
        if args.dry_run:
            targets = collect_local_vlm_targets(
                document,
                asset_roots=asset_roots,
                limit=limit,
                force=args.force,
            )
            dry_run_results.append({
                "input_file": str(input_file),
                "doc_id": document.get("doc_id"),
                "target_count": len(targets),
                "targets": [target.to_json() for target in targets],
            })
            continue

        assert client is not None
        enriched = enrich_document_with_local_vlm(
            document,
            client=client,
            asset_roots=asset_roots,
            prompt_template=prompt,
            limit=limit,
            force=args.force,
            existing_text_limit=args.existing_text_limit,
            include_raw_response=args.include_raw_response,
        )
        output_path = input_file if args.in_place else _output_path(Path(args.output_dir), input_file)
        _write_json(enriched, output_path)
        write_results.append({
            "input_file": str(input_file),
            "output_file": str(output_path),
            "doc_id": enriched.get("doc_id"),
            "local_vlm": enriched.get("normalization", {}).get("local_vlm", {}),
        })

    if args.dry_run:
        print(json.dumps({
            "mode": "dry-run",
            "profile": args.profile,
            "model": args.model,
            "endpoint": args.endpoint,
            "runtime": _runtime_config(args),
            "asset_roots": [str(path) for path in asset_roots],
            "files": dry_run_results,
        }, ensure_ascii=False, indent=2))
        return

    print(json.dumps({
        "processed_files": len(write_results),
        "profile": args.profile,
        "model": args.model,
        "endpoint": args.endpoint,
        "runtime": _runtime_config(args),
        "results": write_results,
    }, ensure_ascii=False, indent=2))


def _resolve_input_files(args: argparse.Namespace) -> list[Path]:
    if args.file and args.input_dir:
        raise ValueError("Use either --file or --input-dir, not both.")
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            raise FileNotFoundError(f"canonical file not found: {file_path}")
        return [file_path]

    input_dir = Path(args.input_dir or PROJECT_ROOT / "data" / "processed" / "unstructured")
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")
    files = sorted(
        path for path in input_dir.glob("*_canonical.json")
        if path.is_file()
    )
    if not files:
        raise FileNotFoundError(f"no *_canonical.json files found under {input_dir}")
    return files


def _asset_roots(args: argparse.Namespace) -> list[Path]:
    if args.asset_root:
        return [Path(value) for value in args.asset_root]
    return [Path(value) for value in args.asset_roots]


def _apply_config_defaults(args: argparse.Namespace) -> argparse.Namespace:
    config = _load_local_vlm_config(Path(args.config))
    profile_name = args.profile or config.get("default_profile") or "e2a"
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(
            f"local VLM profile '{profile_name}' not found in {args.config}. "
            f"Available profiles: {list(profiles.keys())}"
        )
    profile = profiles[profile_name] or {}

    args.profile = profile_name
    args.model = (
        args.model
        or os.environ.get("FAULTDX_LOCAL_VLM_MODEL")
        or profile.get("model")
        or "qwen2.5vl:7b"
    )
    args.endpoint = (
        args.endpoint
        or os.environ.get("FAULTDX_OLLAMA_ENDPOINT")
        or profile.get("endpoint")
        or "http://localhost:11434"
    )
    args.output_dir = (
        args.output_dir
        or profile.get("output_dir")
        or str(PROJECT_ROOT / "data" / "processed" / "unstructured_vlm")
    )
    args.limit = _int_or_default(args.limit, profile.get("limit"), 3)
    args.timeout_seconds = _int_or_default(
        args.timeout_seconds,
        profile.get("timeout_seconds"),
        120,
    )
    args.existing_text_limit = _int_or_default(
        args.existing_text_limit,
        profile.get("existing_text_limit"),
        1200,
    )
    args.allow_non_local_endpoint = _bool_or_default(
        args.allow_non_local_endpoint,
        profile.get("allow_non_local_endpoint"),
        False,
    )
    args.ollama_models_dir = (
        os.environ.get("FAULTDX_OLLAMA_MODELS_DIR")
        or profile.get("ollama_models_dir")
    )
    startup_command = profile.get("startup_command")
    args.startup_command = str(_resolve_project_path(startup_command)) if startup_command and str(startup_command).endswith(".ps1") else startup_command
    if args.prompt_file is None and profile.get("prompt_file"):
        args.prompt_file = str(_resolve_project_path(profile["prompt_file"]))

    if args.asset_root is None:
        configured_roots = profile.get("asset_roots") or [
            "data/processed/unstructured_assets",
            "data/raw/unstructured_input/mineru_output",
            "data/raw/unstructured_input",
        ]
        args.asset_roots = [str(_resolve_project_path(value)) for value in configured_roots]
    else:
        args.asset_roots = []
    return args


def _runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "provider": "ollama",
        "ollama_models_dir": args.ollama_models_dir,
        "startup_command": args.startup_command,
    }


def _load_local_vlm_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"default_profile": "e2a", "profiles": {"e2a": {}}}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"local VLM config must be a mapping: {path}")
    return payload


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _int_or_default(primary: int | None, secondary: Any, default: int) -> int:
    if primary is not None:
        return int(primary)
    if secondary is not None:
        return int(secondary)
    return default


def _bool_or_default(primary: bool | None, secondary: Any, default: bool) -> bool:
    if primary is not None:
        return bool(primary)
    if secondary is not None:
        return bool(secondary)
    return default


def _load_prompt(prompt_file: str | None) -> str:
    if not prompt_file:
        return DEFAULT_LOCAL_VLM_PROMPT
    return Path(prompt_file).read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"canonical JSON must be an object: {path}")
    return payload


def _write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _output_path(output_dir: Path, input_file: Path) -> Path:
    return output_dir / f"{input_file.stem}_vlm.json"


def _validate_endpoint(endpoint: str, *, allow_non_local: bool) -> None:
    if allow_non_local:
        return
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    allowed_hosts = {"localhost", "127.0.0.1", "::1"}
    if host not in allowed_hosts:
        raise ValueError(
            "Refusing to send unstructured images to a non-local VLM endpoint. "
            "Use --allow-non-local-endpoint only for approved internal providers and脱敏-safe inputs."
        )


if __name__ == "__main__":
    main()
