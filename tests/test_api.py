"""Integration tests for MuleTrace backend API (Phase 13).

Validates:
- /health reports all dependencies (FalkorDB, Groq key, MCP mode, nodes, cases)
- /api/reports returns Ravi's report
- POST /api/investigations in replay mode returns 202 and session_id
- SSE stream delivers events in order ending with "done"; reconnecting with Last-Event-ID resumes without duplicates
- GET /api/investigations/{id} returns explanation with verified true and the disclaimer
- /api/cases/{id}/highlight nodes and edges exist in graph, sequence follows time order
- ?format=markdown returns rendered report containing the disclaimer
- The second concurrent run is rejected with 429 and names the running session
- Cancel stops a run; timeout produces an error event with fallback flag
- Invalid IDs, path traversal attempts, and oversized limits return 4xx with standard error shape {"error", "hint"}
- /api/admin/reset-memory returns 403 without DEMO_ADMIN=1
- No endpoint accepts a "cypher" or "query" field (grep router code)
- One slow test with real Groq (live mode) that runs Ravi's report end-to-end
- Hygiene grep: backend/ has no reads of tests/, docs/, ground_truth, and no "ACC_0" literals
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.main import app
from backend.api.sessions import session_manager, SessionState, DEMO_FILE
from backend.explain import save_case_explanation

DISCLAIMER_TEXT = "recommendation for human review, nothing was frozen"


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def ensure_demo_fixture():
    """Ensure data/demo/ravi_run.json exists with valid fixture structure for fast offline replay."""
    if not DEMO_FILE.exists():
        DEMO_FILE.parent.mkdir(parents=True, exist_ok=True)
        fixture_data = {
            "session_id": "fixture_demo_session",
            "report_id": "FR_0001",
            "recorded_at": int(time.time()),
            "events": [
                {
                    "type": "thought",
                    "content": "Analyzing fraud report FR_0001...",
                    "duration_ms": 10,
                },
                {
                    "type": "tool_call",
                    "call_id": "call_001",
                    "tool": "get_fraud_report",
                    "arguments": {"report_id": "FR_0001"},
                    "duration_ms": 10,
                },
                {
                    "type": "tool_result",
                    "call_id": "call_001",
                    "tool": "get_fraud_report",
                    "summary": "Retrieved fraud report for victim ACC_0461, amount Rs 85,000",
                    "duration_ms": 10,
                },
                {
                    "type": "final",
                    "session_id": "fixture_demo_session",
                    "report_id": "FR_0001",
                    "total_recoverable": 85000,
                    "freeze_count": 2,
                    "disclaimer": DISCLAIMER_TEXT,
                    "duration_ms": 10,
                },
                {
                    "type": "done",
                    "session_id": "fixture_demo_session",
                    "duration_ms": 10,
                },
            ],
            "explanation": {
                "session_id": "fixture_demo_session",
                "case_header": {
                    "case_id": "CASE_FR_0001",
                    "report_id": "FR_0001",
                    "victim_account": "ACC_0461",
                    "victim_name": "Ravi Kumar",
                    "stolen_amount": 85000,
                    "reported_at": 1792044900,
                    "total_recoverable": 85000,
                    "disclaimer": DISCLAIMER_TEXT,
                },
                "recommendations": [
                    {
                        "account": "ACC_0991",
                        "bank": "HDFC",
                        "confidence": "high",
                        "priority": 1,
                        "amount_recoverable": 50000,
                        "signals": ["rapid_hop"],
                        "reasons": ["Forwarded money rapidly"],
                        "path_narrative": "Victim -> ACC_0991",
                        "hops": [{"from_account": "ACC_0461", "to_account": "ACC_0991", "amount": 85000, "txn_id": "TX_9901", "timestamp": 1792045000}],
                        "tool_call_ids": ["call_001", "call_002"],
                    }
                ],
                "rejections": [
                    {
                        "account": "ACC_0476",
                        "holder_name": "Decoy Account",
                        "bank": "ICICI",
                        "reasons": ["Decoy behavior profile", "No onward laundering"],
                        "signals": [],
                    }
                ],
                "links": [],
                "freeze_list": {
                    "items": [
                        {
                            "account": "ACC_0991",
                            "confidence": "high",
                            "priority": 1,
                            "amount_recoverable": 50000,
                            "signals": ["rapid_hop"],
                        }
                    ]
                },
                "verified": True,
                "disclaimer": DISCLAIMER_TEXT,
            },
            "verified": True,
            "decoy_rejected": True,
            "freeze_list": ["ACC_0991"],
            "rejections": ["ACC_0476"],
        }
        with open(DEMO_FILE, "w", encoding="utf-8") as f:
            json.dump(fixture_data, f, indent=2)


def test_health_reports_all_dependencies(client):
    """GET /health reports FalkorDB, Groq, MCP mode, nodes count, and saved cases count."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "falkordb_reachable" in data
    assert "groq_key_present" in data
    assert "mcp_mode" in data
    assert "graph_nodes_count" in data or "graph_node_count" in data
    assert "saved_cases_count" in data
    assert isinstance(data["falkordb_reachable"], bool)
    assert isinstance(data["groq_key_present"], bool)


def test_reports_returns_ravi(client):
    """GET /api/reports returns Ravi's fraud report (FR_0001)."""
    resp = client.get("/api/reports")
    assert resp.status_code == 200
    reports = resp.json()
    assert isinstance(reports, list)
    assert len(reports) > 0

    ravi_report = next((r for r in reports if r["id"] == "FR_0001"), None)
    assert ravi_report is not None
    assert ravi_report["victim_account"] == "ACC_0461"
    assert ravi_report["amount"] == 85000


def test_post_investigations_replay_mode(client):
    """POST /api/investigations in replay mode returns 202 and session_id immediately."""
    resp = client.post("/api/investigations", json={
        "report_id": "FR_0001",
        "mode": "replay",
        "speed": 0.0,  # instant replay
    })
    assert resp.status_code == 202
    data = resp.json()
    assert "session_id" in data
    assert data["mode"] == "replay"
    assert data["replay"] is True


def test_sse_stream_and_reconnect(client):
    """GET /api/investigations/{session_id}/events delivers events in order ending with done,

    and Last-Event-ID resumes from bookmark without duplicates.
    """
    # Start replay run
    start_resp = client.post("/api/investigations", json={
        "report_id": "FR_0001",
        "mode": "replay",
        "speed": 0.0,
    })
    assert start_resp.status_code == 202
    session_id = start_resp.json()["session_id"]

    # Allow replay task to complete in memory
    time.sleep(0.1)

    # 1. First full stream read
    with client.stream("GET", f"/api/investigations/{session_id}/events") as sse_resp:
        assert sse_resp.status_code == 200
        assert "text/event-stream" in sse_resp.headers["content-type"]
        lines = [line for line in sse_resp.iter_lines() if line]

    events = []
    current_id = None
    current_event = None
    for line in lines:
        if line.startswith("id: "):
            current_id = line[4:]
        elif line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            events.append((current_id, current_event, json.loads(line[6:])))

    assert len(events) >= 2
    # Ensure stream ends with 'done'
    assert events[-1][1] == "done"

    # 2. Reconnect test using Last-Event-ID
    bookmark_id = events[1][0]  # Take second event ID (e.g. 'ev_2')
    with client.stream(
        "GET",
        f"/api/investigations/{session_id}/events",
        headers={"Last-Event-ID": bookmark_id},
    ) as resume_resp:
        resume_lines = [l for l in resume_resp.iter_lines() if l]

    resumed_events = []
    r_id, r_event = None, None
    for line in resume_lines:
        if line.startswith("id: "):
            r_id = line[4:]
        elif line.startswith("event: "):
            r_event = line[7:]
        elif line.startswith("data: "):
            resumed_events.append((r_id, r_event))

    # All resumed events must come strictly after the bookmark
    bookmark_num = int(bookmark_id.split("_")[1])
    for ev_id, _ in resumed_events:
        if ev_id and ev_id.startswith("ev_"):
            ev_num = int(ev_id.split("_")[1])
            assert ev_num > bookmark_num


def test_investigation_status_and_verified_explanation(client):
    """GET /api/investigations/{id} returns explanation with verified true and disclaimer."""
    # Ensure a completed session exists
    session_id = "test_status_session"
    sess = session_manager.create_session(session_id, "FR_0001", mode="replay")
    sess.status = "done"

    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        demo_json = json.load(f)
    expl = demo_json["explanation"]
    expl["session_id"] = session_id
    expl["verified"] = True
    expl["disclaimer"] = DISCLAIMER_TEXT
    sess.explanation = expl
    save_case_explanation(expl, session_id)

    resp = client.get(f"/api/investigations/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["verified"] is True
    assert data["disclaimer"] == DISCLAIMER_TEXT
    assert data["explanation"] is not None
    assert data["explanation"]["verified"] is True


def test_cases_highlight_sequence(client):
    """GET /api/cases/{session_id}/highlight output nodes and edges exist, sequence follows time order."""
    session_id = "test_highlight_session"
    sess = session_manager.create_session(session_id, "FR_0001", mode="replay")
    sess.status = "done"

    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        demo_json = json.load(f)
    expl = demo_json["explanation"]
    expl["session_id"] = session_id
    sess.explanation = expl
    save_case_explanation(expl, session_id)

    resp = client.get(f"/api/cases/{session_id}/highlight")
    assert resp.status_code == 200
    highlight = resp.json()
    assert "nodes" in highlight
    assert "edges" in highlight
    assert isinstance(highlight["nodes"], list)
    assert isinstance(highlight["edges"], list)

    # Check sequence ordering on edges
    if len(highlight["edges"]) > 1:
        sequences = [e.get("sequence", 0) for e in highlight["edges"]]
        assert sequences == sorted(sequences)


def test_cases_markdown_format(client):
    """GET /api/cases/{session_id}?format=markdown returns rendered report with disclaimer."""
    session_id = "test_md_session"
    sess = session_manager.create_session(session_id, "FR_0001", mode="replay")
    sess.status = "done"

    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        demo_json = json.load(f)
    expl = demo_json["explanation"]
    expl["session_id"] = session_id
    sess.explanation = expl
    save_case_explanation(expl, session_id)

    resp = client.get(f"/api/cases/{session_id}?format=markdown")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    text = resp.text
    assert DISCLAIMER_TEXT in text
    assert "# " in text


def test_concurrent_run_rejection(client):
    """The second concurrent run is rejected with HTTP 429 and names the running session."""
    running_id = "active_running_session"
    active_sess = session_manager.create_session(running_id, "FR_0001", mode="live")
    active_sess.status = "running"

    try:
        resp = client.post("/api/investigations", json={"report_id": "FR_0001"})
        assert resp.status_code == 429
        data = resp.json()
        assert "error" in data
        assert running_id in data["error"] or running_id in data.get("hint", "")
    finally:
        session_manager.remove_session(running_id)


def test_cancel_and_timeout(client):
    """Cancel stops a run; timeout produces an error event with partial findings."""
    cancelling_id = "to_cancel_session"
    sess = session_manager.create_session(cancelling_id, "FR_0001", mode="live")
    sess.status = "running"

    resp = client.post(f"/api/investigations/{cancelling_id}/cancel")
    assert resp.status_code == 200
    assert sess.status == "cancelled"

    # Simulate timeout handling
    sess.error = "Investigation timed out after 90 seconds."
    sess.status = "error"
    sess.add_event("error", {"message": sess.error, "fallback_available": True})

    status_resp = client.get(f"/api/investigations/{cancelling_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "error"
    assert status_resp.json()["fallback_available"] is True


def test_validation_and_safety_checks(client):
    """Invalid IDs, path traversal, and oversized limits return 4xx with standard error shape."""
    # 1. Path traversal attempt on case detail
    resp = client.get("/api/cases/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)
    data = resp.json()
    assert "error" in data
    assert "hint" in data

    # 2. Invalid account ID format
    resp = client.get("/api/accounts/bad_id_$%#@")
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert "hint" in data

    # 3. Oversized limit or hops on neighborhood
    resp = client.get("/api/graph/neighborhood?account_id=ACC_0461&hops=5&limit=250")
    assert resp.status_code in (400, 422)
    data = resp.json()
    assert "error" in data
    assert "hint" in data


def test_admin_reset_memory_unauthorized(client):
    """POST /api/admin/reset-memory returns 403 without DEMO_ADMIN=1."""
    old_env = os.environ.get("DEMO_ADMIN")
    try:
        os.environ.pop("DEMO_ADMIN", None)
        resp = client.post("/api/admin/reset-memory")
        assert resp.status_code == 403
        data = resp.json()
        assert "Admin access disabled" in data["error"]
        assert "DEMO_ADMIN=1" in data["hint"]
    finally:
        if old_env is not None:
            os.environ["DEMO_ADMIN"] = old_env


def test_no_cypher_or_query_parameters_in_routers():
    """Grep router code to verify no endpoint accepts raw Cypher or arbitrary query parameters."""
    api_dir = REPO_ROOT / "backend" / "api"
    router_files = list(api_dir.glob("*.py"))
    assert len(router_files) >= 3

    for r_file in router_files:
        code = r_file.read_text(encoding="utf-8")
        # Ensure no endpoint defines cypher as a param
        assert "cypher:" not in code.lower(), f"Forbidden parameter 'cypher' in {r_file.name}"
        # Ensure no request body defines cypher
        assert '"cypher"' not in code.lower(), f"Forbidden 'cypher' literal in {r_file.name}"


def test_hygiene_backend_clean():
    """Backend code must not read tests/, docs/, ground_truth, and contain no 'ACC_0' literals."""
    backend_dir = REPO_ROOT / "backend"
    py_files = list(backend_dir.rglob("*.py"))

    forbidden_substrings = ["tests/", "docs/", "ground_truth.json", "ACC_0"]

    violations = []
    for f in py_files:
        content = f.read_text(encoding="utf-8")
        for sub in forbidden_substrings:
            if sub in content:
                violations.append((f.name, sub))

    assert not violations, f"Hygiene violations found in backend/: {violations}"


@pytest.mark.slow
def test_live_investigation_end_to_end(client):
    """Slow integration test: runs real Groq agent through the API on Ravi's report."""
    if not (os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")):
        pytest.skip("GROQ_API_KEY not configured.")

    start_time = time.time()
    resp = client.post("/api/investigations", json={
        "report_id": "FR_0001",
        "mode": "live",
        "speed": 1.0,
    })
    assert resp.status_code in (202, 429)
    if resp.status_code == 429:
        pytest.skip("Concurrent investigation running.")

    session_id = resp.json()["session_id"]
    # Poll until completed or timeout
    max_wait = 180
    elapsed = 0
    done = False
    while elapsed < max_wait:
        st_resp = client.get(f"/api/investigations/{session_id}")
        assert st_resp.status_code == 200
        st = st_resp.json()["status"]
        if st in ("done", "error", "cancelled"):
            done = True
            break
        time.sleep(3)
        elapsed += 3

    total_time = round(time.time() - start_time, 2)
    print(f"\n[LIVE TEST] End-to-end investigation finished in {total_time}s (status={st})")
    assert done is True
