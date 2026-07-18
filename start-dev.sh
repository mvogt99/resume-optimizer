#!/usr/bin/env bash
# Start resume-optimizer dev environment (CLOUDLIFT_ENV=local)
# Backend :5000, Frontend :3000

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load ZOHO/SMTP credentials from .zshrc if available
source ~/.zshrc 2>/dev/null || true

echo "[dev] starting backend on :5000..."
cd "$SCRIPT_DIR/backend"
FLASK_APP=app.py FLASK_DEBUG=0 \
CLOUDLIFT_ENV=local \
DATABASE_URL=${DATABASE_URL:-postgresql://ro_user:ro_pass@localhost:15432/ro_test} \
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
APP_URL=http://localhost:5000 \
FRONTEND_URL=http://localhost:3000 \
APP_ENV_NAME=Development \
USER_TABLE=users \
ZOHO_IMAP_OUT_SERVER=${ZOHO_IMAP_OUT_SERVER:-smtppro.zoho.com} \
ZOHO_IMAP_OUT_PORT=${ZOHO_IMAP_OUT_PORT:-465} \
ZOHO_USERNAME=${ZOHO_USERNAME:-contact@concurrentonline.ai} \
ZOHO_PASSWORD=${ZOHO_PASSWORD} \
SMTP_PASSWORD=${SMTP_PASSWORD} \
PYTHONPATH=. \
flask run --host 0.0.0.0 --port 5000 &
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
