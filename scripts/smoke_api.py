"""Smoke test script for MuleTrace backend API (Phase 13).

Can be run against an active uvicorn server (http://localhost:8000) or
using FastAPI's in-process TestClient directly.
Prints PASS or FAIL for every core endpoint.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import httpx
from fastapi.testclient import TestClient
from backend.main import app


def run_smoke_tests(base_url: str = None):
    print("=" * 60)
    print("MuleTrace API Smoke Test Suite")
    print("=" * 60)

    client = None
    if base_url:
        print(f"Target: Remote server at {base_url}")
        client = httpx.Client(base_url=base_url, timeout=10.0)
    else:
        print("Target: In-process TestClient(app)")
        client = TestClient(app)

    results = []

    def check(name: str, passed: bool, detail: str = ""):
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str:4s}] {name} {('- ' + detail) if detail else ''}")
        results.append((name, passed))

    try:
        # 1. Health check
        r = client.get("/health")
        passed = (r.status_code == 200) and (r.json().get("status") in ("ok", "degraded"))
        check("GET /health", passed, f"status={r.status_code}, body={r.text[:60]}")

        # 2. List fraud reports
        r = client.get("/api/reports")
        passed = (r.status_code == 200) and isinstance(r.json(), list) and len(r.json()) > 0
        check("GET /api/reports", passed, f"status={r.status_code}, count={len(r.json()) if passed else 0}")

        # 3. Available MCP tools
        r = client.get("/api/tools")
        passed = (r.status_code == 200) and isinstance(r.json(), list) and len(r.json()) >= 10
        check("GET /api/tools", passed, f"status={r.status_code}, count={len(r.json()) if passed else 0}")

        # 4. Account profile
        r = client.get("/api/accounts/ACC_0461")
        passed = (r.status_code == 200) and (r.json().get("account_id") == "ACC_0461")
        check("GET /api/accounts/ACC_0461", passed, f"status={r.status_code}, name={r.json().get('holder_name')}")

        # 5. Graph neighborhood
        r = client.get("/api/graph/neighborhood?account_id=ACC_0461&hops=2&limit=60")
        passed = (r.status_code == 200) and ("nodes" in r.json()) and ("edges" in r.json())
        check("GET /api/graph/neighborhood", passed, f"status={r.status_code}, nodes={r.json().get('nodes', {}).get('total', 0)}")

        # 6. Saved cases list
        r = client.get("/api/cases")
        passed = (r.status_code == 200) and isinstance(r.json(), list)
        check("GET /api/cases", passed, f"status={r.status_code}, count={len(r.json()) if passed else 0}")

        # 7. Memory cases list
        r = client.get("/api/memory/cases")
        passed = (r.status_code == 200) and ("cases" in r.json() or "items" in r.json())
        check("GET /api/memory/cases", passed, f"status={r.status_code}")

        # 8. Admin reset memory (without DEMO_ADMIN=1 should be 403)
        r = client.post("/api/admin/reset-memory")
        passed = (r.status_code == 403)
        check("POST /api/admin/reset-memory (unauthorized)", passed, f"status={r.status_code}")

        # 9. Path traversal attempt check
        r = client.get("/api/cases/..%2F..%2Fetc%2Fpasswd")
        passed = (r.status_code in (400, 404))
        check("GET /api/cases/{traversal} rejected", passed, f"status={r.status_code}")

        # 10. Neighborhood parameter cap check (hops > 3)
        r = client.get("/api/graph/neighborhood?account_id=ACC_0461&hops=5&limit=60")
        passed = (r.status_code in (400, 422))
        check("GET /api/graph/neighborhood (hops>3 rejected)", passed, f"status={r.status_code}")

    finally:
        if hasattr(client, "close"):
            client.close()

    print("=" * 60)
    all_passed = all(p for _, p in results)
    total_passed = sum(1 for _, p in results if p)
    print(f"Summary: {total_passed}/{len(results)} passed.")
    if all_passed:
        print("ALL ENDPOINTS OPERATIONAL.")
        return 0
    else:
        print("SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(run_smoke_tests(url))
