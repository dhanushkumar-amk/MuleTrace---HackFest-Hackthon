"""Autonomous AI agent for MuleTrace UPI fraud money tracing (Phases 10-11).

Operates via Model Context Protocol (MCP) tool-calling against FalkorDB.
The agent chooses its own tools dynamically based on evidence without any hardcoded sequence.
Every freeze action is strictly a recommendation for human review.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import time
from typing import Any, Dict, List, Optional


def _compact_for_llm(fn_name: str, tool_res: Any) -> str:
    """Format tool result compactly for LLM context budget while keeping essential signals."""
    if not isinstance(tool_res, dict):
        return json.dumps(tool_res, separators=(",", ":"))

    data = copy.deepcopy(tool_res)
    if fn_name == "build_freeze_list":
        if "items" in data and isinstance(data["items"], list):
            for it in data["items"]:
                if isinstance(it, dict):
                    it.pop("edge_facts", None)
                    it.pop("evidence_call_ids", None)
    elif fn_name == "trace_money_forward":
        if "paths" in data and isinstance(data["paths"], dict):
            items = data["paths"].get("items", [])
            data["paths"]["items"] = [
                {"path": p.get("path"), "total_amount": p.get("total_amount")}
                for p in items if isinstance(p, dict)
            ]
    elif fn_name == "get_account_profile":
        data.pop("inflow_total", None)
        data.pop("outflow_total", None)
        data.pop("in_count", None)
        data.pop("out_count", None)
        data.pop("opened_at", None)
        data.pop("age_days", None)
        data.pop("is_flagged", None)
        data.pop("risk_score", None)
        if "devices" in data and isinstance(data["devices"], dict):
            devs = data["devices"].get("items", [])
            data["devices"] = [{"id": d.get("device_id"), "shares": d.get("share_count")} for d in devs if isinstance(d, dict)]
        if "phones" in data and isinstance(data["phones"], dict):
            phs = data["phones"].get("items", [])
            data["phones"] = [{"id": p.get("phone_id"), "shares": p.get("share_count")} for p in phs if isinstance(p, dict)]
        if "cash_outs" in data and isinstance(data["cash_outs"], dict):
            cos = data["cash_outs"].get("items", [])
            data["cash_outs"] = [c.get("amount") for c in cos if isinstance(c, dict)]
    elif fn_name in ("find_shared_devices", "find_shared_phones"):
        key = "shared_devices" if fn_name == "find_shared_devices" else "shared_phones"
        items = data.get(key, [])
        if not items:
            return "{}"
    elif fn_name == "find_cash_out_points":
        pts = data.get("cash_out_points", [])
        if not pts:
            return "{}"
    elif fn_name == "get_balance_held":
        return json.dumps(data.get("balances", {}), separators=(",", ":"))

    return json.dumps(data, separators=(",", ":"))

from backend.llm import get_groq_client, get_llm_model
from backend.mcp_client import MuleTraceMCPClient
from backend.prompts import SYSTEM_PROMPT
from backend.ledger import EvidenceLedger
from backend.schemas import InvestigationResult
from backend.tools import trace


def _extract_report_id(text: str) -> str:
    """Extract report ID (e.g. FR_0001) from input prompt or fallback."""
    match = re.search(r"FR_\d+", text)
    if match:
        return match.group(0)
    return "FR_0001"


async def run_investigation_async(
    query_or_report_id: str,
    max_steps: int = 15,
    save_memory: bool = False,
    mcp_mode: str = "in-process",
) -> Dict[str, Any]:
    """Execute autonomous agent investigation loop for a fraud report or query.

    Args:
        query_or_report_id: Report ID (e.g. 'FR_0001') or natural language investigation query.
        max_steps: Maximum interaction steps before forced conclusion.
        save_memory: Whether to ensure memory write-back is executed before finishing.
        mcp_mode: Transport mode for MCP client ('in-process', 'stdio', 'http').
    """
    t_start = time.perf_counter()
    session_id = f"session_{int(time.time() * 1000)}"
    trace.start(session_id)
    ledger = EvidenceLedger(session_id)

    groq_client = get_groq_client()
    model = get_llm_model()

    report_id = _extract_report_id(query_or_report_id)

    if query_or_report_id.startswith("FR_"):
        user_prompt = (
            f"Investigate fraud report {query_or_report_id}. Trace where the stolen funds went, "
            f"inspect suspect account profiles and shared devices/phones, produce a ranked freeze recommendation "
            f"using build_freeze_list, check for past cases using recall_past_cases, and save the case to memory."
        )
    else:
        user_prompt = query_or_report_id

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    llm_time_total = 0.0
    tool_time_total = 0.0
    step_count = 0
    nudged = False
    final_summary = ""

    async with MuleTraceMCPClient(mode=mcp_mode) as client:
        tools = await client.list_tools()

        for step in range(max_steps):
            step_count += 1

            # Compact older tool messages if conversation history is growing long
            if len(messages) > 6:
                for idx in range(2, len(messages) - 4):
                    m = messages[idx]
                    if m.get("role") == "tool" and len(m.get("content", "")) > 150:
                        m["content"] = m["content"][:120] + "...[trimmed]"

            # 1. Invoke LLM with backoff retry on Groq token/rate limits
            resp = None
            for attempt in range(4):
                try:
                    t_llm0 = time.perf_counter()
                    resp = groq_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto",
                        temperature=0.0,
                    )
                    t_llm1 = time.perf_counter()
                    llm_time_total += (t_llm1 - t_llm0)
                    break
                except Exception as exc:
                    err_str = str(exc).lower()
                    if ("413" in err_str or "429" in err_str or "rate_limit" in err_str or "tokens" in err_str) and attempt < 3:
                        backoff = 12.0 * (attempt + 1)
                        await asyncio.sleep(backoff)
                    else:
                        raise

            msg = resp.choices[0].message

            # 2. Process tool calls
            if msg.tool_calls:
                # Append assistant tool-calls message to history
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        fn_args = {}

                    t_tool0 = time.perf_counter()
                    tool_res = await client.call_tool(fn_name, fn_args)
                    t_tool1 = time.perf_counter()
                    tool_time_total += (t_tool1 - t_tool0)

                    ledger.record_tool_call(fn_name, fn_args, tool_res)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": _compact_for_llm(fn_name, tool_res),
                    })
                # Pacing pause to respect Groq rate limits
                await asyncio.sleep(1.0)
            else:
                # Model returned a textual response without tool calls
                # Requirement: If build_freeze_list has not been called, nudge once
                if not ledger.get_freeze_list() and not nudged and "FR_" in query_or_report_id:
                    nudged = True
                    messages.append({"role": "assistant", "content": msg.content or ""})
                    messages.append({
                        "role": "user",
                        "content": "A freeze recommendation has not been produced yet. Name your candidate suspects and call build_freeze_list to produce a ranked recommendation for human review.",
                    })
                    continue

                final_summary = msg.content or ""
                break

    # If --save-memory was requested and model did not call save_case_to_memory, execute it
    if save_memory and ledger.get_freeze_list() and not ledger.is_memory_saved():
        from backend import memory
        memory.save_case_to_memory(
            None,
            report_id=report_id,
            summary=final_summary[:500] or "Case investigation completed.",
        )
        ledger.memory_saved = True

    # Assemble output strictly from tool results in Python (never retyped by LLM)
    raw_freeze_list = ledger.get_freeze_list()
    grounded_freeze, claims_removed = ledger.ground_freeze_list(raw_freeze_list)
    not_recommended = ledger.get_not_recommended()
    past_cases = ledger.get_past_cases()
    memory_saved = ledger.is_memory_saved()
    total_recoverable = ledger.get_total_recoverable()
    total_cashed_out = ledger.get_total_cashed_out()

    t_total = time.perf_counter() - t_start

    result_data = InvestigationResult(
        report_id=report_id,
        summary=final_summary,
        recommendation_only=True,
        freeze_list=grounded_freeze,
        not_recommended=not_recommended,
        past_cases=past_cases,
        memory_saved=memory_saved,
        total_recoverable=total_recoverable,
        total_cashed_out=total_cashed_out,
        steps_taken=step_count,
        claims_removed=claims_removed,
        llm_time_seconds=round(llm_time_total, 2),
        tool_time_seconds=round(tool_time_total, 2),
        total_time_seconds=round(t_total, 2),
    )

    return result_data.model_dump()


def run_investigation(
    query_or_report_id: str,
    max_steps: int = 15,
    save_memory: bool = False,
    mcp_mode: str = "in-process",
) -> Dict[str, Any]:
    """Synchronous wrapper for running the agent investigation."""
    return asyncio.run(
        run_investigation_async(
            query_or_report_id=query_or_report_id,
            max_steps=max_steps,
            save_memory=save_memory,
            mcp_mode=mcp_mode,
        )
    )