"""Graph and account read-only endpoints for MuleTrace (Phase 13).

Provides:
- GET /api/accounts/{account_id}: profile for UI side panel
- GET /api/graph/neighborhood: capped neighborhood around an account
- GET /api/memory/cases: past cases stored in the graph memory
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.api.models import SAFE_ID_PATTERN, ErrorResponse
from backend.db import get_graph
from backend import queries
from backend.memory import recall_past_cases

logger = logging.getLogger("muletrace.api.graph")

router = APIRouter(tags=["graph"])


@router.get(
    "/api/accounts/{account_id}",
    summary="Get account behavioral profile for UI side panel",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def get_account(account_id: str) -> Dict[str, Any]:
    """Return behavioural profile of an account including transaction aggregates,

    latency, cash-outs, devices, and phones with shared counts.
    """
    if not SAFE_ID_PATTERN.match(account_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid account_id format: '{account_id}'",
                "hint": "account_id must contain only alphanumeric characters, underscores, or hyphens.",
            },
        )

    g = get_graph()
    profile = queries.get_account_profile(g, account_id)
    if not profile or not profile.get("found"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"Account '{account_id}' not found.",
                "hint": "Verify the account ID exists in the graph database.",
            },
        )

    # Calculate shared device and phone counts
    devices = profile.get("devices", {}).get("items", [])
    phones = profile.get("phones", {}).get("items", [])

    shared_devices_count = sum(1 for d in devices if d.get("share_count", 1) > 1)
    shared_phones_count = sum(1 for p in phones if p.get("share_count", 1) > 1)

    result = dict(profile)
    result["shared_device_count"] = shared_devices_count
    result["shared_phone_count"] = shared_phones_count
    return result


@router.get(
    "/api/graph/neighborhood",
    summary="Get graph neighborhood around an account",
    responses={
        400: {"model": ErrorResponse},
    },
)
def get_neighborhood_api(
    account_id: str = Query(..., description="Target account ID"),
    hops: int = Query(2, ge=1, le=3, description="Expansion hops (max 3)"),
    limit: int = Query(60, ge=1, le=150, description="Node count limit (max 150)"),
) -> Dict[str, Any]:
    """Wraps queries.get_neighborhood with strict safety caps (hops <= 3, limit <= 150)."""
    if not SAFE_ID_PATTERN.match(account_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid account_id format: '{account_id}'",
                "hint": "account_id must contain only alphanumeric characters, underscores, or hyphens.",
            },
        )

    if hops > 3 or hops < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Hops '{hops}' out of bounds.",
                "hint": "hops parameter must be between 1 and 3.",
            },
        )

    if limit > 150 or limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Limit '{limit}' out of bounds.",
                "hint": "limit parameter must be between 1 and 150.",
            },
        )

    g = get_graph()
    return queries.get_neighborhood(g, account_id, hops=hops, limit=limit)


@router.get(
    "/api/memory/cases",
    summary="List past cases stored in graph memory",
)
def get_memory_cases(
    account_id: Optional[str] = Query(None, description="Optional account ID filter"),
) -> Dict[str, Any]:
    """Retrieve past case intelligence from graph memory."""
    g = get_graph()

    if account_id:
        if not SAFE_ID_PATTERN.match(account_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid account_id format: '{account_id}'",
                    "hint": "account_id must contain only alphanumeric characters, underscores, or hyphens.",
                },
            )
        recalled = recall_past_cases(g, [account_id])
        return recalled

    # Return all cases stored in graph memory
    rows = queries._rows(
        g,
        "MATCH (c:Case) "
        "OPTIONAL MATCH (c)-[:INVOLVES]->(a:Account) "
        "OPTIONAL MATCH (c)-[:LINKED_TO]->(p:Case) "
        "RETURN c.id, c.report_id, c.created_at, c.summary, c.status, "
        "       collect(DISTINCT a.id), collect(DISTINCT p.id) "
        "ORDER BY c.created_at DESC",
    )

    cases = []
    for cid, rep_id, created, summary, case_status, accounts, linked in rows:
        clean_accounts = [a for a in accounts if a]
        clean_linked = [p for p in linked if p]
        cases.append({
            "case_id": cid,
            "report_id": rep_id,
            "created_at": created,
            "summary": summary,
            "status": case_status,
            "accounts": clean_accounts,
            "linked_cases": clean_linked,
        })

    return {"total": len(cases), "cases": cases}
