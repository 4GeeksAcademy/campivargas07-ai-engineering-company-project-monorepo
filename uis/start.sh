#!/bin/sh
# =============================================================================
#  Brasaland — Startup script for dual Next.js UIs (Website + Backoffice)
#  Website:    http://0.0.0.0:3000
#  Backoffice: http://0.0.0.0:3001
# =============================================================================

set -eu

echo "============================================="
echo "  Brasaland — Starting UIs (Website & Backoffice)"
echo "============================================="

cleanup() {
  echo ""
  echo "Shutting down UI processes..."
  if [ -n "${WEBSITE_PID:-}" ] && kill -0 "$WEBSITE_PID" 2>/dev/null; then
    kill -TERM "$WEBSITE_PID" 2>/dev/null || true
  fi
  if [ -n "${BACKOFFICE_PID:-}" ] && kill -0 "$BACKOFFICE_PID" 2>/dev/null; then
    kill -TERM "$BACKOFFICE_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  exit 0
}

trap cleanup INT TERM

# Determine paths (support /app/uis or fallback /app)
if [ -d "/app/uis/website" ]; then
  BASE_DIR="/app/uis"
else
  BASE_DIR="/app"
fi

# --- Start Website ---
echo "Starting Website on 0.0.0.0:3000..."
(
  cd "${BASE_DIR}/website"
  if [ -x ./node_modules/.bin/next ]; then
    exec ./node_modules/.bin/next dev --webpack -H 0.0.0.0 -p 3000
  else
    exec npx next dev --webpack -H 0.0.0.0 -p 3000
  fi
) &
WEBSITE_PID=$!
echo "  Website PID: $WEBSITE_PID"

# --- Start Backoffice ---
echo "Starting Backoffice on 0.0.0.0:3001..."
(
  cd "${BASE_DIR}/backoffice"
  if [ -x ./node_modules/.bin/next ]; then
    exec ./node_modules/.bin/next dev --webpack -H 0.0.0.0 -p 3001
  else
    exec npx next dev --webpack -H 0.0.0.0 -p 3001
  fi
) &
BACKOFFICE_PID=$!
echo "  Backoffice PID: $BACKOFFICE_PID"

echo "Both UIs started. Monitoring processes..."

# --- Monitor both processes ---
while true; do
  if ! kill -0 "$WEBSITE_PID" 2>/dev/null; then
    echo "Website process (PID $WEBSITE_PID) exited unexpectedly."
    cleanup
    exit 1
  fi
  if ! kill -0 "$BACKOFFICE_PID" 2>/dev/null; then
    echo "Backoffice process (PID $BACKOFFICE_PID) exited unexpectedly."
    cleanup
    exit 1
  fi
  sleep 1 &
  wait $! 2>/dev/null || true
done
