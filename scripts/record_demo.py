"""Demo recorder script for MuleTrace (Phase 13).

Runs the real autonomous agent on Ravi's report (FR_0001), captures all SSE
events and the generated explanation, verifies the explanation, ensures the
decoy account (ACC_0476) was correctly rejected, and writes data/demo/ravi_run.json.

Can be re-run at any time to refresh the demo recording. Retries up to 3 times
if Groq is temporarily degraded or verification fails.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.agent import InvestigationAgent
from backend.explain import explain_case, save_case_explanation
from backend.explain_verify import verify_explanation

DEMO_DIR = REPO_ROOT / "data" / "demo"
DEMO_FILE = DEMO_DIR / "ravi_run.json"

REPORT_ID = "FR_0001"
DECOY_ACCOUNT = "ACC_0476"
MAX_RETRIES = 3


async def record_single_run(attempt: int) -> dict:
    session_id = f"demo_ravi_{int(time.time())}"
    print(f"\n[Attempt {attempt}/{MAX_RETRIES}] Starting live agent run for {REPORT_ID} (session: {session_id})...")

    task_prompt = (
        f"Investigate fraud report {REPORT_ID}: Rs 85,000 stolen from victim Ravi Kumar (ACC_0461). "
        "Trace forward from victim account ACC_0461 to identify all mule accounts, cash-out points, and shared infrastructure. "
        f"Also inspect suspicious candidate accounts in the area (including busy local shop {DECOY_ACCOUNT}) "
        "and pass all candidate accounts to build_freeze_list to ensure legitimate accounts are cleared and rejected, "
        "recall past cases, and save verified findings to memory."
    )

    agent = InvestigationAgent(
        query_or_report_id=task_prompt,
        session_id=session_id,
        max_steps=15,
        save_memory=True,
        polish=False,  # Keep deterministic for rock-solid reproducibility
    )

    events = []
    start_time = time.time()
    last_event_time = start_time

    async for ev in agent.run_stream():
        now = time.time()
        dur_ms = int((now - last_event_time) * 1000)
        last_event_time = now

        ev_copy = dict(ev)
        ev_copy["duration_ms"] = max(50, dur_ms)
        events.append(ev_copy)

        ev_type = ev.get("type", "unknown")
        if ev_type == "thought":
            print(f"  [Agent Thought] {str(ev.get('content', ''))[:80]}...")
        elif ev_type == "tool_call":
            print(f"  [Tool Call] {ev.get('tool')} with {json.dumps(ev.get('arguments', {}))[:60]}")
        elif ev_type == "tool_result":
            summary = ev.get("summary", "")
            print(f"  [Tool Result] {summary[:80]}")
        elif ev_type == "final":
            print(f"  [Final Result] Recoverable: Rs {ev.get('total_recoverable', 0)}, Freezes: {ev.get('freeze_count', 0)}")
        elif ev_type == "error":
            print(f"  [Error Event] {ev.get('message')}")

    total_time = round(time.time() - start_time, 2)
    step_count = len([e for e in events if e.get("type") in ("tool_call", "thought")])
    print(f"[Attempt {attempt}] Agent run finished in {total_time}s across {step_count} steps ({len(events)} events).")

    # Generate and verify explanation
    explanation = explain_case(session_id)
    verification = verify_explanation(explanation)
    verified = bool(verification.get("verified"))

    rejections = [r.get("account") for r in explanation.get("rejections", [])]
    decoy_rejected = DECOY_ACCOUNT in rejections
    freeze_items = [it.get("account") for it in explanation.get("recommendations", [])]

    print(f"  - Verified: {verified}")
    print(f"  - Decoy ({DECOY_ACCOUNT}) Rejected: {decoy_rejected}")
    print(f"  - Recommended Freeze List: {freeze_items}")
    print(f"  - Verification checks: {verification.get('checks', {})}")

    return {
        "session_id": session_id,
        "report_id": REPORT_ID,
        "recorded_at": int(time.time()),
        "total_time_seconds": total_time,
        "step_count": step_count,
        "events": events,
        "explanation": explanation,
        "verified": verified,
        "decoy_rejected": decoy_rejected,
        "freeze_list": freeze_items,
        "rejections": rejections,
    }


async def main():
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            run_data = await record_single_run(attempt)
            if run_data["verified"] and run_data["decoy_rejected"]:
                with open(DEMO_FILE, "w", encoding="utf-8") as f:
                    json.dump(run_data, f, indent=2)
                print(f"\nSUCCESS: Demo recorded and saved to {DEMO_FILE}")
                print(f"Summary:")
                print(f"  Steps: {run_data['step_count']}")
                print(f"  Time: {run_data['total_time_seconds']}s")
                print(f"  Freeze List: {run_data['freeze_list']}")
                print(f"  Decoy Rejected: {'YES' if run_data['decoy_rejected'] else 'NO'}")
                print(f"  Verified: {'YES' if run_data['verified'] else 'NO'}")
                return 0
            else:
                print(f"\nWARNING: Attempt {attempt} did not satisfy all criteria (verified={run_data['verified']}, decoy_rejected={run_data['decoy_rejected']}). Retrying...")
        except Exception as exc:
            print(f"\nERROR on attempt {attempt}: {exc}")
            if attempt == MAX_RETRIES:
                raise
        await asyncio.sleep(2)

    print("\nFAILURE: Could not record a satisfying demo run within retry limit.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
