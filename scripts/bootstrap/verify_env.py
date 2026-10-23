#!/usr/bin/env python3
"""
FaultDx Phase 1 — cross-platform environment smoke test.

Called by:
  Windows : scripts/bootstrap/verify_env.ps1
  Ubuntu  : scripts/bootstrap/verify_env.sh

Exit code: 0 = all checks passed, 1 = one or more checks failed.
"""

import sys
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT   = SCRIPT_DIR.parent.parent.resolve()

# ── Check runner ───────────────────────────────────────────────────────────────
_results: list[tuple[str, bool, str]] = []   # (label, passed, note)

def check(label: str, passed: bool, note: str = "") -> None:
    _results.append((label, passed, note))
    status   = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
    note_str = f"  ({note})" if note else ""
    print(f"  [{status}] {label}{note_str}")


# ──────────────────────────────────────────────────────────────────────────────
# 1. Python version
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 1. Python version ─────────────────────────────────────────────────────")
major, minor = sys.version_info[:2]
check(
    f"Python >= 3.11",
    major == 3 and minor >= 11,
    f"found {sys.version.split()[0]}",
)

# ──────────────────────────────────────────────────────────────────────────────
# 2. Core package imports
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 2. Core package imports ───────────────────────────────────────────────")
CORE_PACKAGES: list[tuple[str, str]] = [
    ("pyyaml",        "yaml"),
    ("python-dotenv", "dotenv"),
    ("pydantic",      "pydantic"),
    ("httpx",         "httpx"),
    ("neo4j",         "neo4j"),
]
for pkg_label, import_name in CORE_PACKAGES:
    try:
        mod = __import__(import_name)
        ver = getattr(mod, "__version__", "")
        check(f"import {import_name}", True, ver)
    except ImportError as exc:
        check(f"import {import_name}", False, str(exc))

# ──────────────────────────────────────────────────────────────────────────────
# 3. GraphRAG import and version
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 3. GraphRAG ───────────────────────────────────────────────────────────")
try:
    import graphrag  # type: ignore
    version = getattr(graphrag, "__version__", "unknown")
    check("import graphrag", True, f"version={version}")
except ImportError as exc:
    check("import graphrag", False, str(exc))

# ──────────────────────────────────────────────────────────────────────────────
# 4. Config file loading
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 4. Config files ───────────────────────────────────────────────────────")
try:
    import yaml  # type: ignore

    base_cfg = REPO_ROOT / "configs" / "base.yaml"
    if not base_cfg.exists():
        check("configs/base.yaml exists", False, "file not found")
    else:
        with open(base_cfg, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        required_keys = {"phase", "provider", "graph", "logging"}
        missing = required_keys - set(cfg.keys())
        check(
            "configs/base.yaml loads + required keys present",
            len(missing) == 0,
            f"missing: {missing}" if missing else "ok",
        )
except Exception as exc:
    check("configs/base.yaml", False, str(exc))

# ──────────────────────────────────────────────────────────────────────────────
# 5. .env loading and key variables
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 5. Environment variables ──────────────────────────────────────────────")
try:
    from dotenv import load_dotenv  # type: ignore

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        check(".env found and loaded", True)
    else:
        # Not an error: .env is optional; env vars may be injected by the shell
        check(".env not present (env vars may be injected externally)", True, "ok")

    provider_type = os.getenv("FAULTDX_PROVIDER_TYPE", "")
    if provider_type:
        valid = provider_type in {"stub", "ollama", "company_api"}
        check(
            "FAULTDX_PROVIDER_TYPE is set",
            valid,
            f"value={provider_type!r}" + ("" if valid else " — expected stub|ollama|company_api"),
        )
    else:
        # Warn but do not fail: first-time setup before .env is filled
        check(
            "FAULTDX_PROVIDER_TYPE not set",
            True,
            "warning: copy .env.example to .env and set FAULTDX_PROVIDER_TYPE",
        )

except Exception as exc:
    check(".env / env var loading", False, str(exc))

# ──────────────────────────────────────────────────────────────────────────────
# 6. Data directory scaffolding
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 6. Data directories ───────────────────────────────────────────────────")
expected_dirs = [
    "data/raw",
    "data/processed",
    "data/serving_structured",
    "data/serving_unstructured",
    "data/serving_unstructured_vlm",
    "data/eval",
]
for rel_dir in expected_dirs:
    p = REPO_ROOT / rel_dir
    check(f"dir  {rel_dir}", p.exists(), "ok" if p.exists() else "missing — run git checkout or mkdir")

# ──────────────────────────────────────────────────────────────────────────────
# 7. Bootstrap scripts present
# ──────────────────────────────────────────────────────────────────────────────
print("\n── 7. Bootstrap scripts present ──────────────────────────────────────────")
bootstrap_scripts = [
    "scripts/bootstrap/setup_env.ps1",
    "scripts/bootstrap/setup_env.sh",
    "scripts/bootstrap/verify_env.py",
    "scripts/bootstrap/verify_env.ps1",
    "scripts/bootstrap/verify_env.sh",
]
for rel_path in bootstrap_scripts:
    p = REPO_ROOT / rel_path
    check(f"file {rel_path}", p.exists())

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
print("\n── Summary ───────────────────────────────────────────────────────────────")
passed = sum(1 for _, ok, _ in _results if ok)
failed = sum(1 for _, ok, _ in _results if not ok)
total  = len(_results)

print(f"  {passed}/{total} checks passed")
if failed:
    print(f"  \033[31m{failed} check(s) FAILED\033[0m — see output above")
    sys.exit(1)
else:
    print("  \033[32mAll checks passed.\033[0m")
    sys.exit(0)
