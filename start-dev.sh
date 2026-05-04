#!/usr/bin/env bash
# Start resume-optimizer dev environment (CLOUDLIFT_ENV=local)
# Backend :5000, Frontend :3000

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[dev] starting backend on :5000..."
cd "$SCRIPT_DIR/backend"
CLOUDLIFT_ENV=local \
ARANGO_HOST=http://localhost:8529 \
ARANGO_DB=hybrid_ai \
ARANGO_USER=root \
ARANGO_PASSWORD=hybrid_ai_root \
ARANGO_ENABLED=true \
QDRANT_HOST=localhost \
QDRANT_PORT=6333 \
ARTEMIS_HOST=localhost \
ARTEMIS_PORT=61613 \
HARNESS_URL=http://localhost:8000/api/harness/run \
PF_URL=http://localhost:8090 \
PYTHONPATH=. \
gunicorn app:app \
  --workers 2 \
  --bind 0.0.0.0:5000 \
  --timeout 120 \
  --access-logfile - \
  --log-level warning &
BACKEND_PID=$!
echo "[dev] backend PID $BACKEND_PID"

echo "[dev] starting frontend on :3000..."
cd "$SCRIPT_DIR/frontend"
npx vite &
FRONTEND_PID=$!
echo "[dev] frontend PID $FRONTEND_PID"

echo ""
echo "  Dev (local services): http://localhost:3000"
echo "  Press Ctrl-C to stop both processes."
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
