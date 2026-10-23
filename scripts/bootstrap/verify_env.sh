#!/usr/bin/env bash
# FaultDx Phase 1 — Ubuntu environment verification wrapper
# Activates the project venv and delegates to verify_env.py.
#
# Usage:
#   cd <repo_root>
#   bash scripts/bootstrap/verify_env.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo ""
echo "=== FaultDx Environment Verification (Ubuntu) ==="
echo "Repo root : $REPO_ROOT"
echo "Platform  : $(uname -sr)"
echo ""

# ── Locate Python ──────────────────────────────────────────────────────────────
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

if [ -f "$VENV_PYTHON" ]; then
    PYTHON_EXE="$VENV_PYTHON"
    echo "Using venv  : $PYTHON_EXE"
else
    # Fall back to system Python if venv not yet created
    PYTHON_EXE=$(command -v python3.11 2>/dev/null \
              || command -v python3   2>/dev/null \
              || command -v python    2>/dev/null || true)
    if [ -z "$PYTHON_EXE" ]; then
        echo "ERROR: Python not found. Run setup_env.sh first."
        exit 1
    fi
    echo "WARNING: .venv not found — using system Python: $PYTHON_EXE"
fi

echo "Python    : $($PYTHON_EXE --version 2>&1)"
echo ""

# ── Run verify_env.py ──────────────────────────────────────────────────────────
VERIFY_SCRIPT="$REPO_ROOT/scripts/bootstrap/verify_env.py"
"$PYTHON_EXE" "$VERIFY_SCRIPT"
EXIT_CODE=$?

echo ""
if [ "$EXIT_CODE" -ne 0 ]; then
    echo "Verification FAILED. Fix the issues above before proceeding."
    exit 1
else
    echo "Verification PASSED. Environment is ready."
    exit 0
fi
