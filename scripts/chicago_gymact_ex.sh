#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${GYMACT_CHICAGO_PORT:-8765}"
BASE_URL="http://127.0.0.1:${PORT}"
LOG_FILE="${TMPDIR:-/tmp}/gymact-ex-chicago-server.log"

for tool in uv mix curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "BLOCKED: required tool '$tool' not on PATH" >&2
    exit 3
  fi
done

cd "$ROOT"
uv sync --frozen

cd "$ROOT/beam/gymact_ex"
mix deps.get

cd "$ROOT"
GYMACT_CHICAGO_PORT="$PORT" uv run python scripts/chicago_gymact_ex_server.py >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  wait "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

READY=0
for _ in $(seq 1 60); do
  if curl --fail --silent "$BASE_URL/health" >/dev/null; then
    READY=1
    break
  fi
  sleep 0.25
done

if [[ "$READY" != "1" ]]; then
  echo "BLOCKED: real GymAct FastAPI server did not become healthy" >&2
  cat "$LOG_FILE" >&2 || true
  exit 3
fi

cd "$ROOT/beam/gymact_ex"
GYMACT_CHICAGO=1 GYMACT_BASE_URL="$BASE_URL" mix test

echo "ALIVE: GymActEx crossed the real FastAPI/GymAct/MemoryProvider boundary"
