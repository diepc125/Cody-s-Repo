#!/usr/bin/env bash
# Sentinel — start backend + frontend
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Sentinel..."

# Backend in background
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend in background
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Sentinel running:"
echo "  Backend  -> http://localhost:8000  (PID $BACKEND_PID)"
echo "  Frontend -> http://localhost:5173  (PID $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop both."

# Wait and forward Ctrl+C to both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
