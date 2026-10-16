"""Demonstration script for MuleTrace MCP Client and Tool Layer (Phase 9).

Connects to the MuleTrace MCP server, lists all registered tools with their
prompt descriptions, and executes 3 sample tools against Ravi's case (FR_0001)
through the MCP client bridge, printing compacted results and timings.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure repo root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.mcp_client import MuleTraceMCPClient


async def main() -> None:
    print("=" * 80)
    print("  MULETRACE MCP CLIENT & TOOL LAYER DEMO (Phase 9)")
    print("=" * 80)

    client = MuleTraceMCPClient()
    t_start = time.perf_counter()

    # 1. Discover and print all tools
    print("\n--- 1. REGISTERED TOOLS IN MCP REGISTRY ---")
    tools = await client.list_tools()
    print(f"Total registered tools: {len(tools)}\n")

    for i, t in enumerate(tools, 1):
        fn = t["function"]
        name = fn["name"]
        desc = fn["description"]
        print(f"[{i:02d}] {name}")
        print(f"     Description: {desc}")
        props = list(fn.get("parameters", {}).get("properties", {}).keys())
        print(f"     Parameters: {props}\n")

    # 2. Call Tool 1: get_fraud_report on Ravi's report (FR_0001)
    print("=" * 80)
    print("--- 2. CALLING TOOL 1: get_fraud_report (FR_0001) ---")
    t0 = time.perf_counter()
    report_res = await client.call_tool("get_fraud_report", {"report_id": "FR_0001"})
    dur1 = (time.perf_counter() - t0) * 1000
    print(f"Execution time: {dur1:.2f} ms")
    print(f"Result:\n{json.dumps(report_res, indent=2)}\n")

    victim_id = report_res.get("victim", {}).get("id", "ACC_0461")
    reported_at = report_res.get("report", {}).get("reported_at", 1792044900)

    # 3. Call Tool 2: trace_money_forward from Ravi's account
    print("=" * 80)
    print(f"--- 3. CALLING TOOL 2: trace_money_forward ({victim_id}) ---")
    t0 = time.perf_counter()
    theft_time = reported_at - 7200  # Fraud occurs prior to report filing
    trace_res = await client.call_tool(
        "trace_money_forward",
        {
            "start_account_id": victim_id,
            "start_time": theft_time,
            "max_hops": 4,
            "min_amount": 500,
        },
    )
    dur2 = (time.perf_counter() - t0) * 1000
    print(f"Execution time: {dur2:.2f} ms")
    print(f"Compacted Result:\n{json.dumps(trace_res, indent=2)}\n")

    # 4. Call Tool 3: find_shared_devices for Ring 1 mule ACC_0463
    target_mule = "ACC_0463"
    print("=" * 80)
    print(f"--- 4. CALLING TOOL 3: find_shared_devices ({target_mule}) ---")
    t0 = time.perf_counter()
    device_res = await client.call_tool("find_shared_devices", {"account_id": target_mule})
    dur3 = (time.perf_counter() - t0) * 1000
    print(f"Execution time: {dur3:.2f} ms")
    print(f"Result:\n{json.dumps(device_res, indent=2)}\n")

    total_dur = (time.perf_counter() - t_start) * 1000
    print("=" * 80)
    print(f"Demo completed successfully in {total_dur:.2f} ms.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
