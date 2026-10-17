"""In-memory session manager, event streaming, and replay engine for MuleTrace (Phase 13).

Manages active investigations, Server-Sent Events (SSE) event buffers,
concurrency limits, timeouts, cancellation, and demo replay mode.
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_FILE = REPO_ROOT / "data" / "demo" / "ravi_run.json"
CASES_DIR = REPO_ROOT / "data" / "runtime" / "cases"

SAFE_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]+$")


def validate_safe_id(val: str, field_name: str = "id") -> str:
    """Validate that an ID string is safe against path traversal and injection."""
    if not val or not SAFE_ID_REGEX.match(val) or ".." in val or "/" in val or "\\" in val:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Invalid {field_name} format.",
                "hint": "Identifiers must only contain alphanumeric characters, underscores, and hyphens.",
            },
        )
    return val


class SessionState:
    """State tracking for a single investigation run."""

    def __init__(self, session_id: str, report_id: str, mode: str = "live"):
        self.session_id = session_id
        self.report_id = report_id
        self.status = "running"  # running | done | error | cancelled
        self.mode = mode  # live | replay
        self.replay = (mode == "replay")
        self.started_at = time.time()
        self.events: List[Dict[str, Any]] = []
        self.subscribers: List[asyncio.Queue] = []
        self.task: Optional[asyncio.Task] = None
        self.explanation: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.fallback_available: bool = DEMO_FILE.exists()

    def add_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Record an event in the session buffer and notify active subscribers."""
        ev_id = f"ev_{len(self.events) + 1}"
        ev = {
            "id": ev_id,
            "event": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        self.events.append(ev)

        # Broadcast to active queues
        for q in list(self.subscribers):
            try:
                q.put_nowait(ev)
            except Exception:
                pass
        return ev

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)


class SessionManager:
    """Coordinates investigation sessions, concurrency control, and rate limits."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._request_timestamps: collections.deque = collections.deque()
        self._lock = asyncio.Lock()

    def get_max_concurrent_runs(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_RUNS", "1"))

    def get_timeout_seconds(self) -> float:
        return float(os.getenv("INVESTIGATION_TIMEOUT_SECONDS", "90.0"))

    def get_demo_mode_default(self) -> str:
        return os.getenv("DEMO_MODE", "live").lower()

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[SessionState]:
        return list(self._sessions.values())

    def cleanup_old_sessions(self, max_age_seconds: float = 3600.0) -> None:
        """Remove finished sessions older than 1 hour from memory (disk cases preserved)."""
        now = time.time()
        to_del = []
        for sid, sess in self._sessions.items():
            if sess.status in ("done", "error", "cancelled") and (now - sess.started_at) > max_age_seconds:
                to_del.append(sid)
        for sid in to_del:
            self._sessions.pop(sid, None)

    def create_session(self, session_id: str, report_id: str = "FR_0001", mode: str = "live") -> SessionState:
        """Create and register an in-memory session object (useful for tests and manual setups)."""
        sess = SessionState(session_id, report_id, mode=mode)
        self._sessions[session_id] = sess
        return sess

    def remove_session(self, session_id: str) -> None:
        """Explicitly remove a session from active memory."""
        self._sessions.pop(session_id, None)

    async def start_investigation(
        self,
        report_id: str = "FR_0001",
        task: Optional[str] = None,
        save_memory: bool = False,
        polish: bool = False,
        requested_mode: Optional[str] = None,
        speed: float = 1.0,
    ) -> SessionState:
        """Start a new investigation session with strict concurrency and rate limit checks."""
        async with self._lock:
            self.cleanup_old_sessions()
            now = time.time()

            # 1. Rate limiting: max 10 start requests per minute
            while self._request_timestamps and now - self._request_timestamps[0] > 60.0:
                self._request_timestamps.popleft()

            if len(self._request_timestamps) >= 10:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded (maximum 10 investigations per minute).",
                        "hint": "Please wait before submitting a new investigation.",
                    },
                )
            self._request_timestamps.append(now)

            # 2. Concurrency limit check
            running_sessions = [s for s in self._sessions.values() if s.status == "running"]
            max_concurrent = self.get_max_concurrent_runs()
            if len(running_sessions) >= max_concurrent:
                active_sid = running_sessions[0].session_id
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Maximum concurrent investigations limit reached.",
                        "hint": f"Wait for active investigation '{active_sid}' to complete or cancel it.",
                        "active_session_id": active_sid,
                    },
                )

            # 3. Determine live vs replay mode
            mode = requested_mode or self.get_demo_mode_default()
            if mode not in ("live", "replay"):
                mode = "live"

            # In replay mode, verify demo file exists
            if mode == "replay" and not DEMO_FILE.exists():
                mode = "live"

            session_id = f"session_{int(now * 1000)}"
            session = SessionState(session_id=session_id, report_id=report_id, mode=mode)
            self._sessions[session_id] = session

            # 4. Launch background execution task
            if mode == "replay":
                session.task = asyncio.create_task(
                    self._run_replay(session, speed=speed)
                )
            else:
                session.task = asyncio.create_task(
                    self._run_live(session, task or report_id, save_memory=save_memory, polish=polish)
                )

            return session

    async def _run_replay(self, session: SessionState, speed: float = 1.0) -> None:
        """Replay pre-recorded session events with realistic delays."""
        try:
            if not DEMO_FILE.exists():
                raise FileNotFoundError("Demo recording data/demo/ravi_run.json does not exist.")

            with open(DEMO_FILE, "r", encoding="utf-8") as f:
                demo_data = json.load(f)

            events = demo_data.get("events", [])
            for ev in events:
                if session.status == "cancelled":
                    break

                ev_type = ev.get("type") or ev.get("event", "message")
                ev_data = ev.get("data") or ev

                # Calculate realistic delay
                dur_ms = ev_data.get("duration_ms", 100)
                if speed > 0:
                    delay = (dur_ms / 1000.0) / speed
                    await asyncio.sleep(min(delay, 2.0))

                session.add_event(ev_type, ev_data)

            # Attach recorded explanation
            saved_expl = demo_data.get("explanation")
            if saved_expl:
                session.explanation = saved_expl
                session.explanation["session_id"] = session.session_id
                session.explanation["mode"] = "replay"
                session.explanation["replay"] = True

                from backend.explain import save_case_explanation
                save_case_explanation(session.explanation, session.session_id)

            session.status = "done"
        except asyncio.CancelledError:
            session.status = "cancelled"
            session.add_event("error", {"message": "Replay investigation cancelled."})
            session.add_event("done", {"session_id": session.session_id})
        except Exception as exc:
            session.status = "error"
            session.error = str(exc)
            session.add_event("error", {"message": f"Replay error: {str(exc)}"})
            session.add_event("done", {"session_id": session.session_id})

    async def _run_live(
        self,
        session: SessionState,
        query_or_report_id: str,
        save_memory: bool = False,
        polish: bool = False,
    ) -> None:
        """Execute real autonomous agent with timeout and error capture."""
        timeout_sec = self.get_timeout_seconds()
        try:
            from backend.agent import InvestigationAgent
            agent = InvestigationAgent(
                query_or_report_id=query_or_report_id,
                session_id=session.session_id,
                save_memory=save_memory,
                polish=polish,
            )

            async def _stream_loop():
                async for ev in agent.run_stream():
                    if session.status == "cancelled":
                        break
                    ev_type = ev.get("type", "message")
                    session.add_event(ev_type, ev)

            # Apply hard timeout
            await asyncio.wait_for(_stream_loop(), timeout=timeout_sec)

            # Load generated explanation from disk or explain_case
            from backend.explain import load_case_explanation, explain_case
            expl = load_case_explanation(session.session_id) or explain_case(session.session_id)
            expl["mode"] = "live"
            expl["replay"] = False
            session.explanation = expl
            session.status = "done"

        except asyncio.CancelledError:
            session.status = "cancelled"
            session.add_event("error", {"message": "Investigation cancelled by user."})
            session.add_event("done", {"session_id": session.session_id})
        except asyncio.TimeoutError:
            session.status = "error"
            session.error = f"Investigation timed out after {timeout_sec} seconds."
            session.fallback_available = DEMO_FILE.exists()
            session.add_event("error", {
                "message": session.error,
                "fallback_available": session.fallback_available,
            })
            session.add_event("done", {"session_id": session.session_id})
        except Exception as exc:
            session.status = "error"
            session.error = str(exc)
            session.fallback_available = DEMO_FILE.exists()
            session.add_event("error", {
                "message": f"Live investigation error: {str(exc)}",
                "fallback_available": session.fallback_available,
            })
            session.add_event("done", {"session_id": session.session_id})

    def cancel_session(self, session_id: str) -> bool:
        """Cancel an in-progress investigation session."""
        session = self._sessions.get(session_id)
        if not session or session.status != "running":
            return False

        if session.task and not session.task.done():
            session.task.cancel()
        session.status = "cancelled"
        return True


# Global session manager instance
session_manager = SessionManager()
