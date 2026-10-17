"""Verification engine for MuleTrace explanations (Phase 12).

Re-checks an explanation against the live FalkorDB graph and the session trace log:
1. Every account named in recommendations and rejections exists in the graph.
2. Every txn_id exists in the graph.
3. Amounts and timestamps on each hop match the graph transaction record.
4. Timestamps strictly increase along each recommendation path.
5. Every cited call_id exists in the trace log for that session.
6. The sum of recoverable amounts in recommendations equals the freeze-list total.

Exposes:
  verify_explanation(explanation, graph=None) -> dict
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from backend.db import get_graph
from backend import queries
from backend.tools import trace


def verify_explanation(
    explanation: Dict[str, Any],
    graph=None,
) -> Dict[str, Any]:
    """Independently verify an explanation against live graph data and trace log.

    Returns:
        Dict containing verified boolean, badge string, passed count, total checks,
        and list of failed items if any.
    """
    g = graph or get_graph()
    passed_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []

    case_header = explanation.get("case_header", {})
    session_id = case_header.get("session_id") or explanation.get("session_id", "default")
    recommendations = explanation.get("recommendations", [])
    rejections = explanation.get("rejections", [])
    links = explanation.get("links", [])
    timeline = explanation.get("timeline", [])

    # -------------------------------------------------------------------------
    # 1. Verify all named accounts exist in graph
    # -------------------------------------------------------------------------
    account_ids_to_check: Set[str] = set()

    # Victim account
    victim_aid = case_header.get("victim_account")
    if victim_aid:
        account_ids_to_check.add(victim_aid)

    # Recommendation accounts and path nodes
    for rec in recommendations:
        aid = rec.get("account")
        if aid:
            account_ids_to_check.add(aid)
        path_obj = rec.get("path", {})
        if isinstance(path_obj, dict):
            for n in path_obj.get("nodes", []):
                nid = n.get("id") if isinstance(n, dict) else n
                if nid and not nid.startswith("CASH_") and not nid.startswith("DEV_") and not nid.startswith("PH_"):
                    account_ids_to_check.add(nid)
        elif isinstance(path_obj, list):
            for n in path_obj:
                nid = n.get("id") if isinstance(n, dict) else n
                if isinstance(nid, str) and not nid.startswith("CASH_") and not nid.startswith("DEV_") and not nid.startswith("PH_"):
                    account_ids_to_check.add(nid)

    # Rejection accounts
    for rej in rejections:
        raid = rej.get("account")
        if raid:
            account_ids_to_check.add(raid)

    # Link accounts
    for lk in links:
        if lk.get("account_a"):
            account_ids_to_check.add(lk["account_a"])
        if lk.get("account_b"):
            account_ids_to_check.add(lk["account_b"])

    # Batch query account existence
    if g and account_ids_to_check:
        found_rows = queries._rows(
            g,
            "UNWIND $ids AS aid MATCH (a:Account {id: aid}) RETURN a.id",
            ids=list(account_ids_to_check),
        )
        existing_accounts = {r[0] for r in found_rows}
        for aid in sorted(account_ids_to_check):
            if aid in existing_accounts:
                passed_items.append({"check": "account_exists", "id": aid, "status": "PASS"})
            else:
                failed_items.append({
                    "check": "account_exists",
                    "id": aid,
                    "reason": f"Account '{aid}' does not exist in live graph",
                })

    # -------------------------------------------------------------------------
    # 2. Verify all txn_ids exist, and amounts/timestamps match graph records
    # -------------------------------------------------------------------------
    hops_to_check: List[Dict[str, Any]] = []
    for rec in recommendations:
        path_obj = rec.get("path", {})
        edges = path_obj.get("edges", []) if isinstance(path_obj, dict) else (path_obj if isinstance(path_obj, list) else [])
        for edge in edges:
            tid = edge.get("txn_id")
            if tid and not tid.startswith("CO_"):
                hops_to_check.append({
                    "account": rec.get("account"),
                    "txn_id": tid,
                    "expected_amount": edge.get("amount"),
                    "expected_timestamp": edge.get("timestamp"),
                })

    if g and hops_to_check:
        tids = [h["txn_id"] for h in hops_to_check]
        t_rows = queries._rows(
            g,
            "UNWIND $ids AS tid MATCH (t:Transaction {id: tid}) RETURN t.id, t.amount, t.timestamp",
            ids=tids,
        )
        tx_map = {r[0]: (r[1], r[2]) for r in t_rows}

        for h in hops_to_check:
            tid = h["txn_id"]
            if tid not in tx_map:
                failed_items.append({
                    "check": "txn_exists",
                    "txn_id": tid,
                    "account": h["account"],
                    "reason": f"Transaction '{tid}' does not exist in live graph",
                })
            else:
                passed_items.append({"check": "txn_exists", "txn_id": tid, "status": "PASS"})
                real_amt, real_ts = tx_map[tid]
                exp_amt = h["expected_amount"]
                exp_ts = h["expected_timestamp"]

                if exp_amt is not None and exp_amt != real_amt:
                    failed_items.append({
                        "check": "txn_amount_match",
                        "txn_id": tid,
                        "reason": f"Transaction '{tid}' amount mismatch: explanation has {exp_amt}, live graph has {real_amt}",
                    })
                elif exp_amt is not None:
                    passed_items.append({"check": "txn_amount_match", "txn_id": tid, "status": "PASS"})

                if exp_ts is not None and exp_ts != real_ts:
                    failed_items.append({
                        "check": "txn_timestamp_match",
                        "txn_id": tid,
                        "reason": f"Transaction '{tid}' timestamp mismatch: explanation has {exp_ts}, live graph has {real_ts}",
                    })
                elif exp_ts is not None:
                    passed_items.append({"check": "txn_timestamp_match", "txn_id": tid, "status": "PASS"})

    # -------------------------------------------------------------------------
    # 3. Timestamps strictly increase along each recommendation path
    # -------------------------------------------------------------------------
    for rec in recommendations:
        aid = rec.get("account", "unknown")
        path_obj = rec.get("path", {})
        edges = path_obj.get("edges", []) if isinstance(path_obj, dict) else (path_obj if isinstance(path_obj, list) else [])
        if len(edges) >= 2:
            prev_ts = -1
            strictly_increasing = True
            for idx, edge in enumerate(edges):
                curr_ts = edge.get("timestamp", 0)
                if curr_ts <= prev_ts:
                    strictly_increasing = False
                    failed_items.append({
                        "check": "timestamp_monotonicity",
                        "account": aid,
                        "edge_index": idx,
                        "reason": f"Path for '{aid}' violates strict time ordering: timestamp {curr_ts} <= preceding {prev_ts}",
                    })
                    break
                prev_ts = curr_ts
            if strictly_increasing:
                passed_items.append({
                    "check": "timestamp_monotonicity",
                    "account": aid,
                    "status": "PASS",
                })

    # -------------------------------------------------------------------------
    # 4. Every cited call_id exists in the trace log for that session
    # -------------------------------------------------------------------------
    trace_events = trace.get(session_id)
    valid_cids: Set[str] = {ev.get("call_id") for ev in trace_events if ev.get("call_id")}

    cited_cids: Set[str] = set()

    for rec in recommendations:
        for sig in rec.get("signals", []):
            cid = sig.get("evidence_call_id")
            if cid:
                cited_cids.add(cid)
        for st in rec.get("steps", []):
            found_cids = re.findall(r"\bcall_\d+\b", st)
            cited_cids.update(found_cids)
        for tc in rec.get("tool_calls", []):
            cid = tc.get("call_id")
            if cid:
                cited_cids.add(cid)

    for rej in rejections:
        for sig in rej.get("signals", []):
            cid = sig.get("evidence_call_id")
            if cid:
                cited_cids.add(cid)
        for st in rej.get("steps", []):
            found_cids = re.findall(r"\bcall_\d+\b", st)
            cited_cids.update(found_cids)
        for tc in rej.get("tool_calls", []):
            cid = tc.get("call_id")
            if cid:
                cited_cids.add(cid)

    for tl in timeline:
        cid = tl.get("call_id")
        if cid:
            cited_cids.add(cid)

    # Check cited call IDs
    if valid_cids:
        for cid in sorted(cited_cids):
            if cid in valid_cids:
                passed_items.append({"check": "call_id_exists", "call_id": cid, "status": "PASS"})
            else:
                failed_items.append({
                    "check": "call_id_exists",
                    "call_id": cid,
                    "reason": f"Cited call_id '{cid}' was not found in trace log for session '{session_id}'",
                })
    elif cited_cids:
        # If trace log is entirely empty, flag missing trace log
        for cid in sorted(cited_cids):
            failed_items.append({
                "check": "call_id_exists",
                "call_id": cid,
                "reason": f"Trace log for session '{session_id}' is empty; cannot verify call_id '{cid}'",
            })

    # -------------------------------------------------------------------------
    # 5. Sum of recoverable amounts equals freeze-list total
    # -------------------------------------------------------------------------
    expected_total = case_header.get("total_recoverable", 0)
    actual_sum = 0
    for rec in recommendations:
        m = rec.get("money", {})
        actual_sum += m.get("recoverable", 0)

    if actual_sum == expected_total:
        passed_items.append({
            "check": "recoverable_sum_match",
            "amount": actual_sum,
            "status": "PASS",
        })
    else:
        failed_items.append({
            "check": "recoverable_sum_match",
            "expected": expected_total,
            "actual": actual_sum,
            "reason": f"Sum of recoverable balances (Rs {actual_sum:,}) does not equal total_recoverable (Rs {expected_total:,})",
        })

    is_verified = (len(failed_items) == 0)
    badge = "verified: true" if is_verified else "verified: false"

    return {
        "verified": is_verified,
        "badge": badge,
        "checks_passed": len(passed_items),
        "total_checks": len(passed_items) + len(failed_items),
        "failed_items": failed_items,
        "passed_items": passed_items,
    }
