@echo off
REM MuleTrace Development Environment Startup Script (Windows)
echo ========================================================
echo Starting MuleTrace Development Environment
echo ========================================================

REM 1. Start Docker containers (FalkorDB)
echo [1/3] Starting FalkorDB container via docker compose...
docker compose up -d
if %ERRORLEVEL% neq 0 (
    echo WARNING: docker compose up failed. Please ensure Docker Desktop is running.
)

REM 2. Check if graph has nodes, load if empty
echo [2/3] Checking FalkorDB graph state...
python -c "from backend.db import get_graph; g = get_graph(); res = g.query('MATCH (n) RETURN count(n)').result_set; print('Node count:', res[0][0] if res else 0); import sys; sys.exit(0 if (res and res[0][0] > 0) else 1)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo Graph is empty or uninitialized. Loading dataset...
    python scripts/load_graph.py
) else (
    echo Graph is already populated with data.
)

REM 3. Print URLs and start API server
echo ========================================================
echo MuleTrace Services Available:
echo   - Backend API:       http://localhost:8000
echo   - Interactive Docs:  http://localhost:8000/docs
echo   - Health Check:      http://localhost:8000/health
echo   - FalkorDB Browser:  http://localhost:3000
echo ========================================================
echo [3/3] Starting uvicorn development server on port 8000...
uvicorn backend.main:app --reload --port 8000
