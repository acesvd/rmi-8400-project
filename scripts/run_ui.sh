#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Run ./scripts/setup_local.sh first."
  exit 1
fi

source .venv/bin/activate

streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0
