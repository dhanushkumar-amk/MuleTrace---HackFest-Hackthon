"""Tests for MuleTrace tool registry, output compaction, tracing, and MCP layer (Phase 9).

Verifies:
1. Tool registry definitions, schemas, and descriptions (<80 words).
2. Output compaction under token size limits (~3,000 chars) while preserving critical fields.
3. Robust error handling (returns {"error": "...", "hint": "..."} without crashing).
4. Full parity between direct query calls and MCP client calls for Ring 1 money tracing.
5. In-memory and JSONL trace logging.
6. OpenAI/Groq function-calling schema compliance.
7. Stdio and Streamable HTTP MCP transports.
8. Safety: Greps backend/ ensuring no reads or references to tests/, docs/, or ground_truth.json.
9. Groq tool-selection smoke test with temperature 0.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from dotenv import load_dotenv

from backend.db import get_graph
from backend import queries as q
from backend.tools import registry, trace
from backend.tools.compaction import compact_output, DEFAULT_MAX_CHARS
from backend.mcp_client import MuleTraceMCPClient
from backend.mcp_server import server as mcp_server
from backend.llm import get_groq_client, get_llm_model

load_dotenv()

with open(ROOT / "tests" / "ground_truth.json", encoding="utf-8") as fh:
    GT = json.load(fh)

RAVI = GT["victim_account_id"]
THEFT = GT["reported_at"] - 6300  # 1792038600
R1 = GT["rings"]["1"]
MULES1 = set(R1["accounts"])

EXPECTED_TOOLS = [
    "get_fraud_report",
    "get_account_profile",
    "trace_money_forward",
    "find_cash_out_points",
    "get_balance_held",
    "find_shared_devices",
    "find_shared_phones",
    "detect_rapid_hops",
    "detect_fan_in",
    "detect_fan_out",
    "get_neighborhood",
    "find_shortest_path",
    "rank_hub_accounts",
    "find_connected_components",
    "find_communities",
    "find_connected_ring",
    "rank_chokepoints",
]


@pytest.fixture(scope="module")
def graph():
    return get_graph()


# ===========================================================================
# 1. Registry Integrity Tests
# ===========================================================================

def test_registry_has_all_expected_tools():
    tools = registry.list_tools()
    tool_names = [t.name for t in tools]
    assert len(tool_names) == 17
    for expected in EXPECTED_TOOLS:
        assert expected in tool_names

        tool_def = registry.get_tool(expected)
        assert tool_def is not None
        assert tool_def.name == expected
        assert callable(tool_def.handler)
        assert tool_def.kind in ("query", "algorithm", "action")

        # Description constraints: concise (< 80 words), no file paths, no graph names
        desc = tool_def.description
        assert desc and len(desc.split()) < 80
        assert "muletrace" not in desc.lower()
        assert "/" not in desc and "\\" not in desc

        # JSON schema validity
        schema = tool_def.get_json_schema()
        assert schema.get("type") == "object"
        assert "properties" in schema


def test_build_freeze_list_placeholder_exists():
    registry_file = ROOT / "backend" / "tools" / "registry.py"
    content = registry_file.read_text(encoding="utf-8")
    assert "build_freeze_list" in content
    assert "Phase 11" in content
    # Ensure it is not implemented as a tool in the active registry
    assert registry.get_tool("build_freeze_list") is None


# ===========================================================================
# 2. Schema and Groq Conversion Tests
# ===========================================================================

def test_groq_format_conversion():
    async def _run():
        client = MuleTraceMCPClient(mode="in-process")
        tools = await client.list_tools()
        assert len(tools) == 17
        for t in tools:
            assert t.get("type") == "function"
            fn = t.get("function", {})
            assert fn.get("name") in EXPECTED_TOOLS
            assert isinstance(fn.get("description"), str)
            assert fn.get("parameters", {}).get("type") == "object"

    asyncio.run(_run())


# ===========================================================================
# 3. Parity and Execution through MCP Client
# ===========================================================================

def test_trace_money_forward_finds_ring1_chain_through_mcp(graph):
    async def _run():
        # 1. Direct call
        direct_res = q.trace_money_forward(graph, RAVI, THEFT, max_hops=8)
        direct_paths = [p["path"] for p in direct_res["paths"]["items"]]

        # 2. MCP Client call
        client = MuleTraceMCPClient(mode="in-process")
        mcp_res = await client.call_tool(
            "trace_money_forward",
            {"start_account_id": RAVI, "start_time": THEFT, "max_hops": 8},
        )
        assert "paths" in mcp_res
        mcp_paths = [p["path"] for p in mcp_res["paths"]["items"]]

        assert mcp_paths == direct_paths
        reachable = {a for p in mcp_paths for a in p}
        assert MULES1 <= reachable
        assert R1["chain_cashout"] in mcp_paths

    asyncio.run(_run())


def test_every_tool_returns_compact_json_under_size_cap():
    async def _run():
        client = MuleTraceMCPClient(mode="in-process")

        sample_inputs: Dict[str, Dict[str, Any]] = {
            "get_fraud_report": {"report_id": "FR_0001"},
            "get_account_profile": {"account_id": RAVI},
            "trace_money_forward": {"start_account_id": RAVI, "start_time": THEFT, "max_hops": 4},
            "find_cash_out_points": {"account_ids": [R1["cashout_account"]]},
            "get_balance_held": {"account_ids": [RAVI, R1["accounts"][0]]},
            "find_shared_devices": {"account_id": R1["accounts"][1]},
            "find_shared_phones": {"account_id": R1["accounts"][1]},
            "detect_rapid_hops": {"account_id": R1["accounts"][0], "window_seconds": 600},
            "detect_fan_in": {"window_seconds": 86400, "min_senders": 3},
            "detect_fan_out": {"account_id": R1["accounts"][0], "window_seconds": 3600},
            "get_neighborhood": {"account_id": RAVI, "hops": 2},
            "find_shortest_path": {"src_account_id": RAVI, "dst_account_id": R1["cashout_account"]},
            "rank_hub_accounts": {"top_k": 10},
            "find_connected_components": {"min_size": 3, "limit": 10},
            "find_communities": {"limit": 10},
            "find_connected_ring": {"account_id": R1["accounts"][0]},
            "rank_chokepoints": {"account_ids": list(MULES1), "top_k": 5},
        }

        for name in EXPECTED_TOOLS:
            inp = sample_inputs.get(name, {})
            res = await client.call_tool(name, inp)
            assert isinstance(res, dict)
            serialized_len = len(json.dumps(res))
            assert serialized_len <= 3500, f"Tool {name} output exceeded size limit: {serialized_len}"

    asyncio.run(_run())


# ===========================================================================
# 4. Error Handling & Timeout Tests
# ===========================================================================

def test_bad_arguments_return_error_with_hint_never_crash():
    async def _run():
        client = MuleTraceMCPClient(mode="in-process")

        # 1. Missing required parameter
        r1 = await client.call_tool("get_fraud_report", {})
        assert "error" in r1 and "hint" in r1
        assert "report_id" in r1["error"].lower() or "missing" in r1["error"].lower() or "validation" in r1["error"].lower()

        # 2. Wrong parameter type
        r2 = await client.call_tool("trace_money_forward", {"start_account_id": RAVI, "start_time": "invalid_not_an_int"})
        assert "error" in r2 and "hint" in r2

        # 3. Unknown account id
        r3 = await client.call_tool("get_account_profile", {"account_id": "ACC_DOES_NOT_EXIST_999"})
        assert "error" in r3 and "hint" in r3
        assert "not found" in r3["error"].lower()

        # 4. Unknown fraud report id
        r4 = await client.call_tool("get_fraud_report", {"report_id": "FR_INVALID_999"})
        assert "error" in r4 and "hint" in r4
        assert "not found" in r4["error"].lower()

    asyncio.run(_run())


def test_output_compaction_edge_cases():
    huge_data = {
        "path": ["ACC_0001", "ACC_0002"],
        "items": [{"account": f"ACC_{i}", "location": "Very long location string" * 10, "amount": i} for i in range(200)],
        "truncated": False,
        "total": 200,
    }
    compacted = compact_output(huge_data, max_chars=1500)
    assert len(json.dumps(compacted)) <= 1600
    assert compacted["truncated"] is True
    assert compacted["total"] == 200
    assert "path" in compacted
    assert "note" in compacted


# ===========================================================================
# 5. Tool Call Trace Tests
# ===========================================================================

def test_trace_log_records_call_with_correct_fields():
    async def _run():
        session_id = "test_session_trace_42"
        trace.start(session_id)

        client = MuleTraceMCPClient(mode="in-process")
        await client.call_tool("get_fraud_report", {"report_id": "FR_0001"})

        records = trace.get(session_id)
        assert len(records) >= 1
        rec = records[-1]
        assert rec["session_id"] == session_id
        assert rec["tool_name"] == "get_fraud_report"
        assert rec["arguments"] == {"report_id": "FR_0001"}
        assert rec["ok"] is True
        assert rec["duration_ms"] > 0
        assert rec["result_size"] > 0
        assert "timestamp" in rec

        log_file = ROOT / "data" / "runtime" / "tool_calls.jsonl"
        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert any(session_id in line for line in lines)

    asyncio.run(_run())


# ===========================================================================
# 6. Safety Grep Test
# ===========================================================================

def test_safety_backend_never_reads_test_docs_or_ground_truth():
    """Ensure no code path in backend/ references tests/, docs/, or ground_truth.json."""
    backend_dir = ROOT / "backend"
    forbidden = ["tests/", "docs/", "ground_truth.json"]

    violations = []
    for p in backend_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for f in forbidden:
            if f in text:
                violations.append((str(p.relative_to(ROOT)), f))

    assert not violations, f"Forbidden string references found in backend: {violations}"


# ===========================================================================
# 7. MCP Server Transports Test
# ===========================================================================

def test_mcp_server_transports():
    async def _run():
        # 1. Stdio transport
        async with MuleTraceMCPClient(mode="stdio") as stdio_client:
            tools_stdio = await stdio_client.list_tools()
            assert len(tools_stdio) == 17
            res_stdio = await stdio_client.call_tool("get_fraud_report", {"report_id": "FR_0001"})
            assert res_stdio.get("found") is True

        # 2. Streamable HTTP transport on port 8765
        server_thread = threading.Thread(
            target=lambda: mcp_server.run(transport="streamable-http", host="127.0.0.1", port=8765),
            daemon=True,
        )
        server_thread.start()
        await asyncio.sleep(1.2)  # wait for uvicorn to bind

        async with MuleTraceMCPClient(mode="http", http_url="http://127.0.0.1:8765/mcp") as http_client:
            tools_http = await http_client.list_tools()
            assert len(tools_http) == 17
            res_http = await http_client.call_tool("get_fraud_report", {"report_id": "FR_0001"})
            assert res_http.get("found") is True

    asyncio.run(_run())


# ===========================================================================
# 8. Tool Selection Smoke Test with Groq
# ===========================================================================

def test_groq_tool_selection_smoke():
    async def _run():
        groq_client = get_groq_client()
        model = get_llm_model()

        client = MuleTraceMCPClient(mode="in-process")
        tools = await client.list_tools()

        test_queries = [
            ("Where did Ravi's money go after the theft?", "trace_money_forward"),
            ("Who shares a device with this account?", "find_shared_devices"),
            ("Which accounts look like hubs this week?", "rank_hub_accounts"),
            ("Is this shop behaving like a mule?", "get_account_profile"),
            ("Are these two accounts connected through anything?", "find_shortest_path"),
            ("Find rings linked to this account", "find_connected_ring"),
            ("What are the details of the filed fraud complaint?", "get_fraud_report"),
            ("Where did the stolen funds get cashed out into crypto or cash?", "find_cash_out_points"),
        ]

        print("\n" + "=" * 80)
        print("GROQ TOOL SELECTION SMOKE TEST RESULTS")
        print("=" * 80)
        print(f"{'User Query':<50} | {'Expected Tool':<22} | {'Chosen Tool':<22} | {'Match'}")
        print("-" * 105)

        matches = 0
        diffs = []
        for query, expected in test_queries:
            time.sleep(1.5)  # Rate limit pacing
            resp = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the MuleTrace anti-money-laundering investigation agent. "
                            "For every user query, invoke the single best tool from the provided definitions to answer or investigate the request. "
                            "Do not output conversational prose; immediately call the tool."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                tools=tools,
                tool_choice="auto",
                temperature=0.0,
            )
            msg = resp.choices[0].message
            chosen = msg.tool_calls[0].function.name if msg.tool_calls else None
            is_match = (chosen == expected)
            if is_match:
                matches += 1
            else:
                diffs.append((query, expected, chosen))

            print(f"{query[:48]:<50} | {expected:<22} | {str(chosen):<22} | {'PASS' if is_match else 'DIFF'}")

        print("=" * 80)
        print(f"Total Matches: {matches} / {len(test_queries)}")
        if diffs:
            print(f"Discrepancies observed ({len(diffs)}):")
            for q_text, exp, got in diffs:
                print(f"  - Query: '{q_text}' -> Expected: '{exp}', Got: '{got}'")
        print("=" * 80)

        # Acceptance rule: Do not fail the whole suite if 1 or 2 differ, but assert at least 6/8
        assert matches >= 6, f"Too many tool selection mismatches: {matches}/{len(test_queries)}"

    asyncio.run(_run())
