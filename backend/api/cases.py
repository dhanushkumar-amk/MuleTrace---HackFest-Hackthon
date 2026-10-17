"""Case management, investigation triggering, and SSE event streaming endpoints for MuleTrace (Phase 13)."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from backend.api.models import (
    InvestigationStartRequest,
    InvestigationStartResponse,
    InvestigationStatusResponse,
    CaseSummaryItem,
    ErrorResponse,
)
from backend.api.sessions import session_manager, validate_safe_id
from backend.explain import (
    explain_case,
    load_case_explanation,
    list_case_explanations,
    build_graph_highlight,
)
from backend.explain_text import to_markdown, to_plain_text

router = APIRouter(prefix="/api", tags=["Investigations & Cases"])


@router.post(
    "/investigations",
    status_code=202,
    response_model=InvestigationStartResponse,
    summary="Start an autonomous fraud investigation",
    responses={
        429: {"model": ErrorResponse, "description": "Too Many Requests / Concurrent Run Limit Exceeded"},
        400: {"model": ErrorResponse, "description": "Invalid Request Parameters"},
    },
)
async def start_investigation(req: InvestigationStartRequest) -> Dict[str, Any]:
    """Start an investigation in the background.

    Runs either in live agent mode or demo replay mode depending on parameters and environment.
    Returns HTTP 202 immediately with the assigned session_id.
    """
    report_id = req.report_id or "FR_0001"
    validate_safe_id(report_id, "report_id")

    session = await session_manager.start_investigation(
        report_id=report_id,
        task=req.task,
        save_memory=req.save_memory,
        polish=req.polish,
        requested_mode=req.mode,
        speed=req.speed,
    )

    return {
        "session_id": session.session_id,
        "status": session.status,
        "mode": session.mode,
        "replay": session.replay,
        "fallback_available": session.fallback_available,
    }


@router.get(
    "/investigations/{session_id}/events",
    summary="Stream live investigation events via Server-Sent Events (SSE)",
    responses={404: {"model": ErrorResponse}},
)
async def stream_investigation_events(
    session_id: str,
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    last_id_param: Optional[str] = Query(None, alias="last_event_id"),
):
    """Server-Sent Events (SSE) event stream for an active or past investigation.

    Delivers compact events: thought, tool_call, tool_result, final, error, done.
    Buffers history so late subscribers get past events.
    Supports reconnection via Last-Event-ID header or query parameter without duplicates.
    Emits heartbeat comments every 15 seconds to prevent client timeout.
    """
    validate_safe_id(session_id, "session_id")
    sess = session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Investigation session '{session_id}' not found.",
                "hint": "Verify session ID or start a new investigation via POST /api/investigations.",
            },
        )

    effective_last_id = last_event_id or last_id_param

    async def event_generator() -> AsyncGenerator[str, None]:
        sent_ids = set()
        start_index = 0

        # Determine catch-up start index if client reconnected with Last-Event-ID
        if effective_last_id and effective_last_id.startswith("ev_"):
            try:
                start_index = int(effective_last_id.split("_")[1])
            except Exception:
                start_index = 0

        # 1. Flush buffered events up to current point
        buffered_snapshot = list(sess.events)
        for ev in buffered_snapshot[start_index:]:
            sent_ids.add(ev["id"])
            data_json = json.dumps(ev["data"])
            yield f"id: {ev['id']}\nevent: {ev['event']}\ndata: {data_json}\n\n"

        # 2. If session already finished, send done if not sent, then close
        if sess.status in ("done", "error", "cancelled"):
            if not any(ev["event"] == "done" for ev in buffered_snapshot[start_index:]):
                ev_id = f"ev_{len(sess.events) + 1}"
                yield f"id: {ev_id}\nevent: done\ndata: {json.dumps({'session_id': session_id})}\n\n"
            return

        # 3. Subscribe to live stream with heartbeat
        q = sess.subscribe()
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                    if ev["id"] not in sent_ids:
                        sent_ids.add(ev["id"])
                        data_json = json.dumps(ev["data"])
                        yield f"id: {ev['id']}\nevent: {ev['event']}\ndata: {data_json}\n\n"
                    if ev["event"] == "done":
                        break
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": heartbeat\n\n"
                    if sess.status in ("done", "error", "cancelled"):
                        break
        finally:
            sess.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/investigations/{session_id}",
    response_model=InvestigationStatusResponse,
    summary="Get investigation status and full case explanation",
    responses={404: {"model": ErrorResponse}},
)
def get_investigation_status(session_id: str) -> Dict[str, Any]:
    """Return status and full explanation object when completed."""
    validate_safe_id(session_id, "session_id")
    sess = session_manager.get_session(session_id)

    # If session is active in memory
    if sess:
        case_data = sess.explanation
        if not case_data and sess.status == "done":
            case_data = load_case_explanation(session_id) or explain_case(session_id)

        is_verified = bool(case_data.get("verified", False)) if case_data else False
        return {
            "session_id": sess.session_id,
            "status": sess.status,
            "mode": sess.mode,
            "replay": sess.replay,
            "verified": is_verified,
            "case": case_data,
            "explanation": case_data,
            "error": sess.error,
            "fallback_available": sess.fallback_available,
            "disclaimer": "recommendation for human review, nothing was frozen",
        }

    # Otherwise check if persisted to disk
    persisted = load_case_explanation(session_id)
    if persisted:
        is_verified = bool(persisted.get("verified", False))
        return {
            "session_id": session_id,
            "status": "done",
            "mode": persisted.get("mode", "live"),
            "replay": persisted.get("replay", False),
            "verified": is_verified,
            "case": persisted,
            "explanation": persisted,
            "error": None,
            "fallback_available": False,
            "disclaimer": "recommendation for human review, nothing was frozen",
        }

    raise HTTPException(
        status_code=404,
        detail={
            "error": f"Investigation session '{session_id}' not found.",
            "hint": "Check session ID formatting or list saved cases via GET /api/cases.",
        },
    )


@router.post(
    "/investigations/{session_id}/cancel",
    summary="Cancel an active investigation",
    responses={404: {"model": ErrorResponse}},
)
def cancel_investigation(session_id: str) -> Dict[str, Any]:
    """Cancel an in-progress investigation."""
    validate_safe_id(session_id, "session_id")
    cancelled = session_manager.cancel_session(session_id)
    if not cancelled:
        sess = session_manager.get_session(session_id)
        if sess and sess.status != "running":
            return {"status": "ok", "message": f"Session was already in status '{sess.status}'."}
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"No active investigation found for '{session_id}'.",
                "hint": "Session may have already finished or does not exist.",
            },
        )
    return {"status": "ok", "message": f"Investigation '{session_id}' cancelled."}


@router.get("/cases", response_model=List[CaseSummaryItem], summary="List persisted case explanations")
def get_cases() -> List[Dict[str, Any]]:
    """List all saved case summaries from disk."""
    items = list_case_explanations()
    res = []
    for it in items:
        ts = it.get("created_at") or it.get("timestamp") or 0
        tot = it.get("recoverable_total") if "recoverable_total" in it else it.get("total_recoverable", 0)
        res.append({
            "session_id": it.get("session_id", ""),
            "report_id": it.get("report_id", ""),
            "case_id": it.get("case_id", ""),
            "victim_name": it.get("victim_name", ""),
            "total_recoverable": tot,
            "recoverable_total": tot,
            "verified": it.get("verified", False),
            "created_at": ts,
            "timestamp": ts,
            "status": it.get("status", "COMPLETED"),
            "file": it.get("file", ""),
        })
    return res


@router.get(
    "/cases/{session_id}",
    summary="Retrieve full case explanation (JSON, Markdown, or Plain Text)",
    responses={404: {"model": ErrorResponse}},
)
def get_case_detail(
    session_id: str,
    format: Optional[str] = Query(None, description="Output format: 'json', 'markdown', or 'text'"),
):
    """Retrieve full case explanation by session ID."""
    validate_safe_id(session_id, "session_id")

    expl = load_case_explanation(session_id)
    if not expl:
        try:
            expl = explain_case(session_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"Case explanation '{session_id}' was not found.",
                    "hint": "Verify session ID or list available cases via GET /api/cases.",
                },
            )

    fmt = (format or "json").lower()
    if fmt == "markdown":
        md_text = to_markdown(expl)
        return Response(content=md_text, media_type="text/markdown; charset=utf-8")
    elif fmt == "text":
        plain_text = to_plain_text(expl)
        return Response(content=plain_text, media_type="text/plain; charset=utf-8")

    return expl


@router.get(
    "/cases/{session_id}/highlight",
    summary="Retrieve graph highlight subgraph with hop-by-hop animation sequence",
    responses={404: {"model": ErrorResponse}},
)
def get_case_highlight(session_id: str) -> Dict[str, Any]:
    """Retrieve graph highlight with sequence order for UI animation."""
    validate_safe_id(session_id, "session_id")

    expl = load_case_explanation(session_id)
    if expl and "highlight" in expl:
        return expl["highlight"]

    try:
        from backend.db import get_graph
        g = get_graph()
        return build_graph_highlight(session_id, graph=g)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Could not build highlight for '{session_id}': {str(exc)}",
                "hint": "Verify session ID and graph connection.",
            },
        )
