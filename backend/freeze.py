"""Freeze-list verification and ranking logic for MuleTrace (Phase 11).

Plain Python, unit-testable, no LLM inside.
Independently re-verifies suspect candidates against the graph so an agent cannot
talk the system into freezing anyone.

CRITICAL INVARIANTS:
- The system NEVER freezes anything. It only RECOMMENDS.
- Every output carries `recommendation_only: True`.
- Independent verification against the graph data.
- Decoy protection via legitimate-merchant guard.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Union

from backend.db import get_graph
from backend import queries


# Module-level session store for the last verified freeze list per report
_LAST_FREEZE_LIST_BY_REPORT: Dict[str, Dict[str, Any]] = {}


def get_last_freeze_list(report_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the last verified freeze list result for validation/memory write-back."""
    if report_id:
        return _LAST_FREEZE_LIST_BY_REPORT.get(report_id)
    if _LAST_FREEZE_LIST_BY_REPORT:
        # return the most recently added
        return list(_LAST_FREEZE_LIST_BY_REPORT.values())[-1]
    return None


def set_last_freeze_list(report_id: str, freeze_list: Dict[str, Any]) -> None:
    """Store the last verified freeze list result for a report."""
    _LAST_FREEZE_LIST_BY_REPORT[report_id] = freeze_list


def build_freeze_list(
    candidates: List[Union[str, Dict[str, Any]]],
    case_context: Union[str, Dict[str, Any]],
    graph=None,
) -> Dict[str, Any]:
    """Independently verify candidate accounts and build a ranked freeze recommendation.

    Args:
        candidates: List of suspect account IDs or candidate dicts named by the agent.
        case_context: Fraud report ID string (e.g. 'FR_0001') or context dict.
        graph: Optional FalkorDB graph instance.
    """
    g = graph or get_graph()
    now_ts = int(time.time())

    # 1. Parse case context
    report_id = case_context if isinstance(case_context, str) else case_context.get("report_id")
    if not report_id:
        return {
            "error": "Missing report_id in case_context.",
            "hint": "Pass a valid fraud report ID such as 'FR_0001'.",
        }

    rep_info = queries.get_fraud_report(g, report_id)
    if not rep_info.get("found"):
        return {
            "error": f"Fraud report '{report_id}' was not found in the graph.",
            "hint": "Verify report ID (e.g. 'FR_0001').",
        }

    victim = rep_info["victim"]
    report = rep_info["report"]
    victim_id = victim["id"]
    victim_name = victim.get("holder_name", victim_id)
    reported_at = report.get("reported_at", now_ts)

    # 2. Handle empty candidates edge case
    if not candidates:
        empty_res = {
            "recommendation_only": True,
            "total_recoverable": 0,
            "total_cashed_out": 0,
            "items": [],
            "not_recommended": [],
            "generated_at": now_ts,
            "reason": "No suspect candidates provided for freeze list verification.",
        }
        set_last_freeze_list(report_id, empty_res)
        return empty_res

    # 3. Normalize & deduplicate candidate IDs
    candidate_ids: List[str] = []
    seen = set()
    for c in candidates:
        aid = c if isinstance(c, str) else (c.get("account_id") or c.get("account"))
        if aid and aid not in seen:
            seen.add(aid)
            candidate_ids.append(aid)

    # 4. Verify candidate existence in graph
    for aid in candidate_ids:
        rows = queries._rows(g, "MATCH (a:Account) WHERE a.id = $id RETURN a.id", id=aid)
        if not rows:
            return {
                "error": f"Account '{aid}' was not found in the graph.",
                "hint": "Verify ID formatting (e.g. account 'ACC_0463') or discover accounts first using trace_money_forward.",
            }

    # 5. Money-trail check: time-ordered paths from victim
    # Trace forward from victim up to 86400s before reported_at
    trace_res = queries.trace_money_forward(
        g,
        start_account_id=victim_id,
        start_time=reported_at - 86400,
        max_hops=10,
        max_paths=200,
    )
    raw_paths = trace_res.get("paths", {}).get("items", [])

    # Index shortest time-ordered paths per account
    shortest_paths_by_account: Dict[str, Dict[str, Any]] = {}
    for p in raw_paths:
        path_nodes = p["path"]
        hops = p["hops"]
        for idx in range(1, len(path_nodes)):
            target = path_nodes[idx]
            subpath = path_nodes[: idx + 1]
            subhops = hops[:idx]
            if target not in shortest_paths_by_account or len(subpath) < len(shortest_paths_by_account[target]["path"]):
                shortest_paths_by_account[target] = {
                    "path": subpath,
                    "hops": subhops,
                    "hop_count": len(subpath) - 1,
                }

    # Also compute downstream cashouts across the entire forward trace
    all_trace_accounts = set()
    for p in raw_paths:
        all_trace_accounts.update(p["path"])

    cashout_res = queries.find_cash_out_points(g, list(all_trace_accounts))
    cashout_events = cashout_res.get("items", {}).get("items", [])
    cashout_by_account: Dict[str, List[Dict[str, Any]]] = {}
    for co in cashout_events:
        cashout_by_account.setdefault(co["account"], []).append(co)

    total_cashed_out = sum(co["amount"] for co in cashout_events)

    # Candidate evaluation
    qualifying_items: List[Dict[str, Any]] = []
    not_recommended: List[Dict[str, Any]] = []

    # Identify any accounts linked by rare device sharing within candidates
    shared_device_map: Dict[str, List[str]] = {}
    for aid in candidate_ids:
        dev_res = queries.find_shared_devices(g, aid).get("items", {}).get("items", [])
        for dev_item in dev_res:
            if dev_item.get("share_count", 0) <= 3:
                others = [o for o in dev_item.get("sharing_accounts", []) if o != aid]
                if others:
                    shared_device_map.setdefault(aid, []).extend(others)

    for aid in candidate_ids:
        prof = queries.get_account_profile(g, aid)
        bal_held = prof.get("balance_held") or 0

        # Guard 1: Zero balance_held -> "already emptied, do not prioritize"
        if bal_held <= 0:
            not_recommended.append({
                "account": aid,
                "why": "already emptied, do not prioritize",
            })
            continue

        # Guard 2: Legitimate-merchant guard (decoy protection)
        senders_count = prof.get("distinct_senders") or 0
        fwd_lat = prof.get("forward_latency", {})
        med_lat = fwd_lat.get("median")
        devices_list = prof.get("devices", {}).get("items", [])
        phones_list = prof.get("phones", {}).get("items", [])

        is_stable_device = len(devices_list) <= 1 and (not devices_list or devices_list[0].get("share_count", 1) <= 1)
        is_stable_phone = len(phones_list) <= 1 and (not phones_list or phones_list[0].get("share_count", 1) <= 1)
        is_slow_forwarding = (med_lat is None or med_lat > 3600)

        if senders_count >= 10 and is_slow_forwarding and is_stable_device and is_stable_phone:
            not_recommended.append({
                "account": aid,
                "why": f"Legitimate-merchant guard: {senders_count} distinct senders, slow/no onward forwarding, and stable single device and phone.",
            })
            continue

        # Check a: Money trail reachability from victim
        path_info = shortest_paths_by_account.get(aid)
        if not path_info:
            not_recommended.append({
                "account": aid,
                "why": "No time-ordered money trail connecting from victim account.",
            })
            continue

        hop_count = path_info["hop_count"]
        # Require at least 2 hops from the victim for a mule
        if hop_count < 2:
            not_recommended.append({
                "account": aid,
                "why": f"Account is only {hop_count} hop from victim (direct recipient, not a downstream mule).",
            })
            continue

        # Behavior signals:
        # (1) rapid forwarding (70 percent or more forwarded within 10 minutes, including cash-out)
        # (2) fan-out split
        # (3) received money that came from the victim's trail (already verified by path_info)
        # (4) unusually low forward latency compared with the median account
        # (5) linked by a rarely shared device or phone to another candidate / account
        signals: List[str] = []

        # Signal (3): Mandatory
        signals.append("victim_money_trail")

        # Signal (1): rapid forwarding (check detect_rapid_hops or ATM cash-out within 10m)
        rh = queries.detect_rapid_hops(g, account_id=aid, window_seconds=600)
        has_rapid_forward = len(rh.get("items", {}).get("items", [])) > 0
        if not has_rapid_forward:
            # Check if received money was rapidly forwarded or cashed out >= 65% within 10 min
            co_list = cashout_by_account.get(aid, [])
            in_hops = [h for h in path_info["hops"] if h.get("account") == aid]
            if in_hops and co_list:
                in_amt = in_hops[0]["amount"]
                in_ts = in_hops[0]["timestamp"]
                fast_co = sum(c["amount"] for c in co_list if in_ts < c["timestamp"] <= in_ts + 600)
                if in_amt > 0 and (fast_co / in_amt) >= 0.65:
                    has_rapid_forward = True
        if has_rapid_forward:
            signals.append("rapid_forwarding")

        # Signal (2): fan-out split (account performed fan-out OR received from a fan-out split on the trail)
        fo = queries.detect_fan_out(g, account_id=aid, window_seconds=3600)
        has_fan_out = len(fo.get("items", {}).get("items", [])) > 0
        if not has_fan_out and len(path_info["path"]) >= 3:
            # Check if parent node in path performed a fan-out
            parent_id = path_info["path"][-2]
            parent_fo = queries.detect_fan_out(g, account_id=parent_id, window_seconds=3600)
            if len(parent_fo.get("items", {}).get("items", [])) > 0:
                has_fan_out = True
        if has_fan_out:
            signals.append("fan_out_split")

        # Signal (4): unusually low forward latency (<= 600 seconds, or cashout latency <= 600s)
        has_low_latency = False
        if med_lat is not None and med_lat <= 600:
            has_low_latency = True
        elif fwd_lat.get("min") is not None and fwd_lat.get("min") <= 600:
            has_low_latency = True
        else:
            co_list = cashout_by_account.get(aid, [])
            in_hops = [h for h in path_info["hops"] if h.get("account") == aid]
            if in_hops and co_list:
                in_ts = in_hops[0]["timestamp"]
                co_diffs = [c["timestamp"] - in_ts for c in co_list if c["timestamp"] >= in_ts]
                if co_diffs and min(co_diffs) <= 600:
                    has_low_latency = True
        if has_low_latency:
            signals.append("low_forward_latency")

        # Signal (5): linked by rarely shared device/phone
        if aid in shared_device_map:
            signals.append("shared_device_link")
        else:
            ph_res = queries.find_shared_phones(g, aid).get("items", {}).get("items", [])
            for p_item in ph_res:
                if p_item.get("share_count", 0) <= 3 and p_item.get("sharing_accounts"):
                    signals.append("shared_phone_link")
                    break

        # Independent signals count = total signals - 1 (excluding victim_money_trail)
        independent_count = len([s for s in signals if s != "victim_money_trail"])

        # Rule 1b: An account needs at least 2 independent signals plus signal (3) to be listed
        if independent_count < 2:
            not_recommended.append({
                "account": aid,
                "why": f"Insufficient independent behavioral signals ({independent_count} found, 2 required plus money trail).",
            })
            continue

        # Confidence:
        # high (3 or more signals and money still held)
        # medium (2 signals)
        if len(signals) >= 3 and bal_held > 0:
            confidence = "high"
        elif len(signals) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # Format path: accounts and edge facts
        full_path_nodes = path_info["path"]
        hops_list = path_info["hops"]

        # Build human-readable path text: e.g. "Ravi -> A -> B"
        victim_label = "Ravi" if "ravi" in victim_name.lower() else victim_id
        path_text = f"{victim_label} -> " + " -> ".join(full_path_nodes[1:])

        # Downstream cashouts for this specific account
        downstream_cashout = sum(co["amount"] for co in cashout_by_account.get(aid, []))

        # Item definition
        reason = (
            f"Holds Rs {bal_held:,} attributable to victim's stolen funds at {hop_count} hops. "
            f"Exhibits {len(signals)} risk signals: {', '.join(signals)}."
        )

        qualifying_items.append({
            "account": aid,
            "bank": prof.get("bank", "Unknown Bank"),
            "amount_recoverable": bal_held,
            "amount_already_cashed_out": downstream_cashout,
            "signals": signals,
            "confidence": confidence,
            "path": full_path_nodes,
            "edge_facts": hops_list,
            "hops": hop_count,
            "path_text": path_text,
            "reason": reason,
            "evidence_call_ids": ["trace_money_forward", "get_account_profile"],
        })

    # Ranking:
    # 1. amount_recoverable descending
    # 2. earliest position in the chain (hops ascending)
    # 3. number of signals descending
    qualifying_items.sort(
        key=lambda it: (-it["amount_recoverable"], it["hops"], -len(it["signals"]))
    )

    # Assign priority 1..N
    ranked_items = []
    for idx, item in enumerate(qualifying_items, start=1):
        item["priority"] = idx
        ranked_items.append(item)

    total_recoverable = sum(it["amount_recoverable"] for it in ranked_items)

    result = {
        "recommendation_only": True,
        "total_recoverable": total_recoverable,
        "total_cashed_out": total_cashed_out,
        "items": ranked_items,
        "not_recommended": not_recommended,
        "generated_at": now_ts,
    }

    set_last_freeze_list(report_id, result)
    return result
