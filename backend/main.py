"""MuleTrace backend API."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import get_graph

app = FastAPI(title="MuleTrace API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _falkordb_reachable() -> bool:
    """Return True if FalkorDB is reachable and the graph is usable."""
    try:
        graph = get_graph()
        graph.query("RETURN 1")
        return True
    except Exception:
        return False


@app.get("/health")
def health():
    return {"status": "ok", "falkordb_reachable": _falkordb_reachable()}