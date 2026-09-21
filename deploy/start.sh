#!/usr/bin/env bash
# ------------------------------------------------------------
# Jaguar AI — container entrypoint.
# Boots both the Flask GUI (gunicorn) and the FastAPI mobile API
# (uvicorn) inside the same container, forwarding SIGTERM so both
# shut down cleanly. Either can be disabled by setting the matching
# *_DISABLE flag to 1.
# ------------------------------------------------------------
set -euo pipefail

PORT="${PORT:-5000}"
API_PORT="${API_PORT:-8000}"
WORKERS="${WORKERS:-2}"
API_WORKERS="${API_WORKERS:-2}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "[jaguar] starting Flask GUI on 0.0.0.0:${PORT} (workers=${WORKERS})"
echo "[jaguar] starting FastAPI mobile API on 0.0.0.0:${API_PORT} (workers=${API_WORKERS})"

PIDS=()
shutdown() {
  echo "[jaguar] received signal, shutting down..."
  for pid in "${PIDS[@]:-}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap shutdown SIGTERM SIGINT

# Flask GUI behind gunicorn (production WSGI server).
gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --threads 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level "${LOG_LEVEL}" \
  wsgi:app &
PIDS+=($!)

# FastAPI mobile API behind uvicorn.
uvicorn \
  --host 0.0.0.0 \
  --port "${API_PORT}" \
  --workers "${API_WORKERS}" \
  --log-level "${LOG_LEVEL}" \
  api.mobile_api:app &
PIDS+=($!)

# Wait for either child to exit; if one dies, shut the other down too.
wait -n "${PIDS[@]}"
echo "[jaguar] a child process exited, tearing down..."
shutdown
