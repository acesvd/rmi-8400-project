#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend/requirements.txt -r ui/requirements.txt

echo ""
echo "Local setup complete."
echo "Activate env: source .venv/bin/activate"
echo "Run backend: ./scripts/run_backend.sh"
echo "Run UI: ./scripts/run_ui.sh"
