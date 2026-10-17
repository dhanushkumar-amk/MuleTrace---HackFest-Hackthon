#!/usr/bin/env bash
# MuleTrace Development Environment Startup Script (Linux/macOS)
set -e

echo "========================================================"
echo "Starting MuleTrace Development Environment"
echo "========================================================"

# 1. Start Docker containers (FalkorDB)
echo "[1/3] Starting FalkorDB container via docker compose..."
docker compose up -d

# 2. Check if graph has nodes, load if empty
echo "[2/3] Checking FalkorDB graph state..."
python3 -c "
from backend.db import get_graph
import sys
try:
    g = get_graph()
    res = g.query('MATCH (n) RETURN count(n)').result_set
    count = res[0][0] if res else 0
    print(f'Node count: {count}')
    sys.exit(0 if count > 0 else 1)
except Exception:
    sys.exit(1)
" || {
    echo "Graph is empty or uninitialized. Loading dataset..."
    python3 scripts/load_graph.py
}

# 3. Print URLs and start API server
echo "========================================================"
echo "MuleTrace Services Available:"
echo "  - Backend API:       http://localhost:8000"
echo "  - Interactive Docs:  http://localhost:8000/docs"
echo "  - Health Check:      http://localhost:8000/health"
echo "  - FalkorDB Browser:  http://localhost:3000"
echo "========================================================"
echo "[3/3] Starting uvicorn development server on port 8000..."
exec uvicorn backend.main:app --reload --port 8000
