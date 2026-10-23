#!/usr/bin/env bash
# FaultDx Phase 1 — Ubuntu environment setup
# Creates a Python 3.11 virtual environment with uv and installs all dependencies.
#
# Prerequisites:
#   - Python 3.11 (sudo apt install python3.11 python3.11-venv python3.11-dev)
#   - uv (curl -LsSf https://astral.sh/uv/install.sh | sh)
#   - Build essentials for graphrag dependencies:
#       sudo apt install build-essential
#
# Usage:
#   cd <repo_root>
#   bash scripts/bootstrap/setup_env.sh
#
# After setup, verify with:
#   bash scripts/bootstrap/verify_env.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo ""
echo "=== FaultDx Phase 1 — Ubuntu Environment Setup ==="
echo "Repo root: $REPO_ROOT"
cd "$REPO_ROOT"

# ── 1. Check uv ───────────────────────────────────────────────────────────────
echo ""
echo "── Step 1: Checking uv ───────────────────────────────────────────────────"
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv not found."
    echo "Install uv:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then restart your shell and re-run this script."
    exit 1
fi
echo "uv: $(uv --version)"

# ── 2. Check Python 3.11 ──────────────────────────────────────────────────────
echo ""
echo "── Step 2: Checking Python 3.11 ──────────────────────────────────────────"
PYTHON311=$(command -v python3.11 2>/dev/null || true)
if [ -z "$PYTHON311" ]; then
    echo "WARNING: python3.11 not found on PATH."
    echo "uv will attempt to locate or download a suitable Python 3.11 runtime."
    echo "To install manually:  sudo apt install python3.11 python3.11-venv python3.11-dev"
else
    echo "python3.11: $($PYTHON311 --version)"
fi

# ── 3. Create virtual environment ─────────────────────────────────────────────
echo ""
echo "── Step 3: Creating .venv (Python 3.11) ──────────────────────────────────"
if [ -d ".venv" ]; then
    echo ".venv already exists — skipping creation. Remove .venv to force recreate."
else
    uv venv --python 3.11 .venv
    echo ".venv created."
fi

# Activate for subsequent pip calls in this script
# shellcheck disable=SC1091
source .venv/bin/activate

# ── 4. Install base dependencies ──────────────────────────────────────────────
echo ""
echo "── Step 4: Installing base dependencies ──────────────────────────────────"
echo "This includes graphrag (latest). May take several minutes on first run."
echo "GraphRAG full index build validation is expected to run on this server."
echo ""
uv pip install -r requirements/base.txt

# ── 5. Install dev dependencies ───────────────────────────────────────────────
echo ""
echo "── Step 5: Installing dev dependencies ───────────────────────────────────"
uv pip install -r requirements/dev.txt

# ── 6. .env setup reminder ────────────────────────────────────────────────────
echo ""
echo "── Step 6: .env setup ────────────────────────────────────────────────────"
if [ ! -f ".env" ]; then
    echo "No .env found. Creating from .env.example ..."
    cp .env.example .env
    echo ".env created. Edit it and set FAULTDX_PROVIDER_TYPE and other values."
else
    echo ".env already exists."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and set FAULTDX_PROVIDER_TYPE (stub | ollama | company_api)"
echo "  2. Run: bash scripts/bootstrap/verify_env.sh"
echo ""
