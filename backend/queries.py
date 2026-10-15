"""Core read-only Cypher queries for the MuleTrace agent.

Every function takes a FalkorDB Graph (from `backend.db.get_graph()`), uses
parameterized Cypher (never string-concatenated values), and returns
JSON-serializable dicts. Results are always capped and annotated with
`{"truncated": bool, "total": N}` so the agent never receives unbounded output.
This module never reads tests/, docs/, or tests/ground_truth.json.

Time-ordered path walking (`trace_money_forward`) uses a hop-by-hop BFS in Python
instead of a single variable-length Cypher query: the single-query form with a
pairwise time-ordering predicate times out on this ~5k-edge graph (see
docs/SCHEMA.md).
"""
from __future__ import annotations

import statistics

DEFAULT_MAX_PATHS = 50
DEFAULT_NEIGHBOR_LIMIT = 60


def _rows(graph, cypher, **params):
    return (graph.query(cypher, params).result_set) or []


def _i(x):
    return int(x) if x is not None else None


# ---------------------------------------------------------------------------
# a) fraud report + victim
# ---------------------------------------------------------------------------
def get_fraud_report(graph, report_id):
    rows = _rows(graph,
                 "MATCH (f:FraudReport {id:$id})-[:REPORTS_VICTIM]->(v:Account) "
                 "RETURN f.id, f.amount, f.reported_at, f.description, f.victim_account_id, "
                 "v.id, v.holder_name, v.bank, v.balance_held", id=report_id)
    if not rows:
        return {"found": False, "report_id": report_id}
    fid, amount, rep_at, desc, vid, v_acc, v_name, v_bank, v_bal = rows[0]
    return {
        "found": True,
        "report": {"id": fid, "amount": _i(amount), "reported_at": _i(rep_at),
                   "description": desc, "victim_account_id": vid},
        "victim": {"id": v_acc, "holder_name": v_name, "bank": v_bank,
                   "balance_held": _i(v_bal)},
    }


# ---------------------------------------------------------------------------
# b) account behaviour profile (no labels; used to tell decoy from mule)
# ---------------------------------------------------------------------------
def get_account_profile(graph, account_id):
    acc = _rows(graph,
                "MATCH (a:Account {id:$id}) "
                "RETURN a.id, a.holder_name, a.bank, a.account_type, a.opened_at, "
                "a.balance_held, a.is_flagged, a.risk_score", id=account_id)
    if not acc:
        return {"found": False, "account_id": account_id}
    aid, name, bank, atype, opened, bal, flagged, risk = acc[0]

    now_ts = _i((_rows(graph, "MATCH (t:Transaction) RETURN max(t.timestamp)") or [[0]])[0][0])
    age_days = None
    if opened is not None:
        age_days = round((now_ts - opened) / 86_400, 1)

    n_senders = _rows(graph,
                      "MATCH (s:Account)-[p:PAID]->(:Account {id:$id}) "
                      "RETURN count(DISTINCT s.id)", id=account_id)[0][0]
    n_receivers = _rows(graph,
                        "MATCH (:Account {id:$id})-[p:PAID]->(r:Account) "
                        "RETURN count(DISTINCT r.id)", id=account_id)[0][0]
    inflow = _i(_rows(graph,
                      "MATCH (s:Account)-[p:PAID]->(:Account {id:$id}) "
                      "RETURN sum(p.amount)", id=account_id)[0][0])
    outflow = _i(_rows(graph,
                       "MATCH (:Account {id:$id})-[p:PAID]->(r:Account) "
                       "RETURN sum(p.amount)", id=account_id)[0][0])
    in_count = _i(_rows(graph,
                        "MATCH (s:Account)-[p:PAID]->(:Account {id:$id}) "
                        "RETURN count(p)", id=account_id)[0][0])
    out_count = _i(_rows(graph,
                         "MATCH (:Account {id:$id})-[p:PAID]->(r:Account) "
                         "RETURN count(p)", id=account_id)[0][0])

    # forward latency: time between an incoming payment and the next outgoing one
    in_times = sorted(_i(r[0]) for r in _rows(
        graph, "MATCH (s:Account)-[p:PAID]->(:Account {id:$id}) RETURN p.timestamp",
        id=account_id))
    out_times = sorted(_i(r[0]) for r in _rows(
        graph, "MATCH (:Account {id:$id})-[p:PAID]->(r:Account) RETURN p.timestamp",
        id=account_id))
    latencies = []
    oi = 0
    for t_in in in_times:
        while oi < len(out_times) and out_times[oi] < t_in:
            oi += 1
        if oi < len(out_times):
            latencies.append(out_times[oi] - t_in)
    fwd_latency = {"min": min(latencies) if latencies else None,
                   "median": round(statistics.median(latencies), 1) if latencies else None,
                   "sample": len(latencies)}

    # devices + phones used, with sharing counts
    dev_rows = _rows(graph,
                     "MATCH (:Account {id:$id})-[:USES_DEVICE]->(d:Device) "
                     "RETURN d.id, d.os", id=account_id)
    dev_share = dict(_rows(graph,
                           "MATCH (d:Device)<-[:USES_DEVICE]-(o:Account) "
                           "RETURN d.id, count(o)"))
    devices = [{"device_id": d, "os": os_, "share_count": dev_share.get(d, 1)}
               for d, os_ in dev_rows]
    ph_rows = _rows(graph,
                    "MATCH (:Account {id:$id})-[:REGISTERED_PHONE]->(p:Phone) "
                    "RETURN p.id, p.number", id=account_id)
    ph_share = dict(_rows(graph,
                          "MATCH (p:Phone)<-[:REGISTERED_PHONE]-(o:Account) "
                          "RETURN p.id, count(o)"))
    phones = [{"phone_id": p, "number": num, "share_count": ph_share.get(p, 1)}
              for p, num in ph_rows]

    cash_rows = _rows(graph,
                      "MATCH (:Account {id:$id})-[c:CASHED_OUT_AT]->(p:CashOutPoint) "
                      "RETURN p.kind, p.name, p.location, c.amount, c.timestamp", id=account_id)
    cash_outs = [{"kind": k, "name": nm, "location": loc, "amount": _i(a),
                  "timestamp": _i(t)} for k, nm, loc, a, t in cash_rows]

    return {
        "found": True,
        "account_id": aid,
        "holder_name": name,
        "bank": bank,
        "account_type": atype,
        "is_flagged": bool(flagged),
        "risk_score": _i(risk),
        "opened_at": _i(opened),
        "age_days": age_days,
        "balance_held": _i(bal),
        "distinct_senders": _i(n_senders),
        "distinct_receivers": _i(n_receivers),
        "inflow_total": inflow,
        "outflow_total": outflow,
        "in_count": in_count,
        "out_count": out_count,
        "forward_latency": fwd_latency,
        "devices": _wrap(devices, 20),
        "phones": _wrap(phones, 20),
        "cash_outs": _wrap(cash_outs, 20),
    }


# ---------------------------------------------------------------------------
# c) forward-in-time multi-hop money trace (BFS)
# ---------------------------------------------------------------------------
def trace_money_forward(graph, start_account_id, start_time, max_hops=8,
                        min_amount=None, max_paths=DEFAULT_MAX_PATHS):
    start_time = _i(start_time)
    frontier = [{"path": [start_account_id], "hops": [], "last_ts": start_time}]
    results = []
    truncated = False
    for _ in range(max_hops):
        if not frontier:
            break
        outgoing = _outgoing_edges(graph, {p["path"][-1] for p in frontier})
        new_frontier = []
        for p in frontier:
            tail = p["path"][-1]
            for dst, amt, ts, txn in outgoing.get(tail, []):
                if ts < p["last_ts"]:
                    continue
                if min_amount is not None and amt < min_amount:
                    continue
                hop = {"account": dst, "txn_id": txn, "amount": _i(amt),
                       "timestamp": _i(ts)}
                results.append({"path": p["path"] + [dst], "hops": p["hops"] + [hop]})
                if len(results) >= max_paths:
                    truncated = True
                    break
                new_frontier.append({"path": p["path"] + [dst],
                                     "hops": p["hops"] + [hop], "last_ts": ts})
            if len(results) >= max_paths:
                break
        if len(results) >= max_paths:
            break
        frontier = new_frontier

    paths = [_path_out(r) for r in results]
    return {"start": start_account_id, "start_time": start_time,
            "max_hops": max_hops, "paths": _wrap(paths, max_paths)}


def _path_out(r):
    hops = r["hops"]
    return {
        "path": r["path"],
        "hops": hops,
        "hop_gaps": [hops[i]["timestamp"] - hops[i - 1]["timestamp"]
                     for i in range(1, len(hops))],
        "total_amount": sum(h["amount"] for h in hops),
    }


def _outgoing_edges(graph, account_ids):
    if not account_ids:
        return {}
    rows = _rows(graph,
                 "MATCH (a:Account)-[p:PAID]->(b:Account) WHERE a.id IN $ids "
                 "RETURN a.id, b.id, p.amount, p.timestamp, p.txn_id",
                 ids=list(account_ids))
    out = {}
    for aid, bid, amt, ts, tx in rows:
        out.setdefault(aid, []).append((bid, _i(amt), _i(ts), tx))
    return out


# ---------------------------------------------------------------------------
# d) cash-out points
# ---------------------------------------------------------------------------
def find_cash_out_points(graph, account_ids, limit=200):
    if not account_ids:
        return {"items": _wrap([], limit)}
    rows = _rows(graph,
                 "MATCH (a:Account)-[c:CASHED_OUT_AT]->(p:CashOutPoint) "
                 "WHERE a.id IN $ids RETURN a.id, p.kind, p.name, p.location, "
                 "c.amount, c.timestamp ORDER BY a.id, c.timestamp",
                 ids=list(account_ids))
    items = [{"account": a, "kind": k, "name": nm, "location": loc,
              "amount": _i(amt), "timestamp": _i(ts)} for a, k, nm, loc, amt, ts in rows]
    return {"items": _wrap(items, limit)}


# ---------------------------------------------------------------------------
# e) balance held
# ---------------------------------------------------------------------------
def get_balance_held(graph, account_ids):
    if not account_ids:
        return {}
    rows = _rows(graph,
                 "MATCH (a:Account) WHERE a.id IN $ids RETURN a.id, a.balance_held",
                 ids=list(account_ids))
    return {a: _i(b) for a, b in rows}


# ---------------------------------------------------------------------------
# f / g) shared devices / phones
# ---------------------------------------------------------------------------
def find_shared_devices(graph, account_id):
    rows = _rows(graph,
                 "MATCH (:Account {id:$id})-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(o:Account) "
                 "WHERE o.id <> $id "
                 "RETURN d.id, collect(DISTINCT o.id)", id=account_id)
    share_count = dict(_rows(graph,
                             "MATCH (d:Device)<-[:USES_DEVICE]-(a:Account) RETURN d.id, count(a)"))
    usage = dict((d, (fs, ls)) for d, fs, ls in _rows(
        graph, "MATCH (:Account {id:$id})-[u:USES_DEVICE]->(d:Device) "
               "RETURN d.id, u.first_seen, u.last_seen", id=account_id))
    out = []
    for nid, others in rows:
        if not others:
            continue  # a device only this account uses is not "shared"
        fs, ls = usage.get(nid, (None, None))
        out.append({"device_id": nid,
                    "sharing_accounts": sorted(others),
                    "share_count": share_count.get(nid, 0),
                    "first_seen": _i(fs), "last_seen": _i(ls)})
    return {"items": _wrap(out, DEFAULT_MAX_PATHS)}


def find_shared_phones(graph, account_id):
    rows = _rows(graph,
                 "MATCH (:Account {id:$id})-[:REGISTERED_PHONE]->(p:Phone)<-[:REGISTERED_PHONE]-(o:Account) "
                 "WHERE o.id <> $id "
                 "RETURN p.id, p.number, collect(DISTINCT o.id)", id=account_id)
    share_count = dict(_rows(graph,
                             "MATCH (p:Phone)<-[:REGISTERED_PHONE]-(a:Account) RETURN p.id, count(a)"))
    out = [{"phone_id": pid, "number": num, "sharing_accounts": sorted(others),
            "share_count": share_count.get(pid, 0)} for pid, num, others in rows
           if others]
    return {"items": _wrap(out, DEFAULT_MAX_PATHS)}


# ---------------------------------------------------------------------------
# h) rapid hops: forwarded >=70% of an incoming amount within a window
# ---------------------------------------------------------------------------
def detect_rapid_hops(graph, account_id=None, window_seconds=600, limit=20):
    rows = _rows(graph, "MATCH (s:Account)-[p:PAID]->(t:Account) "
                        "RETURN s.id, t.id, p.amount, p.timestamp, p.txn_id")
    incoming, outgoing = {}, {}
    for src, dst, amt, ts, tx in rows:
        ts = _i(ts)
        incoming.setdefault(dst, []).append({"ts": ts, "amt": _i(amt), "txn": tx,
                                             "src": src})
        outgoing.setdefault(src, []).append({"ts": ts, "amt": _i(amt), "txn": tx,
                                             "dst": dst})

    events = []
    targets = [account_id] if account_id else list(incoming.keys())
    for acct in targets:
        for inc in incoming.get(acct, []):
            out = [o for o in outgoing.get(acct, [])
                   if inc["ts"] < o["ts"] <= inc["ts"] + window_seconds]
            out_sum = sum(o["amt"] for o in out)
            if out_sum >= 0.7 * inc["amt"]:
                events.append({
                    "account": acct,
                    "in": {"txn_id": inc["txn"], "from": inc["src"],
                           "amount": inc["amt"], "timestamp": inc["ts"]},
                    "out_amount": out_sum, "out_count": len(out),
                    "matched_out": [{"txn_id": o["txn"], "to": o["dst"],
                                     "amount": o["amt"], "timestamp": o["ts"]}
                                    for o in out],
                })
    events.sort(key=lambda e: e["out_amount"], reverse=True)
    cap = limit if account_id is None else DEFAULT_MAX_PATHS
    return {"window_seconds": window_seconds, "items": _wrap(events, cap)}


# ---------------------------------------------------------------------------
# i) fan-in / smurf aggregators
# ---------------------------------------------------------------------------
def detect_fan_in(graph, window_seconds=86400, min_senders=6, limit=20):
    rows = _rows(graph, "MATCH (s:Account)-[p:PAID]->(t:Account) "
                        "RETURN s.id, t.id, p.amount, p.timestamp, p.txn_id")
    incoming, outgoing = {}, {}
    for src, dst, amt, ts, tx in rows:
        ts = _i(ts)
        incoming.setdefault(dst, []).append((ts, src, _i(amt)))
        outgoing.setdefault(src, []).append((ts, _i(amt)))
    cash = {}
    for a, cid, amt, ts in _rows(graph,
                                 "MATCH (a:Account)-[c:CASHED_OUT_AT]->(p:CashOutPoint) "
                                 "RETURN a.id, p.id, c.amount, c.timestamp"):
        cash.setdefault(a, []).append((_i(ts), _i(amt)))

    results = []
    for acct, ev in incoming.items():
        ev.sort()
        best = _densest_window(ev, window_seconds)
        if best is None:
            continue
        start, end, senders, total = best
        if senders < min_senders:
            continue
        # "forwarding onward" = money that leaves shortly AFTER the inflow window
        follow = min(window_seconds, 6 * 3600)
        onward = sum(a for t, a in outgoing.get(acct, [])
                     if end < t <= end + follow)
        onward += sum(a for t, a in cash.get(acct, [])
                      if end < t <= end + follow)
        ratio = round(onward / total, 3) if total else 0.0
        results.append({"account": acct, "sender_count": senders,
                        "total_received": total, "onward_forward_ratio": ratio})
    results.sort(key=lambda r: (-r["onward_forward_ratio"], -r["total_received"]))
    return {"window_seconds": window_seconds, "min_senders": min_senders,
            "items": _wrap(results, limit)}


def _densest_window(events, window_seconds):
    """Return (start, last_event_ts, max_distinct_senders, total) best window."""
    best = None
    n = len(events)
    for i in range(n):
        start = events[i][0]
        j = i
        senders = set()
        total = 0
        last = start
        while j < n and events[j][0] <= start + window_seconds:
            senders.add(events[j][1])
            total += events[j][2]
            last = events[j][0]
            j += 1
        if best is None or len(senders) > best[2] or \
           (len(senders) == best[2] and total > best[3]):
            best = (start, last, len(senders), total)
    return best


# ---------------------------------------------------------------------------
# j) fan-out: split an incoming amount to >=2 receivers quickly
# ---------------------------------------------------------------------------
def detect_fan_out(graph, account_id, window_seconds=3600, limit=50):
    rows = _rows(graph, "MATCH (s:Account)-[p:PAID]->(t:Account) "
                        "RETURN s.id, t.id, p.amount, p.timestamp, p.txn_id")
    incoming = [( _i(ts), _i(amt), tx, src) for src, dst, amt, ts, tx in rows if dst == account_id]
    outgoing = [(_i(ts), _i(amt), tx, dst) for src, dst, amt, ts, tx in rows if src == account_id]
    events = []
    for t_in, amt_in, tx_in, src in incoming:
        outs = [o for o in outgoing if t_in < o[0] <= t_in + window_seconds]
        if len({o[3] for o in outs}) >= 2:
            events.append({
                "account": account_id,
                "in": {"txn_id": tx_in, "from": src, "amount": amt_in,
                       "timestamp": t_in},
                "splits": [{"txn_id": o[2], "to": o[3], "amount": o[1],
                            "timestamp": o[0]} for o in outs],
            })
    events.sort(key=lambda e: sum(s["amount"] for s in e["splits"]), reverse=True)
    return {"window_seconds": window_seconds, "items": _wrap(events, limit)}


# ---------------------------------------------------------------------------
# k) neighbourhood for the UI
# ---------------------------------------------------------------------------
def get_neighborhood(graph, account_id, hops=2, limit=DEFAULT_NEIGHBOR_LIMIT):
    nodes = {account_id}
    edges = []
    frontier = {account_id}
    expanded = set()
    seen_edges = set()
    for _ in range(hops):
        expanded |= frontier
        fwd = _rows(graph,
                    "MATCH (a:Account)-[p:PAID]->(b:Account) WHERE a.id IN $ids "
                    "RETURN a.id, b.id, p.amount, p.timestamp, p.txn_id", ids=list(frontier))
        rev = _rows(graph,
                    "MATCH (a:Account)<-[p:PAID]-(b:Account) WHERE a.id IN $ids "
                    "RETURN a.id, b.id, p.amount, p.timestamp, p.txn_id", ids=list(frontier))
        next_frontier = set()
        for src, dst, amt, ts, tx in fwd + rev:
            key = (src, dst, tx)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"source": src, "target": dst, "type": "PAID",
                          "props": {"amount": _i(amt), "timestamp": _i(ts),
                                    "txn_id": tx}})
            nodes.add(dst)
            nodes.add(src)
            if dst not in expanded:
                next_frontier.add(dst)
        frontier = next_frontier
        if len(nodes) >= limit or not frontier:
            break

    props = {}
    for nid, name, atype, bal, flagged in _rows(
            graph, "MATCH (a:Account) WHERE a.id IN $ids RETURN a.id, "
                   "a.holder_name, a.account_type, a.balance_held, a.is_flagged",
            ids=list(nodes)):
        props[nid] = {"holder_name": name, "account_type": atype,
                      "balance_held": _i(bal), "is_flagged": bool(flagged)}
    node_list = [{"id": nid, "label": "Account", "props": props.get(nid, {})}
                 for nid in sorted(nodes)]
    truncated = len(node_list) > limit
    return {"nodes": _wrap(node_list, limit), "edges": _wrap(edges, limit * 4)}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _wrap(items, cap):
    items = list(items)
    return {"truncated": len(items) > cap, "total": len(items),
            "items": items[:cap]}