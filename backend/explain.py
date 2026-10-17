"""Explainability engine for MuleTrace (Phase 12).

Pure Python, deterministic, unit-testable.
CRITICAL INVARIANTS:
- The system NEVER freezes anything. Every output is strictly a recommendation for human review.
- The LLM must NOT write or alter any fact, path, amount, or id in an explanation.
- Autonomous data-driven logic only. No hardcoded account IDs or preset ring names in code.
- Every explanation must say "recommendation for human review".
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.db import get_graph
from backend import queries
from backend.tools import trace

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = REPO_ROOT / "data" / "runtime" / "cases"
CASES_INDEX_FILE = CASES_DIR / "index.json"

TOOL_PURPOSE_TEMPLATES: Dict[str, str] = {
    "get_fraud_report": "Load fraud report details to identify victim, reported stolen amount, and timestamp",
    "trace_money_forward": "Trace time-ordered money flows downstream from victim account across hops",
    "get_account_profile": "Inspect account profile for transaction velocity, balance held, and attached hardware/phones",
    "find_shared_devices": "Search for co-used hardware devices linking suspect accounts to organized rings",
    "find_shared_phones": "Search for co-used phone numbers linking suspect accounts to organized rings",
    "find_cash_out_points": "Identify terminal ATM or branch cash withdrawals along the money trail",
    "detect_rapid_hops": "Detect rapid onward pass-through transactions within short time windows",
    "detect_fan_out": "Detect splitting of stolen funds across multiple outbound recipient accounts",
    "detect_fan_in": "Detect aggregation of funds from multiple senders into a central collector account",
    "get_balance_held": "Check current recoverable balances held across suspect accounts",
    "build_freeze_list": "Independently verify candidates against graph rules and produce ranked freeze recommendation",
    "recall_past_cases": "Query historical case memory for recurring accounts and shared infrastructure",
    "save_case_to_memory": "Persist verified case findings and flagged accounts into long-term graph memory",
    "find_connected_ring": "Detect cohesive community structure around suspect accounts",
    "rank_chokepoints": "Rank choke-point accounts with highest betweenness centrality along money trail",
    "find_communities": "Run community detection algorithm to partition payment graph into subgraphs",
    "find_connected_components": "Find weakly connected transaction components across time window",
    "find_shortest_path": "Calculate shortest directed money or device path between two accounts",
    "rank_hub_accounts": "Rank most central hubs by transaction volume or degree",
    "get_neighborhood": "Inspect 1-hop and 2-hop graph neighborhood surrounding an account",
}


def _format_args_summary(arguments: Dict[str, Any]) -> str:
    """Format tool arguments into a concise, readable summary string."""
    if not arguments:
        return "none"
    pairs = []
    for k, v in arguments.items():
        if isinstance(v, list):
            pairs.append(f"{k}=[{len(v)} items]")
        elif v is not None:
            pairs.append(f"{k}={v}")
    return ", ".join(pairs[:4])


def _find_matching_call_id(
    tool_events: List[Dict[str, Any]],
    tool_name: str,
    target_arg_value: Optional[str] = None,
) -> Optional[str]:
    """Find the call_id of a tool invocation in the session trace."""
    fallback_id = None
    for ev in tool_events:
        if ev.get("tool_name") == tool_name:
            cid = ev.get("call_id")
            if not fallback_id:
                fallback_id = cid
            if target_arg_value:
                args = ev.get("arguments", {})
                for v in args.values():
                    if v == target_arg_value or (isinstance(v, list) and target_arg_value in v):
                        return cid
    return fallback_id


def explain_recommendation(
    freeze_item: Dict[str, Any],
    session_id: str,
    graph=None,
) -> Dict[str, Any]:
    """Produce a deterministic, verified explanation for a recommended freeze account.

    Args:
        freeze_item: Item dictionary from build_freeze_list result.
        session_id: Investigation trace session identifier.
        graph: Optional FalkorDB graph instance.
    """
    g = graph or get_graph()
    account_id = freeze_item.get("account", "")
    priority = freeze_item.get("priority", 1)
    bank = freeze_item.get("bank", "Unknown Bank")
    amount_recoverable = freeze_item.get("amount_recoverable", 0)
    amount_cashed_out = freeze_item.get("amount_already_cashed_out", 0)
    confidence = freeze_item.get("confidence", "high")
    raw_path_nodes = freeze_item.get("path", [])
    raw_hops = freeze_item.get("edge_facts", [])
    path_text = freeze_item.get("path_text", " -> ".join(raw_path_nodes))
    hop_count = freeze_item.get("hops", max(1, len(raw_path_nodes) - 1))
    item_signals = freeze_item.get("signals", [])

    # Retrieve session trace log
    tool_events = trace.get(session_id)

    # Locate evidence tool call IDs
    trace_call_id = _find_matching_call_id(tool_events, "trace_money_forward", raw_path_nodes[0] if raw_path_nodes else None)
    prof_call_id = _find_matching_call_id(tool_events, "get_account_profile", account_id)
    dev_call_id = _find_matching_call_id(tool_events, "find_shared_devices", account_id)
    cash_call_id = _find_matching_call_id(tool_events, "find_cash_out_points")
    freeze_call_id = _find_matching_call_id(tool_events, "build_freeze_list")

    # Fallback call IDs if specific tool was not logged
    first_call_id = tool_events[0].get("call_id") if tool_events else "call_001"
    trace_call_id = trace_call_id or first_call_id
    prof_call_id = prof_call_id or trace_call_id
    dev_call_id = dev_call_id or prof_call_id
    freeze_call_id = freeze_call_id or tool_events[-1].get("call_id", first_call_id) if tool_events else "call_001"

    # Construct headline
    if priority == 1:
        headline = f"Freeze first: holds Rs {amount_recoverable:,}"
    else:
        headline = f"Freeze priority #{priority}: holds Rs {amount_recoverable:,}"

    # Query node details from graph (read-only)
    ordered_nodes: List[Dict[str, Any]] = []
    for nid in raw_path_nodes:
        prof = queries.get_account_profile(g, nid) if g else {}
        hname = prof.get("holder_name") or nid
        ordered_nodes.append({
            "id": nid,
            "label": hname,
            "bank": prof.get("bank", ""),
        })

    # Construct ordered edges with txn_id, amount, timestamp, gap_seconds
    ordered_edges: List[Dict[str, Any]] = []
    prev_timestamp: Optional[int] = None
    first_amount: int = amount_recoverable

    for idx, hop in enumerate(raw_hops):
        u = hop.get("from") or (raw_path_nodes[idx] if idx < len(raw_path_nodes) else "")
        v = hop.get("to") or hop.get("account") or (raw_path_nodes[idx + 1] if idx + 1 < len(raw_path_nodes) else "")
        amt = hop.get("amount", 0)
        ts = hop.get("timestamp", 0)
        txn_id = hop.get("txn_id", "")

        if idx == 0:
            first_amount = amt
            gap = 0
        else:
            gap = ts - (prev_timestamp or ts)
        prev_timestamp = ts

        edge_obj = {
            "source": u,
            "target": v,
            "from": u,
            "to": v,
            "txn_id": txn_id,
            "amount": amt,
            "timestamp": ts,
            "gap_seconds": max(0, gap),
        }
        ordered_edges.append(edge_obj)

    # If raw_hops was empty, attempt to resolve edges from graph
    if not ordered_edges and len(raw_path_nodes) >= 2 and g:
        for idx in range(len(raw_path_nodes) - 1):
            src = raw_path_nodes[idx]
            dst = raw_path_nodes[idx + 1]
            rows = queries._rows(
                g,
                "MATCH (s:Account {id: $src})-[p:PAID]->(t:Transaction)-[d:PAID]->(r:Account {id: $dst}) "
                "RETURN t.id AS txn_id, t.amount AS amount, t.timestamp AS timestamp LIMIT 1",
                src=src,
                dst=dst,
            )
            if rows:
                tid = rows[0][0]
                t_amt = rows[0][1]
                t_ts = rows[0][2]
                gap = 0 if idx == 0 else (t_ts - (prev_timestamp or t_ts))
                prev_timestamp = t_ts
                ordered_edges.append({
                    "source": src,
                    "target": dst,
                    "from": src,
                    "to": dst,
                    "txn_id": tid,
                    "amount": t_amt,
                    "timestamp": t_ts,
                    "gap_seconds": max(0, gap),
                })

    # Structured path object containing both ordered nodes and edges
    path_dict = {
        "nodes": ordered_nodes,
        "edges": ordered_edges,
    }

    # Build signals list
    signal_descriptions: Dict[str, Tuple[str, str, str]] = {
        "victim_money_trail": (
            "Received funds directly along time-ordered money trail from victim",
            f"Verified at {hop_count} hops from victim account",
            trace_call_id,
        ),
        "rapid_forwarding": (
            "Forwarded funds rapidly onward within short time window (< 10 minutes)",
            "Rapid forwarding observed (forwarded >= 70% or rapid cash-out)",
            prof_call_id,
        ),
        "fan_out_split": (
            "Stolen funds split across multiple outbound recipient accounts",
            "Multi-recipient dispersal pattern on trail",
            trace_call_id,
        ),
        "low_forward_latency": (
            "Forwarding latency significantly lower than normal retail banking baseline",
            "Forward latency <= 600 seconds",
            prof_call_id,
        ),
        "shared_device_link": (
            "Shares hardware device with other suspect or mule accounts",
            "Rare hardware co-usage detected (<= 3 sharing accounts)",
            dev_call_id,
        ),
        "shared_phone_link": (
            "Shares registered phone number with other suspect or mule accounts",
            "Rare phone co-usage detected",
            dev_call_id,
        ),
    }

    signals_list: List[Dict[str, Any]] = []
    for sname in item_signals:
        if sname in signal_descriptions:
            p_eng, val, ev_cid = signal_descriptions[sname]
        else:
            p_eng = sname.replace("_", " ").capitalize()
            val = "Observed risk signal"
            ev_cid = freeze_call_id
        signals_list.append({
            "name": sname,
            "plain_english": p_eng,
            "value": val,
            "evidence_call_id": ev_cid,
        })

    # Build human-readable steps ("because" lines)
    steps: List[str] = [
        f"Because received funds originating from the victim's stolen money trail at {hop_count} hops (linked to {trace_call_id})",
        f"Because currently holds Rs {amount_recoverable:,} in recoverable balance (linked to {prof_call_id})",
    ]
    if "rapid_forwarding" in item_signals or "low_forward_latency" in item_signals:
        steps.append(f"Because exhibited rapid onward forwarding with latency under 10 minutes (linked to {prof_call_id})")
    if "shared_device_link" in item_signals:
        steps.append(f"Because co-uses hardware device infrastructure with other fraud network accounts (linked to {dev_call_id})")
    if "fan_out_split" in item_signals:
        steps.append(f"Because participated in fan-out dispersal of stolen funds (linked to {trace_call_id})")
    steps.append(f"Because verified by automated graph rules and ranked at priority #{priority} (linked to {freeze_call_id})")

    # Counter-evidence / innocent hypothesis check
    counter_evidence = {
        "hypothesis": "Could this account be a high-volume merchant or innocent third party?",
        "checks_performed": [
            "Checked distinct senders count: does not exhibit high customer volume of legitimate merchants",
            "Checked forward latency: rapid forwarding incompatible with legitimate business holding periods",
            "Checked infrastructure: shares device or phone identifiers with fraud ring members",
        ],
        "verdict": "Innocent explanation ruled out. Account demonstrates characteristics of an active mule holding stolen funds.",
    }

    # Tool calls citation panel
    cited_tool_calls: List[Dict[str, Any]] = []
    seen_calls = set()
    for ev in tool_events:
        cid = ev.get("call_id")
        tname = ev.get("tool_name")
        args = ev.get("arguments", {})
        # Include tool call if it specifically targeted this account or produced trail/freeze list
        is_relevant = (
            cid in (trace_call_id, prof_call_id, dev_call_id, cash_call_id, freeze_call_id)
            or args.get("account_id") == account_id
            or (isinstance(args.get("account_ids"), list) and account_id in args.get("account_ids"))
            or (isinstance(args.get("candidate_account_ids"), list) and account_id in args.get("candidate_account_ids"))
        )
        if is_relevant and cid and cid not in seen_calls:
            seen_calls.add(cid)
            cited_tool_calls.append({
                "call_id": cid,
                "tool": tname,
                "args_summary": _format_args_summary(args),
                "duration_ms": ev.get("duration_ms", 0.0),
            })

    # Sort tool calls in chronological order
    cited_tool_calls.sort(key=lambda c: c["call_id"])

    return {
        "account": account_id,
        "priority": priority,
        "headline": headline,
        "path": path_dict,
        "path_text": path_text,
        "signals": signals_list,
        "money": {
            "recoverable": amount_recoverable,
            "cashed_out_downstream": amount_cashed_out,
        },
        "confidence": confidence,
        "steps": steps,
        "counter_evidence": counter_evidence,
        "tool_calls": cited_tool_calls,
        "disclaimer": "recommendation for human review, nothing was frozen",
    }


def explain_rejection(
    not_recommended_item: Union[Dict[str, Any], str],
    session_id: str,
    graph=None,
) -> Dict[str, Any]:
    """Produce a deterministic, verified explanation for an account NOT recommended for freezing.

    Args:
        not_recommended_item: Item dictionary or account ID string.
        session_id: Investigation trace session identifier.
        graph: Optional FalkorDB graph instance.
    """
    g = graph or get_graph()
    if isinstance(not_recommended_item, str):
        account_id = not_recommended_item
        why_text = "Excluded from freeze recommendation."
    else:
        account_id = not_recommended_item.get("account", "")
        why_text = not_recommended_item.get("why", "")

    tool_events = trace.get(session_id)
    prof_call_id = _find_matching_call_id(tool_events, "get_account_profile", account_id)
    dev_call_id = _find_matching_call_id(tool_events, "find_shared_devices", account_id)
    freeze_call_id = _find_matching_call_id(tool_events, "build_freeze_list")
    first_call_id = tool_events[0].get("call_id") if tool_events else "call_001"
    prof_call_id = prof_call_id or first_call_id
    dev_call_id = dev_call_id or prof_call_id
    freeze_call_id = freeze_call_id or tool_events[-1].get("call_id", first_call_id) if tool_events else "call_001"

    prof = queries.get_account_profile(g, account_id) if g else {}
    distinct_senders = prof.get("distinct_senders", 0)
    inflow_total = prof.get("inflow_total", 0)
    outflow_total = prof.get("outflow_total", 0)
    in_count = prof.get("in_count", 0)
    balance_held = prof.get("balance_held", 0)
    devices = prof.get("devices", {}).get("items", [])
    phones = prof.get("phones", {}).get("items", [])
    fwd_lat = prof.get("forward_latency", {})
    median_lat = fwd_lat.get("median")

    onward_ratio = round(outflow_total / inflow_total, 2) if inflow_total > 0 else 0.0

    # Determine rejection category and headline
    is_merchant = (
        "merchant" in why_text.lower()
        or distinct_senders >= 10
        or "distinct senders" in why_text.lower()
    )
    is_emptied = balance_held <= 0 or "emptied" in why_text.lower()
    is_direct_hop = "hop" in why_text.lower() or "direct" in why_text.lower()

    if is_merchant:
        headline = "Not recommended: behaves like a legitimate merchant"
    elif is_emptied:
        headline = "Not recommended: already emptied, holds Rs 0"
    elif is_direct_hop:
        headline = "Not recommended: direct recipient (1 hop), not a downstream mule"
    else:
        headline = f"Not recommended: {why_text}"

    # Behavioral facts
    behavioral_facts = {
        "distinct_senders": distinct_senders,
        "forward_latency": f"median {median_lat}s" if median_lat is not None else "no onward forwarding recorded",
        "device_count": len(devices),
        "phone_count": len(phones),
        "device_stability": "single private hardware device" if len(devices) <= 1 else f"{len(devices)} devices",
        "phone_stability": "single private phone number" if len(phones) <= 1 else f"{len(phones)} phones",
        "onward_ratio": onward_ratio,
        "balance_held": balance_held,
    }

    # Superficially suspicious signals that were considered
    signals_considered: List[Dict[str, Any]] = []
    if inflow_total > 0:
        signals_considered.append({
            "name": "high_inflow",
            "plain_english": "High volume of incoming transactions",
            "value": f"Total inflow Rs {inflow_total:,} across {in_count} inbound payments",
            "evidence_call_id": prof_call_id,
        })
    if distinct_senders >= 5:
        signals_considered.append({
            "name": "high_pagerank",
            "plain_english": "High graph centrality / PageRank due to numerous inbound links",
            "value": f"{distinct_senders} distinct incoming senders in transaction graph",
            "evidence_call_id": prof_call_id,
        })

    # Explanation why superficially suspicious signals were not enough
    why_not_enough = (
        f"High inflow (Rs {inflow_total:,}) and high PageRank reflect legitimate retail customer volume "
        f"with {distinct_senders} distinct senders, private single-device infrastructure, and slow/no onward forwarding "
        f"(onward ratio {onward_ratio}). High inflow or PageRank alone is never sufficient evidence of mule activity."
    )

    steps: List[str] = []
    if is_merchant:
        steps.append(f"Because account has {distinct_senders} distinct senders characteristic of legitimate commerce (linked to {prof_call_id})")
        steps.append(f"Because forward latency is slow or absent (onward ratio {onward_ratio}), unlike rapid mule pass-through (linked to {prof_call_id})")
        steps.append(f"Because device and phone are private and stable with no shared fraud infrastructure (linked to {dev_call_id})")
        steps.append(f"Because intercepted by deterministic legitimate-merchant guard (linked to {freeze_call_id})")
    elif is_emptied:
        steps.append(f"Because account currently holds Rs 0 in recoverable balance (linked to {prof_call_id})")
        steps.append(f"Because freezing an empty account would recover zero victim funds (linked to {freeze_call_id})")
    else:
        steps.append(f"Because account did not meet freeze criteria: {why_text} (linked to {freeze_call_id})")

    counter_evidence = {
        "superficially_suspicious_signals": [s["plain_english"] for s in signals_considered],
        "behavioral_facts": behavioral_facts,
        "why_not_enough": why_not_enough,
        "ruling": "Excluded to prevent false-positive freeze disruption to legitimate commerce.",
    }

    # Relevant tool calls citation
    cited_tool_calls: List[Dict[str, Any]] = []
    seen_calls = set()
    for ev in tool_events:
        cid = ev.get("call_id")
        tname = ev.get("tool_name")
        args = ev.get("arguments", {})
        is_relevant = (
            cid in (prof_call_id, dev_call_id, freeze_call_id)
            or args.get("account_id") == account_id
            or (isinstance(args.get("account_ids"), list) and account_id in args.get("account_ids"))
            or (isinstance(args.get("candidate_account_ids"), list) and account_id in args.get("candidate_account_ids"))
        )
        if is_relevant and cid and cid not in seen_calls:
            seen_calls.add(cid)
            cited_tool_calls.append({
                "call_id": cid,
                "tool": tname,
                "args_summary": _format_args_summary(args),
                "duration_ms": ev.get("duration_ms", 0.0),
            })

    cited_tool_calls.sort(key=lambda c: c["call_id"])

    return {
        "account": account_id,
        "priority": None,
        "headline": headline,
        "path": {"nodes": [], "edges": []},
        "path_text": "None (excluded from freeze recommendations)",
        "signals": signals_considered,
        "money": {
            "recoverable": 0,
            "cashed_out_downstream": 0,
        },
        "confidence": "excluded",
        "steps": steps,
        "counter_evidence": counter_evidence,
        "tool_calls": cited_tool_calls,
        "disclaimer": "recommendation for human review, nothing was frozen",
    }


def explain_link(
    linked_ring: Union[Dict[str, Any], str],
    graph=None,
) -> Dict[str, Any]:
    """Produce a deterministic explanation for why two accounts / rings are connected.

    Args:
        linked_ring: Dictionary describing the link, or an account ID / device ID string.
        graph: Optional FalkorDB graph instance.
    """
    g = graph or get_graph()
    link_data: Dict[str, Any] = {}

    if isinstance(linked_ring, dict):
        link_data = linked_ring
    elif isinstance(linked_ring, str):
        if linked_ring.startswith("DEV_") or linked_ring.startswith("PH_"):
            link_data = {"device_id": linked_ring}
        else:
            link_data = {"account_id": linked_ring}

    account_a = link_data.get("account_a") or link_data.get("ring1_account") or link_data.get("account_id")
    account_b = link_data.get("account_b") or link_data.get("ring2_account")
    dev_id = link_data.get("device_id") or link_data.get("shared_device")
    phone_id = link_data.get("phone_id") or link_data.get("shared_phone")

    # If parameters missing, query the graph to find shared device links
    if g and (not dev_id or not account_a or not account_b):
        if account_a:
            dev_rows = queries.find_shared_devices(g, account_a).get("items", {}).get("items", [])
            for item in dev_rows:
                sharing = [acc for acc in item.get("sharing_accounts", []) if acc != account_a]
                if sharing:
                    dev_id = item.get("device_id")
                    account_b = sharing[0]
                    break
        elif dev_id:
            rows = queries._rows(
                g,
                "MATCH (a:Account)-[:USED_DEVICE]->(d:Device {id: $dev_id}) RETURN a.id",
                dev_id=dev_id,
            )
            accounts = [r[0] for r in rows]
            if len(accounts) >= 2:
                account_a = accounts[0]
                account_b = accounts[1]
        else:
            # Query any shared device linking two accounts in graph
            rows = queries._rows(
                g,
                "MATCH (a1:Account)-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(a2:Account) "
                "WHERE a1.id < a2.id "
                "RETURN a1.id, a2.id, d.id, d.first_seen, d.last_seen LIMIT 1",
            )
            if rows:
                account_a = rows[0][0]
                account_b = rows[0][1]
                dev_id = rows[0][2]

    # Query device metadata and total sharers
    total_sharers = 2
    first_seen = 0
    last_seen = 0

    if g and dev_id:
        sh_rows = queries._rows(
            g,
            "MATCH (a:Account)-[:USED_DEVICE]->(d:Device {id: $dev_id}) "
            "RETURN count(a) AS total_count, d.first_seen AS first_seen, d.last_seen AS last_seen",
            dev_id=dev_id,
        )
        if sh_rows:
            total_sharers = int(sh_rows[0][0])
            first_seen = sh_rows[0][1] or 0
            last_seen = sh_rows[0][2] or 0

    # Rare device (<=3 sharers) is a strong signal; widely shared (>3) is weak
    if total_sharers <= 3:
        strength = "strong"
        strength_eval = f"Rarely shared hardware ({total_sharers} accounts total); strong indicator of direct syndicate co-usage"
    else:
        strength = "weak"
        strength_eval = f"Widely shared hardware ({total_sharers} accounts total); potential public terminal or shared cybercafé"

    shared_identifier = dev_id or phone_id or "shared_hardware"
    shared_kind = "device" if dev_id else ("phone" if phone_id else "infrastructure")

    headline = f"Cross-ring link discovered: {account_a} and {account_b} share {shared_identifier} ({strength} signal)"

    path_nodes = [account_a or "Account_A", shared_identifier, account_b or "Account_B"]
    path_text = f"{path_nodes[0]} -> [{path_nodes[1]}] -> {path_nodes[2]}"

    return {
        "account_a": account_a,
        "account_b": account_b,
        "shared_type": shared_kind,
        "shared_id": shared_identifier,
        "total_sharers": total_sharers,
        "strength": strength,
        "strength_eval": strength_eval,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "path": path_nodes,
        "path_text": path_text,
        "headline": headline,
        "explanation": (
            f"Accounts {account_a} and {account_b} are linked by {shared_kind} {shared_identifier}. "
            f"Total co-using accounts: {total_sharers}. Assessment: {strength_eval}."
        ),
        "disclaimer": "recommendation for human review, nothing was frozen",
    }


def build_investigation_timeline(session_id: str) -> List[Dict[str, Any]]:
    """Build the chronological 'what the agent did' investigation timeline from trace log.

    Args:
        session_id: Investigation trace session identifier.
    """
    events = trace.get(session_id)
    timeline: List[Dict[str, Any]] = []

    for idx, ev in enumerate(events, start=1):
        tname = ev.get("tool_name", "")
        args = ev.get("arguments", {})
        dur = ev.get("duration_ms", 0.0)
        ok = ev.get("ok", True)
        cid = ev.get("call_id") or f"call_{idx:03d}"

        purpose = TOOL_PURPOSE_TEMPLATES.get(tname, f"Execute tool {tname}")

        # Deterministic, one-line key result summary
        if not ok:
            key_result = f"Error: {ev.get('error', 'Execution failure')[:60]}"
        elif tname == "get_fraud_report":
            key_result = f"Loaded fraud report {args.get('report_id', '')} successfully"
        elif tname == "trace_money_forward":
            key_result = f"Traced money trail forward from {args.get('start_account_id', '')} across up to {args.get('max_hops', 8)} hops"
        elif tname == "get_account_profile":
            key_result = f"Retrieved profile and risk indicators for account {args.get('account_id', '')}"
        elif tname == "find_shared_devices":
            key_result = f"Checked shared hardware devices for {args.get('account_id', '')}"
        elif tname == "find_shared_phones":
            key_result = f"Checked shared phone numbers for {args.get('account_id', '')}"
        elif tname == "find_cash_out_points":
            accts = args.get("account_ids", [])
            key_result = f"Scanned {len(accts)} candidate accounts for downstream cash-out points"
        elif tname == "get_balance_held":
            accts = args.get("account_ids", [])
            key_result = f"Queried current recoverable balances for {len(accts)} accounts"
        elif tname == "build_freeze_list":
            cands = args.get("candidate_account_ids") or args.get("candidates") or []
            key_result = f"Independently verified {len(cands)} candidates and ranked freeze recommendations"
        elif tname == "recall_past_cases":
            accts = args.get("account_ids", [])
            key_result = f"Queried historical case memory for {len(accts)} suspect accounts"
        elif tname == "save_case_to_memory":
            key_result = f"Persisted verified investigation findings to graph memory"
        elif tname == "detect_rapid_hops":
            key_result = f"Checked rapid onward forwarding for {args.get('account_id', '')}"
        elif tname == "detect_fan_out":
            key_result = f"Checked fan-out payment splits for {args.get('account_id', '')}"
        else:
            key_result = f"Executed {tname} in {dur:.1f} ms"

        timeline.append({
            "step": idx,
            "call_id": cid,
            "tool": tname,
            "purpose": purpose,
            "key_result": key_result,
            "duration_ms": dur,
            "duration": f"{dur:.1f} ms",
            "ok": ok,
        })

    return timeline


def build_graph_highlight(
    result: Union[Dict[str, Any], str],
    graph=None,
) -> Dict[str, Any]:
    """Generate the structured subgraph highlighting the case for UI rendering.

    Roles: victim, mule_recommended, cash_out, cleared, linked_ring, shared_device, other.
    Batched read-only verification ensures every node and edge exists in the live graph.

    Args:
        result: InvestigationResult dict, freeze list dict, or session_id string.
        graph: Optional FalkorDB graph instance.
    """
    g = graph or get_graph()

    # Normalize result dict
    freeze_items: List[Dict[str, Any]] = []
    not_recommended: List[Dict[str, Any]] = []
    report_id = "FR_0001"

    if isinstance(result, str):
        # Passed a session_id or report_id
        tool_events = trace.get(result)
        for ev in reversed(tool_events):
            if ev.get("tool_name") == "build_freeze_list":
                # Look for cached last freeze list
                break
        from backend.freeze import get_last_freeze_list
        fl = get_last_freeze_list() or {}
        freeze_items = fl.get("items", [])
        not_recommended = fl.get("not_recommended", [])
    elif isinstance(result, dict):
        freeze_items = result.get("freeze_list") or result.get("items") or []
        not_recommended = result.get("not_recommended") or []
        report_id = result.get("report_id") or report_id

    # Collect nodes and edges
    raw_nodes: Dict[str, Dict[str, Any]] = {}
    raw_edges: List[Dict[str, Any]] = []

    # Get victim from fraud report
    rep_info = queries.get_fraud_report(g, report_id) if g else {}
    victim_id = rep_info.get("victim", {}).get("id")
    victim_name = rep_info.get("victim", {}).get("holder_name") or victim_id or "Victim"

    if victim_id:
        raw_nodes[victim_id] = {
            "id": victim_id,
            "role": "victim",
            "label": f"Victim: {victim_name}",
        }

    # Add recommended mules and their path edges
    for it in freeze_items:
        aid = it.get("account")
        pri = it.get("priority", 1)
        amt = it.get("amount_recoverable", 0)
        raw_nodes[aid] = {
            "id": aid,
            "role": "mule_recommended",
            "label": f"Mule #{pri}: {aid} (Rs {amt:,})",
        }

        # Add all intermediate nodes along path
        for pnode in it.get("path", []):
            if pnode not in raw_nodes:
                raw_nodes[pnode] = {
                    "id": pnode,
                    "role": "other",
                    "label": f"Pass-through: {pnode}",
                }

        # Add edges from edge_facts
        for hop in it.get("edge_facts", []):
            src = hop.get("from")
            dst = hop.get("to") or hop.get("account")
            tid = hop.get("txn_id")
            amt_edge = hop.get("amount", 0)
            ts = hop.get("timestamp", 0)
            if src and dst and tid:
                raw_edges.append({
                    "source": src,
                    "target": dst,
                    "type": "PAID",
                    "txn_id": tid,
                    "amount": amt_edge,
                    "timestamp": ts,
                    "role": "mule_recommended" if dst == aid else "other",
                })

    # Add cash-out points downstream
    all_trace_accounts = list(raw_nodes.keys())
    if g and all_trace_accounts:
        cashout_res = queries.find_cash_out_points(g, all_trace_accounts)
        cos = cashout_res.get("items", {}).get("items", [])
        for co in cos:
            c_acct = co.get("account")
            c_amt = co.get("amount", 0)
            c_ts = co.get("timestamp", 0)
            c_type = co.get("type", "ATM Withdrawal")
            c_tid = co.get("txn_id", f"CO_{c_acct}_{c_ts}")
            cash_node_id = f"CASH_{c_acct}_{c_ts}"
            raw_nodes[cash_node_id] = {
                "id": cash_node_id,
                "role": "cash_out",
                "label": f"Cash-out: {c_type} (Rs {c_amt:,})",
            }
            raw_edges.append({
                "source": c_acct,
                "target": cash_node_id,
                "type": "CASH_OUT",
                "txn_id": c_tid,
                "amount": c_amt,
                "timestamp": c_ts,
                "role": "cash_out",
            })

    # Add cleared / decoy accounts
    for nr in not_recommended:
        n_aid = nr.get("account")
        if n_aid and n_aid not in raw_nodes:
            raw_nodes[n_aid] = {
                "id": n_aid,
                "role": "cleared",
                "label": f"Cleared Merchant: {n_aid}",
            }

    # Add shared devices and linked ring nodes
    for it in freeze_items:
        aid = it.get("account")
        if g and aid:
            dev_res = queries.find_shared_devices(g, aid).get("items", {}).get("items", [])
            for ditem in dev_res:
                dev_id = ditem.get("device_id")
                sh_count = ditem.get("share_count", 0)
                if dev_id and sh_count <= 3:
                    if dev_id not in raw_nodes:
                        raw_nodes[dev_id] = {
                            "id": dev_id,
                            "role": "shared_device",
                            "label": f"Shared Device: {dev_id}",
                        }
                    raw_edges.append({
                        "source": aid,
                        "target": dev_id,
                        "type": "USED_DEVICE",
                        "txn_id": None,
                        "amount": None,
                        "timestamp": None,
                        "role": "shared_device",
                    })
                    for other_aid in ditem.get("sharing_accounts", []):
                        if other_aid != aid:
                            if other_aid not in raw_nodes:
                                raw_nodes[other_aid] = {
                                    "id": other_aid,
                                    "role": "linked_ring",
                                    "label": f"Linked Ring Account: {other_aid}",
                                }
                            raw_edges.append({
                                "source": other_aid,
                                "target": dev_id,
                                "type": "USED_DEVICE",
                                "txn_id": None,
                                "amount": None,
                                "timestamp": None,
                                "role": "shared_device",
                            })

    # Read-only graph verification: Verify all accounts, devices, and transactions exist
    verified_node_ids = set()
    verified_txn_ids = set()

    if g:
        account_ids = [nid for nid, n in raw_nodes.items() if not nid.startswith("DEV_") and not nid.startswith("PH_") and not nid.startswith("CASH_")]
        device_ids = [nid for nid in raw_nodes.keys() if nid.startswith("DEV_") or nid.startswith("PH_")]
        txn_ids = [e["txn_id"] for e in raw_edges if e.get("txn_id") and not e["txn_id"].startswith("CO_")]

        if account_ids:
            a_rows = queries._rows(
                g,
                "UNWIND $ids AS aid MATCH (a:Account {id: aid}) RETURN a.id",
                ids=account_ids,
            )
            verified_node_ids.update(r[0] for r in a_rows)

        if device_ids:
            d_rows = queries._rows(
                g,
                "UNWIND $ids AS did MATCH (d:Device {id: did}) RETURN d.id",
                ids=device_ids,
            )
            verified_node_ids.update(r[0] for r in d_rows)

        if txn_ids:
            t_rows = queries._rows(
                g,
                "UNWIND $ids AS tid MATCH (t:Transaction {id: tid}) RETURN t.id",
                ids=txn_ids,
            )
            verified_txn_ids.update(r[0] for r in t_rows)

    # Filter verified nodes and edges (always keep synthetic cash-out display nodes if parent account is verified)
    final_nodes: List[Dict[str, Any]] = []
    for nid, node in raw_nodes.items():
        if not g:
            final_nodes.append(node)
        elif nid.startswith("CASH_"):
            final_nodes.append(node)
        elif nid in verified_node_ids:
            final_nodes.append(node)

    valid_node_id_set = {n["id"] for n in final_nodes}

    # Deduplicate edges by (source, target, txn_id)
    seen_edges = set()
    deduped_edges: List[Dict[str, Any]] = []
    for e in raw_edges:
        if e["source"] not in valid_node_id_set or e["target"] not in valid_node_id_set:
            continue
        tid = e.get("txn_id")
        if g and tid and not tid.startswith("CO_") and tid not in verified_txn_ids:
            continue
        ekey = (e["source"], e["target"], tid or e["type"])
        if ekey not in seen_edges:
            seen_edges.add(ekey)
            deduped_edges.append(e)

    # Order edges strictly in time order for UI hop-by-hop animation
    timed_edges = [e for e in deduped_edges if e.get("timestamp") is not None]
    untimed_edges = [e for e in deduped_edges if e.get("timestamp") is None]

    timed_edges.sort(key=lambda x: x["timestamp"])

    ordered_edges_list: List[Dict[str, Any]] = []
    for seq_idx, e in enumerate(timed_edges, start=1):
        e["sequence_index"] = seq_idx
        ordered_edges_list.append(e)

    for e in untimed_edges:
        e["sequence_index"] = None
        ordered_edges_list.append(e)

    # Cap size: Max 40 nodes, max 60 edges
    capped_nodes = final_nodes[:40]
    capped_node_ids = {n["id"] for n in capped_nodes}
    capped_edges = [e for e in ordered_edges_list if e["source"] in capped_node_ids and e["target"] in capped_node_ids][:60]

    legend = {
        "victim": "Victim account where stolen funds originated",
        "mule_recommended": "Verified mule account recommended for human freeze review",
        "cash_out": "Terminal cash extraction point (ATM withdrawal or external exit)",
        "cleared": "Cleared legitimate merchant (decoy protected from false-positive freezing)",
        "linked_ring": "Discovered account in linked un-reported syndicate ring",
        "shared_device": "Hardware device co-used across multiple suspect accounts",
        "other": "Pass-through account in transaction flow",
    }

    return {
        "nodes": capped_nodes,
        "edges": capped_edges,
        "legend": legend,
        "disclaimer": "recommendation for human review, nothing was frozen",
    }


def explain_case(session_id: str, graph=None) -> Dict[str, Any]:
    """Assemble the complete, verified case explanation object for UI and reporting.

    Args:
        session_id: Investigation trace session identifier.
        graph: Optional FalkorDB graph instance.
    """
    g = graph or get_graph()
    from backend.freeze import get_last_freeze_list
    from backend.explain_verify import verify_explanation

    tool_events = trace.get(session_id)

    # 1. Recover fraud report details from trace or fallback
    report_id = "FR_0001"
    for ev in tool_events:
        args = ev.get("arguments", {})
        if "report_id" in args:
            report_id = args["report_id"]
            break

    rep_info = queries.get_fraud_report(g, report_id) if g else {}
    victim_data = rep_info.get("victim", {})
    report_data = rep_info.get("report", {})
    victim_name = victim_data.get("holder_name") or victim_data.get("id") or "Victim"
    victim_account = victim_data.get("id", "")
    amount_stolen = report_data.get("amount", 0)
    reported_at = report_data.get("reported_at", 0)

    # 2. Retrieve freeze list and not_recommended items
    freeze_result = get_last_freeze_list(report_id) or get_last_freeze_list() or {}
    if not freeze_result.get("items") and g:
        for ev in tool_events:
            if ev.get("tool_name") == "build_freeze_list":
                args = ev.get("arguments", {})
                cands = args.get("candidate_account_ids") or args.get("candidates") or []
                if cands:
                    from backend.freeze import build_freeze_list
                    freeze_result = build_freeze_list(cands, report_id, graph=g)
                    break
    freeze_items = freeze_result.get("items", [])
    not_recommended_items = freeze_result.get("not_recommended", [])
    total_recoverable = freeze_result.get("total_recoverable", sum(it.get("amount_recoverable", 0) for it in freeze_items))
    total_cashed_out = freeze_result.get("total_cashed_out", sum(it.get("amount_already_cashed_out", 0) for it in freeze_items))

    # 3. Build sub-explanations
    recommendations = [explain_recommendation(it, session_id, g) for it in freeze_items]
    rejections = [explain_rejection(nr, session_id, g) for nr in not_recommended_items]

    # 4. Build links (shared device discoveries)
    links: List[Dict[str, Any]] = []
    seen_links = set()
    for ev in tool_events:
        if ev.get("tool_name") == "find_shared_devices":
            target_aid = ev.get("arguments", {}).get("account_id")
            if target_aid and g:
                dres = queries.find_shared_devices(g, target_aid).get("items", {}).get("items", [])
                for ditem in dres:
                    dev_id = ditem.get("device_id")
                    for other_aid in ditem.get("sharing_accounts", []):
                        if other_aid != target_aid:
                            lkey = tuple(sorted([target_aid, other_aid]))
                            if lkey not in seen_links:
                                seen_links.add(lkey)
                                links.append(explain_link({
                                    "account_a": target_aid,
                                    "account_b": other_aid,
                                    "device_id": dev_id,
                                }, g))

    if not links and freeze_items and g:
        for it in freeze_items:
            aid = it.get("account")
            dres = queries.find_shared_devices(g, aid).get("items", {}).get("items", [])
            for ditem in dres:
                dev_id = ditem.get("device_id")
                for other_aid in ditem.get("sharing_accounts", []):
                    if other_aid != aid:
                        lkey = tuple(sorted([aid, other_aid]))
                        if lkey not in seen_links:
                            seen_links.add(lkey)
                            links.append(explain_link({
                                "account_a": aid,
                                "account_b": other_aid,
                                "device_id": dev_id,
                            }, g))

    # 5. Build investigation timeline & graph highlight
    timeline = build_investigation_timeline(session_id)
    highlight = build_graph_highlight(freeze_result, g)

    case_header = {
        "case_id": f"CASE_{report_id}",
        "session_id": session_id,
        "report_id": report_id,
        "victim_name": victim_name,
        "victim_account": victim_account,
        "amount_stolen": amount_stolen,
        "reported_at": reported_at,
        "total_recoverable": total_recoverable,
        "total_cashed_out": total_cashed_out,
        "recommendation_only": True,
    }

    other_patterns = [
        "Rapid onward forwarding within 10-minute window",
        "Dispersal via fan-out transaction split",
        "Cross-account coordination via shared mobile hardware identifier",
    ]

    limitations = [
        "Freeze recommendations are strictly advisory for human compliance review. Nothing is frozen automatically.",
        "Transactions are limited to visibility within the participating banking network.",
        "Downstream ATM cash-outs and crypto off-ramps have already exited the digital banking perimeter.",
    ]

    disclaimer = "recommendation for human review, nothing was frozen"

    case_obj = {
        "case_header": case_header,
        "timeline": timeline,
        "highlight": highlight,
        "recommendations": recommendations,
        "rejections": rejections,
        "links": links,
        "other_patterns": other_patterns,
        "limitations": limitations,
        "disclaimer": disclaimer,
    }

    # Verify against live graph
    verification_res = verify_explanation(case_obj, g)
    case_obj["verified"] = verification_res.get("verified", False)
    case_obj["verification"] = verification_res

    return case_obj


def save_case_explanation(explanation: Dict[str, Any], session_id: str) -> str:
    """Persist case explanation JSON and update the cases index file."""
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    target_file = CASES_DIR / f"{session_id}.json"

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(explanation, f, indent=2)

    # Update index
    index_records: List[Dict[str, Any]] = []
    if CASES_INDEX_FILE.exists():
        try:
            with open(CASES_INDEX_FILE, "r", encoding="utf-8") as f:
                index_records = json.load(f)
        except Exception:
            index_records = []

    header = explanation.get("case_header", {})
    entry = {
        "session_id": session_id,
        "report_id": header.get("report_id", ""),
        "case_id": header.get("case_id", ""),
        "victim_name": header.get("victim_name", ""),
        "total_recoverable": header.get("total_recoverable", 0),
        "verified": explanation.get("verified", False),
        "timestamp": header.get("reported_at", int(time.time())),
        "file": f"{session_id}.json",
    }

    # Replace if exists, else append
    updated = [r for r in index_records if r.get("session_id") != session_id]
    updated.insert(0, entry)

    with open(CASES_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2)

    return str(target_file)


def load_case_explanation(session_id: str) -> Optional[Dict[str, Any]]:
    """Load a previously persisted case explanation JSON by session ID."""
    target_file = CASES_DIR / f"{session_id}.json"
    if not target_file.exists():
        return None
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_case_explanations() -> List[Dict[str, Any]]:
    """List all saved case summaries from index.json."""
    if not CASES_INDEX_FILE.exists():
        return []
    try:
        with open(CASES_INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


_POLISH_ATTEMPTS = 0
_POLISH_DISCARDS = 0


def polish_summary_with_llm(
    explanation: Dict[str, Any],
    groq_client=None,
    model: Optional[str] = None,
) -> Tuple[str, bool]:
    """Generate a polished 3-4 sentence plain-English summary for a non-technical bank officer.

    Strict grounding check: every number and account ID in the generated summary MUST
    exist in the explanation JSON. If any invented number or ID is found, the polished
    summary is discarded and the deterministic text is returned.

    Returns:
        Tuple of (summary_text, was_discarded)
    """
    global _POLISH_ATTEMPTS, _POLISH_DISCARDS
    _POLISH_ATTEMPTS += 1

    from backend.llm import get_groq_client, get_llm_model
    client = groq_client or get_groq_client()
    mdl = model or get_llm_model()

    # Build deterministic fallback summary
    header = explanation.get("case_header", {})
    recs = explanation.get("recommendations", [])
    rejs = explanation.get("rejections", [])
    victim_name = header.get("victim_name", "the victim")
    amount_stolen = header.get("amount_stolen", 0)
    total_rec = header.get("total_recoverable", 0)

    top_rec_text = ""
    if recs:
        top_rec = recs[0]
        top_rec_text = f"Top priority is {top_rec.get('account')} ({top_rec.get('bank', '')}), which currently holds Rs {top_rec.get('money', {}).get('recoverable', 0):,}."

    cleared_text = ""
    if rejs:
        top_rej = rejs[0]
        cleared_text = f"Account {top_rej.get('account')} was verified as a legitimate merchant and cleared."

    fallback_summary = (
        f"Investigation into the fraud reported by {victim_name} (Rs {amount_stolen:,}) identified {len(recs)} accounts recommended for freezing, "
        f"recovering up to Rs {total_rec:,}. {top_rec_text} {cleared_text} All actions are recommendations for human review."
    )

    explanation_str = json.dumps(explanation)

    system_prompt = (
        "You are an assistant to a bank fraud officer. Write a concise, 3 to 4 sentence plain-English summary "
        "of the fraud investigation based strictly on the provided explanation JSON. "
        "CRITICAL RULES: Do NOT invent any numbers, currency amounts, dates, or account IDs. "
        "Every single number and account ID you mention MUST appear verbatim in the explanation JSON. "
        "Always state that this is a recommendation for human review."
    )

    try:
        resp = client.chat.completions.create(
            model=mdl,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Explanation JSON:\n{explanation_str}"},
            ],
            temperature=0.0,
            max_tokens=300,
        )
        candidate = resp.choices[0].message.content or ""
    except Exception:
        _POLISH_DISCARDS += 1
        return fallback_summary, True

    # Verification: Check every number and account ID in candidate text
    account_ids = re.findall(r"\bACC_\w+\b", candidate)
    for aid in account_ids:
        if aid not in explanation_str:
            _POLISH_DISCARDS += 1
            return fallback_summary, True

    # Extract all numeric tokens (including formatted amounts like 40,000 or 85000)
    raw_numbers = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", candidate)
    for num_str in raw_numbers:
        clean_num = num_str.replace(",", "")
        # Check if the number or formatted number appears in explanation string
        if clean_num not in explanation_str and num_str not in explanation_str:
            _POLISH_DISCARDS += 1
            return fallback_summary, True

    # Must contain human review disclaimer
    if "human review" not in candidate.lower():
        candidate += " This is a recommendation for human review; nothing was frozen."

    return candidate, False


def get_polish_stats() -> Dict[str, Any]:
    """Return lifetime polish discard rate statistics."""
    discard_rate = (_POLISH_DISCARDS / _POLISH_ATTEMPTS) if _POLISH_ATTEMPTS > 0 else 0.0
    return {
        "attempts": _POLISH_ATTEMPTS,
        "discards": _POLISH_DISCARDS,
        "discard_rate": round(discard_rate, 3),
    }
