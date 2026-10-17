"""System, reports, admin, and tool catalog endpoints for MuleTrace (Phase 13)."""
from __future__ import annotations

import os
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from backend.db import get_graph
from backend import queries
from backend.tools.registry import list_tools
from backend.api.models import ReportItem, ToolItem, ErrorResponse

router = APIRouter(prefix="/api", tags=["System & Catalog"])


@router.get("/reports", response_model=List[ReportItem], summary="List fraud reports")
def get_reports() -> List[Dict[str, Any]]:
    """List all filed fraud reports from FalkorDB."""
    g = get_graph()
    rows = queries._rows(
        g,
        "MATCH (fr:FraudReport) "
        "OPTIONAL MATCH (fr)-[:REPORTS_VICTIM]->(a:Account) "
        "RETURN fr.id, COALESCE(a.id, fr.victim_account_id), fr.amount, fr.reported_at, fr.description "
        "ORDER BY fr.reported_at DESC",
    )
    results = []
    for fid, aid, amt, rep_at, desc in rows:
        results.append({
            "id": fid,
            "victim_account": aid,
            "amount": int(amt) if amt is not None else 0,
            "reported_at": int(rep_at) if rep_at is not None else 0,
            "description": desc or "UPI Payment Fraud Incident",
        })
    return results


@router.get("/tools", response_model=List[ToolItem], summary="List available MCP tools")
def get_tools() -> List[Dict[str, Any]]:
    """List all graph exploration and verification tools available to the agent."""
    all_defs = list_tools()
    items = []
    for t in all_defs:
        short_desc = t.description
        if len(short_desc) > 140:
            short_desc = short_desc[:137] + "..."
        items.append({
            "name": t.name,
            "kind": str(t.kind),
            "short_description": short_desc,
        })
    return items


@router.post(
    "/admin/reset-memory",
    summary="Reset long-term graph memory (demo admin only)",
    responses={403: {"model": ErrorResponse}},
)
def post_reset_memory() -> Dict[str, Any]:
    """Reset long-term case memory in FalkorDB between demo takes.

    Requires environment variable DEMO_ADMIN=1.
    """
    demo_admin = os.getenv("DEMO_ADMIN", "0").lower()
    if demo_admin not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Admin access disabled.",
                "hint": "Set environment variable DEMO_ADMIN=1 to allow resetting memory between demo takes.",
            },
        )

    from backend.memory import reset_memory
    g = get_graph()
    res = reset_memory(g)
    return {"status": "ok", "message": res.get("message", "Memory reset complete.")}
