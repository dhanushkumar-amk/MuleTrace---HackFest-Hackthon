"""Tool execution tracing module for MuleTrace.

Logs every tool invocation to an in-memory session buffer and writes JSONL records
to data/runtime/tool_calls.jsonl for explainability and auditing (Phase 12).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ACTIVE_SESSION: str = "default"
_TRACES: Dict[str, List[Dict[str, Any]]] = {}

# Locate repository root safely from backend/tools/trace.py
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACE_FILE = REPO_ROOT / "data" / "runtime" / "tool_calls.jsonl"


def start(session_id: str) -> None:
    """Initialize or reset an active trace session."""
    global _ACTIVE_SESSION
    _ACTIVE_SESSION = session_id
    _TRACES[session_id] = []


def get(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all recorded trace events for a session, loading from disk if needed."""
    sid = session_id or _ACTIVE_SESSION
    if sid in _TRACES and _TRACES[sid]:
        for idx, ev in enumerate(_TRACES[sid], start=1):
            if "call_id" not in ev or not ev["call_id"]:
                ev["call_id"] = f"call_{idx:03d}"
        return list(_TRACES.get(sid, []))

    if TRACE_FILE.exists():
        loaded = []
        try:
            with open(TRACE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("session_id") == sid:
                        loaded.append(rec)
            if loaded:
                for idx, ev in enumerate(loaded, start=1):
                    if "call_id" not in ev or not ev["call_id"]:
                        ev["call_id"] = f"call_{idx:03d}"
                _TRACES[sid] = loaded
                return list(loaded)
        except Exception:
            pass

    return list(_TRACES.get(sid, []))


def list_sessions() -> List[str]:
    """Return all active session IDs in memory and disk."""
    sids = set(_TRACES.keys())
    if TRACE_FILE.exists():
        try:
            with open(TRACE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if "session_id" in rec:
                        sids.add(rec["session_id"])
        except Exception:
            pass
    return sorted(sids)


def clear() -> None:
    """Clear all in-memory traces."""
    global _ACTIVE_SESSION
    _ACTIVE_SESSION = "default"
    _TRACES.clear()


def record(
    tool_name: str,
    arguments: Dict[str, Any],
    duration_ms: float,
    result_size: int,
    ok: bool,
    path: Optional[Any] = None,
    error: Optional[str] = None,
    session_id: Optional[str] = None,
    call_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a tool call event to in-memory trace and append to data/runtime/tool_calls.jsonl."""
    sid = session_id or _ACTIVE_SESSION
    if sid not in _TRACES:
        _TRACES[sid] = []

    cid = call_id or f"call_{len(_TRACES[sid]) + 1:03d}"

    event: Dict[str, Any] = {
        "call_id": cid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": sid,
        "tool_name": tool_name,
        "arguments": arguments,
        "duration_ms": round(float(duration_ms), 2),
        "result_size": int(result_size),
        "ok": bool(ok),
        "path": path,
        "error": error,
    }

    _TRACES[sid].append(event)

    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        # Trace file failure must never crash tool execution
        pass

    return event
