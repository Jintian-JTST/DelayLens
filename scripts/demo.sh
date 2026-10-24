#!/usr/bin/env bash
# One-command local demo for macOS/Linux: offline bus 29 snapshot API + Vite UI, browser opens itself.
# Run from anywhere:  ./scripts/demo.sh        (add --live to use backend/.env instead of the snapshot)
# Press Ctrl+C in this window to stop both servers.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend="$root/backend"
frontend="$root/frontend"
# Team demo snapshot: Saturday 17:00 -> 16:22 / 92%, 56 trips. Relative paths resolve from the repo root.
snapshot="docs/evidence/bus29-db-final-20261024T202558Z"
live=0
[ "${1:-}" = "--live" ] && live=1

for tool in node npm curl; do
    command -v "$tool" >/dev/null 2>&1 || { echo "$tool is not installed or not on PATH." >&2; exit 1; }
done

port_free() { ! (echo >"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
find_free_port() {
    local port
    for port in $(seq "$1" $(($1 + 50))); do
        if port_free "$port"; then echo "$port"; return 0; fi
    done
    echo "No free port found from $1" >&2
    return 1
}
wait_url() {  # url seconds pid
    local i
    for i in $(seq 1 "$2"); do
        kill -0 "$3" 2>/dev/null || return 1
        curl -fsS -o /dev/null --max-time 2 "$1" 2>/dev/null && return 0
        sleep 1
    done
    return 1
}
kill_tree() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null || true); do kill_tree "$child"; done
    kill "$1" 2>/dev/null || true
}

# Backend runner: uv when installed, otherwise an existing backend/.venv (see README for creating one by hand).
if command -v uv >/dev/null 2>&1; then
    (cd "$backend" && uv sync --locked)
    api_cmd=(uv run --locked uvicorn)
elif [ -x "$backend/.venv/bin/uvicorn" ]; then
    api_cmd=("$backend/.venv/bin/uvicorn")
else
    echo "Neither uv nor backend/.venv is available. Install uv, or create backend/.venv (see README)." >&2
    exit 1
fi

# Ports: take the usual ones if free, otherwise the next free ones; nothing already running is killed.
api_port="$(find_free_port 8000)"
web_port="$(find_free_port 5173)"

if [ ! -x "$frontend/node_modules/.bin/vite" ]; then
    echo "Installing frontend dependencies (first run only)..."
    (cd "$frontend" && npm ci)
fi

if [ "$live" = 1 ]; then unset SNAPSHOT_DIR; else export SNAPSHOT_DIR="$snapshot"; fi
export API_TARGET="http://127.0.0.1:$api_port"   # overrides frontend/.env.local, which may point at another port
log="${TMPDIR:-/tmp}/delaylens-backend.log"

api_pid=""
web_pid=""
cleanup() {
    trap - EXIT INT TERM
    [ -n "$web_pid" ] && kill_tree "$web_pid"
    [ -n "$api_pid" ] && kill_tree "$api_pid"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

echo "Starting API on port $api_port ($([ "$live" = 1 ] && echo 'live: backend/.env' || echo 'offline snapshot'))..."
(cd "$backend" && exec "${api_cmd[@]}" app.main:app --host 127.0.0.1 --port "$api_port") >"$log" 2>&1 &
api_pid=$!
if ! wait_url "http://127.0.0.1:$api_port/api/health" 90 "$api_pid"; then
    tail -n 20 "$log" >&2 || true
    echo "API did not start. Log: $log" >&2
    exit 1
fi

echo "Starting UI on port $web_port..."
(cd "$frontend" && exec npm run dev -- --port "$web_port") &
web_pid=$!
wait_url "http://127.0.0.1:$web_port/" 60 "$web_pid" || { echo "UI did not start." >&2; exit 1; }

echo
echo "DelayLens is running:  http://127.0.0.1:$web_port   (API docs: http://127.0.0.1:$api_port/docs)"
echo "Press Ctrl+C here to stop everything."
if command -v open >/dev/null 2>&1; then open "http://127.0.0.1:$web_port"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:$web_port" >/dev/null 2>&1 || true
fi
wait "$web_pid"
