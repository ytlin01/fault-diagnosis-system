#!/usr/bin/env bash
# ============================================================
# FaultDx — gx10 Ubuntu Setup & Run Reference
# ============================================================
# Sections:
#   0. Pre-check
#   1. System dependencies
#   2. Python 3.11
#   3. uv (package manager)
#   4. Project setup
#   5. Neo4j
#   6. Ollama
#   7. Run: full pipeline
#   8. Run: Route A only
#   9. Run: Route B only
#  10. Run: Route C only
#  11. Run: Eval
# ============================================================

# ── Shared settings ─────────────────────────────────────────
REPO="$HOME/FaultDx_main"    # adjust if repo lives elsewhere
VENV="$REPO/.venv"
PY="$VENV/bin/python"


# ============================================================
# SECTION 0 — PRE-CHECK
# Run this first to see what is already installed.
# ============================================================

echo "=== FaultDx gx10 Pre-check ==="

# 0-a. OS
lsb_release -a 2>/dev/null || cat /etc/os-release

# 0-b. Python
echo "--- Python ---"
python3 --version 2>/dev/null || echo "python3 not found"
python3.11 --version 2>/dev/null || echo "python3.11 not found"

# 0-c. uv
echo "--- uv ---"
uv --version 2>/dev/null || echo "uv not found"

# 0-d. git
echo "--- git ---"
git --version 2>/dev/null || echo "git not found"

# 0-e. Neo4j
echo "--- Neo4j ---"
neo4j --version 2>/dev/null || echo "neo4j CLI not found"
systemctl is-active neo4j 2>/dev/null || echo "neo4j service not active / not installed"

# 0-f. Ollama
echo "--- Ollama ---"
ollama --version 2>/dev/null || echo "ollama not found"
systemctl is-active ollama 2>/dev/null || echo "ollama service not active / not installed"

# 0-g. CUDA / GPU (for Ollama GPU inference)
echo "--- GPU ---"
nvidia-smi 2>/dev/null || echo "nvidia-smi not found (CPU-only or drivers not installed)"

# 0-h. Repo and venv
echo "--- Repo ---"
[ -d "$REPO" ]          && echo "Repo exists: $REPO"  || echo "Repo NOT found: $REPO"
[ -d "$VENV" ]          && echo "venv exists: $VENV"  || echo "venv NOT found"
[ -f "$REPO/.env" ]     && echo ".env exists"          || echo ".env NOT found (copy from .env.example)"

# 0-i. Port availability
echo "--- Ports ---"
ss -tlnp | grep -E "7474|7687|11434" || echo "none of 7474/7687/11434 in use"

echo ""
echo "Pre-check done. Fix any FAILs above before continuing."


# ============================================================
# SECTION 1 — SYSTEM DEPENDENCIES
# ============================================================

sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    git \
    curl \
    wget \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libffi-dev \
    liblzma-dev \
    openjdk-21-jre-headless   # required by Neo4j


# ============================================================
# SECTION 2 — PYTHON 3.11
# ============================================================

# Check if 3.11 is already available
python3.11 --version 2>/dev/null && echo "Python 3.11 already installed" || {
    sudo apt install -y software-properties-common
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install -y python3.11 python3.11-venv python3.11-dev
}


# ============================================================
# SECTION 3 — uv (fast package manager)
# ============================================================

uv --version 2>/dev/null || {
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Reload PATH so uv is available in this session
    source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
}


# ============================================================
# SECTION 4 — PROJECT SETUP
# ============================================================

# 4-a. Clone repo (skip if already cloned)
[ -d "$REPO" ] || git clone https://github.com/Nicole-gemini/FaultDx_main.git "$REPO"

cd "$REPO"

# 4-b. Create venv with Python 3.11
[ -d "$VENV" ] || uv venv --python python3.11 "$VENV"

# 4-c. Install base dependencies
uv pip install --python "$PY" -r requirements/base.txt

# 4-d. Copy and fill .env
[ -f .env ] || cp .env.example .env
# Then open .env and fill in:
#   FAULTDX_PROVIDER_TYPE=ollama        (or company_api)
#   FAULTDX_OLLAMA_ENDPOINT=http://localhost:11434
#   FAULTDX_OLLAMA_MODEL=qwen2.5:7b
#   FAULTDX_NEO4J_HOST=bolt://127.0.0.1:7687
#   FAULTDX_NEO4J_USER=neo4j
#   FAULTDX_NEO4J_PASSWORD=<your_password>
#   FAULTDX_MASKING_SALT=<random_string>
nano .env   # or: vim .env

# 4-e. Create data directory scaffold
mkdir -p data/raw \
         data/processed/structured \
         data/processed/unstructured \
         data/processed/unstructured_vlm \
         data/processed/masked \
         data/processed/indexes \
         data/processed/review_pending \
         data/serving_structured \
         data/serving_unstructured \
         data/serving_masked \
         data/eval \
         tmp

# 4-f. Run environment pre-check via project's own verifier
"$PY" scripts/bootstrap/verify_env.py


# ============================================================
# SECTION 5 — NEO4J
# ============================================================

# 5-a. Add Neo4j repo and install
# Match the version on your source machine (check: neo4j --version on Windows machine)
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | \
    sudo gpg --dearmor -o /etc/apt/keyrings/neotechnology.gpg

echo 'deb [signed-by=/etc/apt/keyrings/neotechnology.gpg] https://debian.neo4j.com stable latest' | \
    sudo tee /etc/apt/sources.list.d/neo4j.list

sudo apt update
sudo apt install -y neo4j     # or: neo4j=1:5.x.x for a pinned version

# 5-b. Set initial password BEFORE first start
sudo neo4j-admin dbms set-initial-password <your_password>

# 5-c. Enable and start
sudo systemctl enable neo4j
sudo systemctl start neo4j
sudo systemctl status neo4j

# 5-d. Verify (should return bolt://127.0.0.1:7687)
ss -tlnp | grep 7687

# 5-e. Load data from dump file (transferred from Windows machine)
# Stop service first, then load, then restart
sudo systemctl stop neo4j
sudo neo4j-admin database load neo4j \
    --from-path=/path/to/dump/folder/ \
    --overwrite-destination=true
sudo systemctl start neo4j


# ============================================================
# SECTION 6 — OLLAMA
# ============================================================

# 6-a. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 6-b. Enable as a service (installer usually does this; verify)
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama

# 6-c. Pull the model used by FaultDx
# Default from .env.example: qwen2.5:7b
ollama pull qwen2.5:7b

# Optional — if you want the model in base.yaml (llama3.1):
# ollama pull llama3.1

# 6-d. Verify Ollama is responding
curl http://localhost:11434/api/tags

# 6-e. Optional: custom models directory
# Set OLLAMA_MODELS before starting the service if models are on a separate disk:
# sudo systemctl edit ollama   # add: Environment="OLLAMA_MODELS=/mnt/models"
# sudo systemctl restart ollama


# ============================================================
# SECTION 7 — RUN: FULL PIPELINE (all routes, interactive)
# ============================================================

cd "$REPO"

# Interactive mode — prompts for route [a/b/c] then query
"$PY" scripts/cli_route_abc.py

# Full pipeline with explicit provider
"$PY" scripts/cli_route_abc.py --provider ollama --model qwen2.5:7b


# ============================================================
# SECTION 8 — RUN: ROUTE A (structured KG diagnosis)
# ============================================================

# Interactive REPL (Route A only)
"$PY" scripts/cli_route_a.py

# Single query via unified CLI
"$PY" scripts/cli_route_abc.py --route a \
    --query "M07 station alarm" \
    --provider ollama

# Save output to file
"$PY" scripts/cli_route_abc.py --route a \
    --query "M07 station alarm" \
    --provider ollama \
    --out tmp/route_a_out.json

# Plumbing smoke test (unit-level, no LLM needed)
"$PY" scripts/run_eval/run_route_a_plumbing_smoke.py

# End-to-end smoke test
"$PY" scripts/run_eval/run_route_a_e2e_smoke.py


# ============================================================
# SECTION 9 — RUN: ROUTE B (document evidence retrieval)
# ============================================================

# Single query
"$PY" scripts/cli_route_abc.py --route b \
    --query "TCP IPv4 IP address settings" \
    --provider ollama

# Run a named fixture
"$PY" scripts/cli_route_abc.py --fixture route_b --fixture-id RB-SAFE-001

# List available query-bank cases
"$PY" scripts/cli_route_abc.py --list-query-bank route_b

# Run a specific query-bank case
"$PY" scripts/cli_route_abc.py --route b \
    --query-id RB-QB-001 \
    --provider ollama \
    --out tmp/route_b_out.json

# Render answer text only (no raw JSON printed)
"$PY" scripts/cli_route_abc.py --route b \
    --query-id RB-QB-001 \
    --render-only

# Anchor retrieval smoke test
"$PY" scripts/run_eval/run_route_b_anchor_smoke.py

# Retrieval quality benchmark
"$PY" scripts/run_eval/run_route_b_benchmark_v0.py

# ============================================================
# SECTION 10 — RUN: ROUTE C (case retrieval / governance)
# ============================================================

# Single query
"$PY" scripts/cli_route_abc.py --route c \
    --query "similar alarm C07 last month" \
    --provider ollama

# Run a named fixture
"$PY" scripts/cli_route_abc.py --fixture route_c --fixture-id RC-SAFE-001

# List query-bank cases
"$PY" scripts/cli_route_abc.py --list-query-bank route_c

# Run a specific query-bank case
"$PY" scripts/cli_route_abc.py --route c \
    --query-id RC-QB-001 \
    --provider ollama \
    --out tmp/route_c_out.json

# Case retrieval benchmark
"$PY" scripts/run_eval/run_route_c_case_benchmark_v0.py


# ============================================================
# SECTION 11 — RUN: EVAL
# ============================================================

# Phase 1 full eval (routing + all routes)
"$PY" scripts/run_eval/run_phase1_eval_v0.py

# Route A eval only
"$PY" scripts/eval/eval_route_a.py

# LLM smoke test (verifies provider connectivity)
"$PY" scripts/run_eval/smoke_test_llm.py

# Synthesis prompt test
"$PY" scripts/run_eval/test_synthesis_prompt.py

# Stub provider — fastest, no LLM or Neo4j needed
"$PY" scripts/run_eval/run_phase1_eval_v0.py   # uses FAULTDX_PROVIDER_TYPE=stub from .env
