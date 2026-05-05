#!/usr/bin/env bash
# Start legacy resume-optimizer (pre-Phase-1) on ports 3010 (frontend) / 5010 (backend)
# Requires: hybrid-arangodb, hybrid-qdrant, hybrid-artemis containers running

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load ZOHO/SMTP credentials from .zshrc if available
source ~/.zshrc 2>/dev/null || true

echo "[legacy] starting backend on :5010..."
cd "$SCRIPT_DIR/backend"
FLASK_APP=app.py FLASK_DEBUG=0 \
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
APP_URL=http://localhost:5010 \
FRONTEND_URL=http://localhost:3010 \
APP_ENV_NAME=Legacy \
USER_TABLE=users \
ZOHO_IMAP_OUT_SERVER=${ZOHO_IMAP_OUT_SERVER:-smtppro.zoho.com} \
ZOHO_IMAP_OUT_PORT=${ZOHO_IMAP_OUT_PORT:-465} \
ZOHO_USERNAME=${ZOHO_USERNAME:-contact@concurrentonline.ai} \
ZOHO_PASSWORD=${ZOHO_PASSWORD} \
SMTP_PASSWORD=${SMTP_PASSWORD} \
PYTHONPATH=. \
flask run --host 0.0.0.0 --port 5010 &
BACKEND_PID=$!
echo "[legacy] backend PID $BACKEND_PID"

echo "[legacy] starting frontend on :3010..."
cd "$SCRIPT_DIR/frontend"
npm install --silent 2>/dev/null
VITE_API_URL=/api VITE_CLOUDLIFT_ENV=legacy npx vite --config vite.config.legacy.js &
FRONTEND_PID=$!
echo "[legacy] frontend PID $FRONTEND_PID"

echo ""
echo "  Legacy (pre-Phase-1): http://localhost:3010"
echo "  Press Ctrl-C to stop both processes."
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
