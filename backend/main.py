"""MuleTrace backend FastAPI application (Phase 13).

Provides:
- GET /health: dependency health and system stats
- Routers:
  - backend/api/cases.py (investigations, cases, events, highlights)
  - backend/api/graph.py (accounts, neighborhood, memory cases)
  - backend/api/system.py (reports, tools, admin)
- CORS for http://localhost:5173 and http://127.0.0.1:5173
- Strict request validation, standard error responses, timing middleware.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.cases import router as cases_router
from backend.api.graph import router as graph_router
from backend.api.models import ErrorResponse, HealthResponse
from backend.api.system import router as system_router
from backend.db import get_graph
from backend.explain import list_case_explanations

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("muletrace.api")

app = FastAPI(
    title="MuleTrace API",
    version="0.1.0",
    description="Autonomous fraud ring investigation API powered by FalkorDB, MCP, and Groq.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middlewares: Access logging with timing & Request size limit
# ---------------------------------------------------------------------------
MAX_REQUEST_SIZE = 1_048_576  # 1 MB


@app.middleware("http")
async def security_and_timing_middleware(request: Request, call_next):
    # Enforce request content-length limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "error": "Request entity too large",
                "hint": f"Request body must not exceed {MAX_REQUEST_SIZE} bytes.",
            },
        )

    start_time = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Never log API keys, auth headers, or sensitive query strings
    safe_path = request.url.path
    logger.info("%s %s -> %s (%.2fms)", request.method, safe_path, response.status_code, duration_ms)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail),
            "hint": "Check request parameters and try again.",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_err = errors[0] if errors else {}
    loc = " -> ".join(str(l) for l in first_err.get("loc", []))
    msg = first_err.get("msg", "Invalid parameter")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": f"Validation error at '{loc}': {msg}",
            "hint": "Review the API schema at /docs to ensure all fields are properly formatted.",
        },
    )


# ---------------------------------------------------------------------------
# Dependency helpers for /health
# ---------------------------------------------------------------------------
def _falkordb_reachable() -> bool:
    """Return True if FalkorDB is reachable and the graph responds."""
    try:
        graph = get_graph()
        graph.query("RETURN 1")
        return True
    except Exception:
        return False


def _graph_node_count() -> int:
    """Return node count in FalkorDB if reachable."""
    try:
        graph = get_graph()
        res = graph.query("MATCH (n) RETURN count(n)").result_set
        if res and res[0]:
            return int(res[0][0])
        return 0
    except Exception:
        return 0


def _saved_cases_count() -> int:
    """Return count of saved cases in data/runtime/cases/."""
    try:
        return len(list_case_explanations())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health check reporting dependencies and graph status",
)
def health() -> Dict[str, Any]:
    falkor_ok = _falkordb_reachable()
    groq_present = bool(os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY"))
    mcp_mode = os.getenv("MCP_MODE", "in-process")
    node_count = _graph_node_count() if falkor_ok else 0
    cases_count = _saved_cases_count()
    status_str = "ok" if (falkor_ok and groq_present) else "degraded"

    return {
        "status": status_str,
        "falkordb_reachable": falkor_ok,
        "groq_key_present": groq_present,
        "mcp_mode": mcp_mode,
        "graph_node_count": node_count,
        "graph_nodes_count": node_count,
        "saved_cases_count": cases_count,
    }


# Include Routers
app.include_router(cases_router)
app.include_router(graph_router)
app.include_router(system_router)