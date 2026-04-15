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

TUNNEL_PROVIDER="${1:-ngrok}" # ngrok | cloudflared | none
API_PORT="${DEMO_API_PORT:-8000}"
UI_PORT="${DEMO_UI_PORT:-8501}"
BACKEND_LOG="${DEMO_BACKEND_LOG:-/tmp/appeals_backend.log}"
UI_LOG="${DEMO_UI_LOG:-/tmp/appeals_ui.log}"

# Optional demo-time overrides:
#   export APPEALS_OLLAMA_BASE_URL="https://your-school-endpoint"
#   export CLAIMRIGHT_UI_USERNAME="demo"
#   export CLAIMRIGHT_UI_PASSWORD="strong-password"

pids=()

cleanup() {
  for pid in "${pids[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT INT TERM

echo "Starting backend on port ${API_PORT}..."
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "$API_PORT" >"$BACKEND_LOG" 2>&1 &
pids+=("$!")

echo "Starting Streamlit UI on port ${UI_PORT}..."
streamlit run ui/app.py --server.port "$UI_PORT" --server.address 0.0.0.0 >"$UI_LOG" 2>&1 &
pids+=("$!")

echo ""
echo "Backend log:   $BACKEND_LOG"
echo "Streamlit log: $UI_LOG"
echo "Local UI URL:  http://localhost:${UI_PORT}"
echo "API docs URL:  http://localhost:${API_PORT}/docs"
echo ""

case "$TUNNEL_PROVIDER" in
  ngrok)
    if ! command -v ngrok >/dev/null 2>&1; then
      echo "ngrok is not installed. Install ngrok or run with: ./scripts/run_demo.sh cloudflared"
      exit 1
    fi
    echo "Starting ngrok tunnel (Ctrl+C to stop everything)..."
    ngrok http "$UI_PORT"
    ;;
  cloudflared)
    if ! command -v cloudflared >/dev/null 2>&1; then
      echo "cloudflared is not installed. Install cloudflared or run with: ./scripts/run_demo.sh ngrok"
      exit 1
    fi
    echo "Starting cloudflared tunnel (Ctrl+C to stop everything)..."
    cloudflared tunnel --url "http://localhost:${UI_PORT}"
    ;;
  none)
    echo "Tunnel disabled (mode: none). Services are running locally."
    echo "Press Ctrl+C to stop."
    while true; do
      sleep 60
    done
    ;;
  *)
    echo "Unknown tunnel provider: $TUNNEL_PROVIDER"
    echo "Usage: ./scripts/run_demo.sh [ngrok|cloudflared|none]"
    exit 1
    ;;
esac
