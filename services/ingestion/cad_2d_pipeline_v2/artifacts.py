from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(*, stage: str, config: dict, inputs: dict, result: dict) -> dict:
    config_hash = sha256_value(config)
    input_hashes = {name: sha256_value(value) for name, value in sorted(inputs.items())}
    result_hash = sha256_value(result)
    identity = sha256_value(
        {"stage": stage, "config": config_hash, "inputs": input_hashes, "result": result_hash}
    )
    return {
        "manifest_version": "cad-2d-run-v1",
        "run_id": f"cad2d_{stage.lower()}_{identity[:16]}",
        "stage": stage,
        "config_schema_version": config["schema_version"],
        "config_sha256": config_hash,
        "input_sha256": input_hashes,
        "result_sha256": result_hash,
        "promotion_state": "candidate",
        "graph_activation": False,
    }


def write_json_exclusive(path: str | Path, value: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return output


def write_json_pair_exclusive(
    output_path: str | Path,
    output_value: Any,
    manifest_path: str | Path,
    manifest_value: Any,
) -> tuple[Path, Path]:
    output = Path(output_path)
    manifest = Path(manifest_path)
    if output.resolve() == manifest.resolve():
        raise ValueError("output and manifest paths must be different")
    created: list[Path] = []
    try:
        write_json_exclusive(manifest, manifest_value)
        created.append(manifest)
        write_json_exclusive(output, output_value)
        created.append(output)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return output, manifest
