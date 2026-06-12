#!/bin/bash

# Tempo Project Launch Script
# This script starts the backend, worker, and frontend.

# Configuration
PROJECT_ROOT=$(pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV="$BACKEND_DIR/.venv"
LOG_DIR="$PROJECT_ROOT/logs"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Tempo...${NC}"

# 1. Create logs directory
mkdir -p "$LOG_DIR"

# 2. Check for .env file
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo -e "${RED}❌ Error: backend/.env file not found.${NC}"
    echo "Please create it based on backend/.env.example"
    exit 1
fi

# Load environment variables for the script's use (e.g., to check Docker)
export $(grep -v '^#' "$BACKEND_DIR/.env" | xargs)

# 3. Check if Docker services are running
echo -e "${BLUE}🐳 Checking Docker dependencies...${NC}"
if ! docker ps | grep -q "tempo-postgres-1"; then
    echo -e "${RED}❌ Postgres container is not running.${NC}"
    echo "Run 'docker-compose up -d' first."
    exit 1
fi

if ! docker ps | grep -q "tempo-redis-1"; then
    echo -e "${RED}❌ Redis container is not running.${NC}"
    echo "Run 'docker-compose up -d' first."
    exit 1
fi
echo -e "${GREEN}✅ Docker services OK.${NC}"

# 4. Stop existing processes
echo -e "${BLUE}🛑 Cleaning up old processes...${NC}"
pkill -f "uvicorn" || true
pkill -f "run_worker.py" || true
pkill -f "vite" || true
sleep 2

# Force kill if still alive
if lsof -i :8000 > /dev/null; then
    echo -e "${RED}⚠️ Port 8000 still in use, force killing...${NC}"
    lsof -ti :8000 | xargs kill -9 || true
    sleep 1
fi

if lsof -i :5173 > /dev/null; then
    lsof -ti :5173 | xargs kill -9 || true
    sleep 1
fi

# 5. Start Worker
echo -e "${BLUE}👷 Starting Background Worker...${NC}"
cd "$BACKEND_DIR"
PYTHONPATH=. "$VENV/bin/python" run_worker.py > "$LOG_DIR/worker.log" 2>&1 &
echo -e "${GREEN}✅ Worker started (Logs: logs/worker.log)${NC}"

# 6. Start Backend
echo -e "${BLUE}🐍 Starting FastAPI Backend...${NC}"
"$VENV/bin/uvicorn" app.main:app --reload --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
echo -e "${GREEN}✅ Backend started on http://localhost:8000 (Logs: logs/backend.log)${NC}"

# 7. Start Frontend
echo -e "${BLUE}⚛️ Starting Vite Frontend...${NC}"
cd "$FRONTEND_DIR"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
echo -e "${GREEN}✅ Frontend starting... (Logs: logs/frontend.log)${NC}"

echo -e "\n${GREEN}✨ Tempo is launching!${NC}"
echo -e "Frontend: ${BLUE}http://localhost:5173${NC}"
echo -e "Backend:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "\nTo stop everything, run: ${RED}pkill -f \"uvicorn|run_worker|vite\"${NC}"
