#!/bin/bash

echo "Starting MentorMind..."

source .venv/bin/activate

# Start backend in background, capture PID
python -m uvicorn backend.main:app --reload &
BACKEND_PID=$!

# Start frontend in background, capture PID
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Backend  → http://127.0.0.1:8000"
echo "✅ Frontend → http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both."

# Kill both on Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'; exit" INT
wait