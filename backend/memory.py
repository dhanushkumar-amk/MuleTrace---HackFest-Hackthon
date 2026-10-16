"""Memory write-back and historical recall system for MuleTrace (Phase 11, Track 02 bonus).

Allows the agent to remember past fraud investigations by writing Case nodes,
FLAGGED_IN edges to FraudReports, and INVOLVES / LINKED_TO edges across cases.

CRITICAL INVARIANTS:
- Writes only: Case node, FLAGGED_IN, INVOLVES, LINKED_TO, Account.is_flagged, Account.risk_score.
- NEVER writes forbidden labels or properties (mule, decoy, ring_id, plant).
- Idempotent: MERGE on ids.
- Only accounts approved by the last build_freeze_list result can be saved.
- recall_past_cases queries past cases via direct account or shared device/phone links.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from backend.db import get_graph
from backend import queries
from backend.freeze import get_last_freeze_list


FORBIDDEN_PROPERTY_SUBSTRINGS = ("ring", "mule", "decoy", "plant")


def save_case_to_memory(
    graph,
    report_id: str,
    summary: str,
    account_ids: Optional[List[str]] = None,
    status: str = "COMPLETED",
) -> Dict[str, Any]:
    """Persist verified investigation findings to the FalkorDB graph memory.

    Args:
        graph: FalkorDB Graph instance.
        report_id: Fraud report ID string (e.g. 'FR_0001').
        summary: High-level factual narrative of the case.
        account_ids: Optional subset of candidate accounts to flag. If omitted,
                     all accounts from the last build_freeze_list result are saved.
        status: Case outcome status (default 'COMPLETED').
    """
    g = graph or get_graph()
    now_ts = int(time.time())

    # 1. Retrieve the last verified freeze list for this report
    last_freeze = get_last_freeze_list(report_id)
    if not last_freeze or not last_freeze.get("items"):
        return {
            "error": f"No verified freeze list found for report '{report_id}' in the current session.",
            "hint": "You must call build_freeze_list first before saving case memory.",
        }

    # Map approved accounts
    approved_map = {it["account"]: it for it in last_freeze["items"]}

    target_accounts: List[Dict[str, Any]] = []
    if account_ids:
        for aid in account_ids:
            if aid not in approved_map:
                return {
                    "error": f"Account '{aid}' was not in the verified freeze list recommendation.",
                    "hint": f"Only accounts approved by build_freeze_list may be saved. Approved accounts: {list(approved_map.keys())}",
                }
            target_accounts.append(approved_map[aid])
    else:
        target_accounts = list(approved_map.values())

    # 2. Case node (MERGE on id)
    case_id = f"CASE_{report_id}"
    queries._rows(
        g,
        "MERGE (c:Case {id: $case_id}) "
        "SET c.report_id = $report_id, "
        "    c.created_at = $created_at, "
        "    c.summary = $summary, "
        "    c.status = $status",
        case_id=case_id,
        report_id=report_id,
        created_at=now_ts,
        summary=summary,
        status=status,
    )

    # 3. For each approved account: INVOLVES edge, FLAGGED_IN edge, and Account properties
    for item in target_accounts:
        aid = item["account"]
        conf = item.get("confidence", "high")
        priority = int(item.get("priority", 1))
        amt = int(item.get("amount_recoverable", 0))
        signals_list = item.get("signals", [])
        signals_str = ", ".join(signals_list)

        # Compute risk score (number between 0 and 1)
        if conf == "high":
            risk_score = round(min(0.99, 0.80 + len(signals_list) * 0.05), 2)
        elif conf == "medium":
            risk_score = 0.60
        else:
            risk_score = 0.30

        # MERGE (Case)-[:INVOLVES]->(Account)
        queries._rows(
            g,
            "MATCH (c:Case {id: $case_id}), (a:Account {id: $aid}) "
            "MERGE (c)-[:INVOLVES]->(a)",
            case_id=case_id,
            aid=aid,
        )

        # MERGE (Account)-[:FLAGGED_IN]->(FraudReport)
        queries._rows(
            g,
            "MATCH (a:Account {id: $aid}), (fr:FraudReport {id: $report_id}) "
            "MERGE (a)-[f:FLAGGED_IN]->(fr) "
            "SET f.confidence = $conf, "
            "    f.priority = $priority, "
            "    f.amount_recoverable = $amt, "
            "    f.signals = $signals_str, "
            "    f.at = $now_ts",
            aid=aid,
            report_id=report_id,
            conf=conf,
            priority=priority,
            amt=amt,
            signals_str=signals_str,
            now_ts=now_ts,
        )

        # Update Account.is_flagged and Account.risk_score
        queries._rows(
            g,
            "MATCH (a:Account {id: $aid}) "
            "SET a.is_flagged = true, a.risk_score = $risk",
            aid=aid,
            risk=risk_score,
        )

    # 4. Link to earlier cases: (Case)-[:LINKED_TO]->(earlierCase)
    # Check if accounts involved, or accounts sharing devices/phones with them, are in earlier cases
    target_aids = [it["account"] for it in target_accounts]
    linked_case_ids: Set[str] = set()

    # (a) Direct account overlap
    overlap_rows = queries._rows(
        g,
        "MATCH (c:Case {id: $case_id})-[:INVOLVES]->(a:Account)<-[:INVOLVES]-(prev:Case) "
        "WHERE prev.id <> $case_id "
        "RETURN DISTINCT prev.id",
        case_id=case_id,
    )
    for r in overlap_rows:
        linked_case_ids.add(r[0])

    # (b) Device sharing link
    dev_link_rows = queries._rows(
        g,
        "MATCH (c:Case {id: $case_id})-[:INVOLVES]->(a:Account)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(o:Account)<-[:INVOLVES]-(prev:Case) "
        "WHERE prev.id <> $case_id AND o.id <> a.id "
        "RETURN DISTINCT prev.id",
        case_id=case_id,
    )
    for r in dev_link_rows:
        linked_case_ids.add(r[0])

    # (c) Phone sharing link
    phone_link_rows = queries._rows(
        g,
        "MATCH (c:Case {id: $case_id})-[:INVOLVES]->(a:Account)-[:REGISTERED_PHONE]->(p:Phone)<-[:REGISTERED_PHONE]-(o:Account)<-[:INVOLVES]-(prev:Case) "
        "WHERE prev.id <> $case_id AND o.id <> a.id "
        "RETURN DISTINCT prev.id",
        case_id=case_id,
    )
    for r in phone_link_rows:
        linked_case_ids.add(r[0])

    # Create LINKED_TO edges
    for prev_id in linked_case_ids:
        queries._rows(
            g,
            "MATCH (c:Case {id: $case_id}), (prev:Case {id: $prev_id}) "
            "MERGE (c)-[:LINKED_TO]->(prev)",
            case_id=case_id,
            prev_id=prev_id,
        )

    return {
        "saved": True,
        "case_id": case_id,
        "report_id": report_id,
        "accounts_flagged": len(target_accounts),
        "status": status,
        "linked_cases": sorted(linked_case_ids),
        "message": f"Successfully committed case '{case_id}' to memory with {len(target_accounts)} flagged accounts.",
    }


def recall_past_cases(graph, account_ids: List[str]) -> Dict[str, Any]:
    """Retrieve past case intelligence involving given accounts or their infrastructure.

    Args:
        graph: FalkorDB Graph instance.
        account_ids: Account IDs to check for prior incident involvement.
    """
    g = graph or get_graph()
    if not account_ids:
        return {"items": queries._wrap([], 20)}

    clean_ids = [a if isinstance(a, str) else a.get("account_id") for a in account_ids]
    clean_ids = [a for a in clean_ids if a]

    records: List[Dict[str, Any]] = []
    seen = set()

    # 1. Direct involvement
    direct_rows = queries._rows(
        g,
        "MATCH (c:Case)-[:INVOLVES]->(a:Account) WHERE a.id IN $ids "
        "OPTIONAL MATCH (a)-[f:FLAGGED_IN]->(fr:FraudReport {id: c.report_id}) "
        "RETURN c.id, c.report_id, c.created_at, c.summary, c.status, a.id, "
        "       f.confidence, f.priority, f.amount_recoverable",
        ids=clean_ids,
    )
    for cid, rep_id, created, summary, status, aid, conf, prio, amt in direct_rows:
        key = (cid, aid, "direct")
        if key not in seen:
            seen.add(key)
            records.append({
                "case_id": cid,
                "report_id": rep_id,
                "created_at": created,
                "summary": summary,
                "status": status,
                "account": aid,
                "link_type": "direct",
                "confidence": conf or "high",
                "priority": prio,
                "amount_recoverable": amt,
            })

    # 2. Shared device involvement
    dev_rows = queries._rows(
        g,
        "MATCH (a:Account)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(o:Account)<-[:INVOLVES]-(c:Case) "
        "WHERE a.id IN $ids AND o.id <> a.id "
        "OPTIONAL MATCH (o)-[f:FLAGGED_IN]->(fr:FraudReport {id: c.report_id}) "
        "RETURN c.id, c.report_id, c.created_at, c.summary, c.status, a.id, o.id, d.id, "
        "       f.confidence, f.priority, f.amount_recoverable",
        ids=clean_ids,
    )
    for cid, rep_id, created, summary, status, aid, oid, did, conf, prio, amt in dev_rows:
        key = (cid, aid, oid, "shared_device")
        if key not in seen:
            seen.add(key)
            records.append({
                "case_id": cid,
                "report_id": rep_id,
                "created_at": created,
                "summary": summary,
                "status": status,
                "queried_account": aid,
                "linked_account": oid,
                "shared_device": did,
                "link_type": "shared_device",
                "confidence": conf or "high",
                "priority": prio,
                "amount_recoverable": amt,
            })

    # 3. Shared phone involvement
    phone_rows = queries._rows(
        g,
        "MATCH (a:Account)-[:REGISTERED_PHONE]->(p:Phone)<-[:REGISTERED_PHONE]-(o:Account)<-[:INVOLVES]-(c:Case) "
        "WHERE a.id IN $ids AND o.id <> a.id "
        "OPTIONAL MATCH (o)-[f:FLAGGED_IN]->(fr:FraudReport {id: c.report_id}) "
        "RETURN c.id, c.report_id, c.created_at, c.summary, c.status, a.id, o.id, p.id, "
        "       f.confidence, f.priority, f.amount_recoverable",
        ids=clean_ids,
    )
    for cid, rep_id, created, summary, status, aid, oid, pid, conf, prio, amt in phone_rows:
        key = (cid, aid, oid, "shared_phone")
        if key not in seen:
            seen.add(key)
            records.append({
                "case_id": cid,
                "report_id": rep_id,
                "created_at": created,
                "summary": summary,
                "status": status,
                "queried_account": aid,
                "linked_account": oid,
                "shared_phone": pid,
                "link_type": "shared_phone",
                "confidence": conf or "high",
                "priority": prio,
                "amount_recoverable": amt,
            })

    records.sort(key=lambda r: r.get("created_at") or 0, reverse=True)
    return {"items": queries._wrap(records, 20)}


def reset_memory(graph=None) -> Dict[str, Any]:
    """Remove only memory artifacts (Case nodes, FLAGGED_IN, INVOLVES, LINKED_TO) and reset flags."""
    g = graph or get_graph()
    g.query("MATCH (c:Case) DETACH DELETE c")
    g.query("MATCH ()-[r:FLAGGED_IN]->() DELETE r")
    g.query("MATCH (a:Account) WHERE a.is_flagged = true OR a.risk_score > 0 SET a.is_flagged = false, a.risk_score = 0.0")
    return {"status": "ok", "message": "Memory graph reset completed."}
