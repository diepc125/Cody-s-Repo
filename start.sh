#!/usr/bin/env bash
# Sentinel — pull latest, then start backend + frontend
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BRANCH="claude/trading-algorithm-McKTc"

cd "$ROOT"

echo "Sentinel"
echo "--------"
echo "Pulling latest from $BRANCH..."
if ! git pull origin "$BRANCH"; then
    echo "git pull failed. Resolve and re-run."
    exit 1
fi

echo "At commit: $(git log -1 --oneline)"
echo ""

# Backend
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Backend  -> http://localhost:8000 (PID $BACKEND_PID)"
echo "Frontend -> http://localhost:5173 (PID $FRONTEND_PID)"
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
