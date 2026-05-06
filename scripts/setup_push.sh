#!/usr/bin/env bash
# One-command setup for Web Push VAPID keys.
#
# Run this from anywhere on your Mac:
#   bash ~/anti-billionaires-app/scripts/setup_push.sh
#
# Or if executable:
#   ~/anti-billionaires-app/scripts/setup_push.sh
#
# Auto-resolves the project directory from this script's own location, creates
# the venv on first run, installs requirements, then prints the three env
# vars to paste into Railway. Safe to re-run, but every run generates a NEW
# keypair — old subscriptions break if you swap keys, so only re-run when
# you intentionally want to rotate.

set -e

# Resolve project root from script location, regardless of where you run it from
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

echo "[setup] Project: $PROJECT_ROOT"

# Bootstrap venv on first run
if [ ! -d ".venv" ]; then
    echo "[setup] Creating Python virtual environment (first run)..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[setup] Installing the one package we need (cryptography)..."
pip install -q --upgrade pip > /dev/null 2>&1 || true
# Keygen only needs `cryptography` — install just that to avoid pulling in
# the full app's deps (Pillow, etc.) which can have build issues on bleeding-
# edge local Python versions. Railway installs the full requirements.txt
# during deploy; this script only needs to generate keys, not run the app.
pip install -q cryptography

echo ""
echo "================================================================"
echo "   COPY THE THREE LINES BELOW INTO RAILWAY → VARIABLES"
echo "   (Each line is its own env var: name=value)"
echo "================================================================"
echo ""

python scripts/generate_vapid_keys.py

echo ""
echo "================================================================"
echo "   Done. After saving in Railway, it will auto-redeploy."
echo "   Push notifications activate as soon as the deploy finishes."
echo "================================================================"
