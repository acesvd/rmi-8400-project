#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  echo "Missing .venv. Run ./scripts/setup_local.sh first."
  exit 1
fi

source .venv/bin/activate

uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 > /tmp/appeals_backend.log 2>&1 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Backend started (PID $BACKEND_PID). Logs: /tmp/appeals_backend.log"
echo "Starting Streamlit UI..."
streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0
