"""Graph algorithm functions for MuleTrace (Phase 8).

Exposes plain Python functions that analyze connectivity, centrality, and
community structures over the FalkorDB payment and device graph.
Functions take a graph (from backend/db.get_graph()) plus parameters, use
parameterized Cypher queries, return JSON-serializable dicts, and never read
test datasets, documentation files, or ground truth files.

Output lists are capped and include {"truncated": bool, "total": N}.
Subgraphs are projected into NetworkX with in-memory TTL caching for fast repeated calls.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

# ---------------------------------------------------------------------------
# In-memory TTL Projection Cache
# ---------------------------------------------------------------------------
_PROJECTION_CACHE: Dict[Any, Tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def clear_projection_cache() -> None:
    """Clear the in-memory graph projection cache."""
    _PROJECTION_CACHE.clear()


def _rows(graph, cypher: str, **params):
    return (graph.query(cypher, params).result_set) or []


def _wrap(items: list, cap: int, truncated: Optional[bool] = None) -> dict:
    items = list(items)
    is_trunc = truncated if truncated is not None else (len(items) > cap)
    return {"truncated": is_trunc, "total": len(items), "items": items[:cap]}


def _get_latest_timestamp(graph) -> int:
    cached = _PROJECTION_CACHE.get("__latest_ts__")
    now = time.time()
    if cached and (now - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]
    rows = _rows(graph, "MATCH (p:PAID) RETURN max(p.timestamp)")
    val = int(rows[0][0]) if rows and rows[0][0] is not None else int(time.time())
    _PROJECTION_CACHE["__latest_ts__"] = (now, val)
    return val


def _get_victim_account_ids(graph) -> Set[str]:
    cached = _PROJECTION_CACHE.get("__victim_ids__")
    now = time.time()
    if cached and (now - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]
    rows = _rows(graph, "MATCH (f:FraudReport)-[:REPORTS_VICTIM]->(v:Account) RETURN v.id")
    v_ids = {r[0] for r in rows if r and r[0]}
    _PROJECTION_CACHE["__victim_ids__"] = (now, v_ids)
    return v_ids


def _build_projected_graph(
    graph,
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    include_shared_devices: bool = True,
    include_shared_phones: bool = True,
    max_device_sharing: int = 3,
    dev_weight: float = 50000.0,
    min_amount: Optional[float] = None,
) -> Tuple[nx.DiGraph, nx.Graph, List[dict]]:
    """Return (DiGraph_directed, Graph_undirected_multilink, shared_links_list)."""
    cache_key = (
        window_start,
        window_end,
        include_shared_devices,
        include_shared_phones,
        max_device_sharing,
        dev_weight,
        min_amount,
    )
    now = time.time()
    cached = _PROJECTION_CACHE.get(cache_key)
    if cached and (now - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]

    # Query PAID edges within the window
    cypher = (
        "MATCH (a:Account)-[p:PAID]->(b:Account) "
        "WHERE ($start IS NULL OR p.timestamp >= $start) "
        "  AND ($end IS NULL OR p.timestamp <= $end) "
    )
    if min_amount is not None:
        cypher += "  AND p.amount >= $min_amt "
    cypher += "RETURN a.id, b.id, p.amount, p.timestamp, p.txn_id"

    edges = _rows(
        graph,
        cypher,
        start=window_start,
        end=window_end,
        min_amt=min_amount,
    )

    digraph = nx.DiGraph()
    undirected = nx.Graph()

    for src, dst, amt, ts, tx in edges:
        amt_i = int(amt) if amt is not None else 0
        ts_i = int(ts) if ts is not None else 0

        # Directed graph for PageRank and directional flow
        if digraph.has_edge(src, dst):
            digraph[src][dst]["weight"] += amt_i
            digraph[src][dst]["count"] += 1
            digraph[src][dst]["txns"].append({"txn_id": tx, "amount": amt_i, "timestamp": ts_i})
        else:
            digraph.add_edge(
                src, dst, weight=amt_i, count=1,
                txns=[{"txn_id": tx, "amount": amt_i, "timestamp": ts_i}]
            )

        # Undirected graph for community detection & components
        if undirected.has_edge(src, dst):
            undirected[src][dst]["weight"] += amt_i
            undirected[src][dst]["count"] += 1
        else:
            undirected.add_edge(src, dst, weight=amt_i, count=1, link_type="PAID")

    shared_links: List[dict] = []

    # Include shared devices if requested
    if include_shared_devices:
        dev_rows = _rows(
            graph,
            "MATCH (d:Device)<-[:USES_DEVICE]-(a:Account) "
            "WITH d, collect(DISTINCT a.id) AS accs "
            "WHERE size(accs) >= 2 AND size(accs) <= $max_share "
            "RETURN d.id, accs",
            max_share=max_device_sharing,
        )
        for dev_id, accs in dev_rows:
            n = len(accs)
            for i in range(n):
                for j in range(i + 1, n):
                    u, v = accs[i], accs[j]
                    shared_links.append(
                        {"type": "SHARED_DEVICE", "device_id": dev_id, "accounts": [u, v]}
                    )
                    if undirected.has_edge(u, v):
                        undirected[u][v]["weight"] += dev_weight
                        undirected[u][v]["has_device"] = True
                        undirected[u][v].setdefault("devices", []).append(dev_id)
                    else:
                        undirected.add_edge(
                            u, v, weight=dev_weight, count=1,
                            link_type="SHARED_DEVICE", device_id=dev_id, devices=[dev_id]
                        )

    # Include shared phones if requested
    if include_shared_phones:
        phone_rows = _rows(
            graph,
            "MATCH (p:Phone)<-[:REGISTERED_PHONE]-(a:Account) "
            "WITH p, collect(DISTINCT a.id) AS accs "
            "WHERE size(accs) >= 2 AND size(accs) <= $max_share "
            "RETURN p.id, p.number, accs",
            max_share=max_device_sharing,
        )
        for ph_id, ph_num, accs in phone_rows:
            n = len(accs)
            for i in range(n):
                for j in range(i + 1, n):
                    u, v = accs[i], accs[j]
                    shared_links.append(
                        {"type": "SHARED_PHONE", "phone_id": ph_id, "number": ph_num, "accounts": [u, v]}
                    )
                    if undirected.has_edge(u, v):
                        undirected[u][v]["weight"] += dev_weight
                        undirected[u][v]["has_phone"] = True
                        undirected[u][v].setdefault("phones", []).append(ph_num)
                    else:
                        undirected.add_edge(
                            u, v, weight=dev_weight, count=1,
                            link_type="SHARED_PHONE", phone_id=ph_id, phones=[ph_num]
                        )

    result = (digraph, undirected, shared_links)
    _PROJECTION_CACHE[cache_key] = (now, result)
    return result


# ---------------------------------------------------------------------------
# a) find_shortest_path
# ---------------------------------------------------------------------------
def find_shortest_path(
    graph,
    src_account_id: str,
    dst_account_id: str,
    max_hops: int = 10,
    mode: str = "money",
    max_device_sharing: int = 3,
) -> dict:
    """Find the shortest path between two accounts.

    - mode="money": follows directed PAID edges only. Uses native Cypher shortestPath.
    - mode="any": allows hybrid hops through shared Device and Phone nodes (shared by <= 3 accounts).
    """
    if mode == "money":
        # Native Cypher shortestPath in WITH/RETURN
        cypher = (
            "MATCH (a:Account {id:$src}), (b:Account {id:$dst}) "
            "WITH shortestPath((a)-[:PAID*..10]->(b)) AS p "
            "WHERE p IS NOT NULL "
            "RETURN [n IN nodes(p) | n.id] AS path, "
            "       [r IN relationships(p) | {type: 'PAID', amount: r.amount, timestamp: r.timestamp, txn_id: r.txn_id}] AS hops"
        )
        rows = _rows(graph, cypher, src=src_account_id, dst=dst_account_id)
        if not rows or not rows[0][0]:
            return {
                "found": False,
                "src": src_account_id,
                "dst": dst_account_id,
                "mode": mode,
                "hops": 0,
                "path": [],
                "links": [],
                "link_types": [],
                "total_amount": 0,
            }
        path_ids = rows[0][0]
        raw_hops = rows[0][1]
        hops = [
            {
                "type": "PAID",
                "amount": int(h["amount"]) if h.get("amount") is not None else 0,
                "timestamp": int(h["timestamp"]) if h.get("timestamp") is not None else 0,
                "txn_id": h.get("txn_id"),
            }
            for h in raw_hops
        ]
        link_types = ["PAID"] * len(hops)
        total_amount = sum(h["amount"] for h in hops)
        return {
            "found": True,
            "src": src_account_id,
            "dst": dst_account_id,
            "mode": mode,
            "hops": len(hops),
            "path": path_ids,
            "links": hops,
            "link_types": link_types,
            "total_amount": total_amount,
        }

    elif mode == "any":
        # Hybrid graph with PAID edges + shared hardware links (<= max_device_sharing accounts)
        G = nx.Graph()
        edge_details: Dict[Tuple[str, str], dict] = {}

        # 1. PAID edges
        edges = _rows(graph, "MATCH (a:Account)-[p:PAID]->(b:Account) RETURN a.id, b.id, p.amount, p.timestamp, p.txn_id")
        for u, v, amt, ts, tx in edges:
            G.add_edge(u, v)
            pair = (min(u, v), max(u, v))
            edge_details[pair] = {
                "type": "PAID",
                "amount": int(amt) if amt is not None else 0,
                "timestamp": int(ts) if ts is not None else 0,
                "txn_id": tx,
            }

        # 2. Shared devices (<= max_device_sharing)
        devs = _rows(
            graph,
            "MATCH (d:Device)<-[:USES_DEVICE]-(a:Account) "
            "WITH d, collect(DISTINCT a.id) AS accs "
            "WHERE size(accs) >= 2 AND size(accs) <= $max_share "
            "RETURN d.id, accs",
            max_share=max_device_sharing,
        )
        for dev_id, accs in devs:
            n = len(accs)
            for i in range(n):
                for j in range(i + 1, n):
                    u, v = accs[i], accs[j]
                    G.add_edge(u, v)
                    pair = (min(u, v), max(u, v))
                    if pair not in edge_details or edge_details[pair]["type"] != "PAID":
                        edge_details[pair] = {
                            "type": "SHARED_DEVICE",
                            "device_id": dev_id,
                        }

        # 3. Shared phones (<= max_device_sharing)
        phones = _rows(
            graph,
            "MATCH (p:Phone)<-[:REGISTERED_PHONE]-(a:Account) "
            "WITH p, collect(DISTINCT a.id) AS accs "
            "WHERE size(accs) >= 2 AND size(accs) <= $max_share "
            "RETURN p.id, p.number, accs",
            max_share=max_device_sharing,
        )
        for ph_id, ph_num, accs in phones:
            n = len(accs)
            for i in range(n):
                for j in range(i + 1, n):
                    u, v = accs[i], accs[j]
                    G.add_edge(u, v)
                    pair = (min(u, v), max(u, v))
                    if pair not in edge_details:
                        edge_details[pair] = {
                            "type": "SHARED_PHONE",
                            "phone_id": ph_id,
                            "number": ph_num,
                        }

        if not G.has_node(src_account_id) or not G.has_node(dst_account_id):
            return {
                "found": False,
                "src": src_account_id,
                "dst": dst_account_id,
                "mode": mode,
                "hops": 0,
                "path": [],
                "links": [],
                "link_types": [],
            }

        try:
            path_nodes = nx.shortest_path(G, src_account_id, dst_account_id)
        except nx.NetworkXNoPath:
            return {
                "found": False,
                "src": src_account_id,
                "dst": dst_account_id,
                "mode": mode,
                "hops": 0,
                "path": [],
                "links": [],
                "link_types": [],
            }

        if len(path_nodes) - 1 > max_hops:
            return {
                "found": False,
                "src": src_account_id,
                "dst": dst_account_id,
                "mode": mode,
                "hops": len(path_nodes) - 1,
                "path": [],
                "links": [],
                "link_types": [],
            }

        links = []
        link_types = []
        for i in range(len(path_nodes) - 1):
            pair = (min(path_nodes[i], path_nodes[i + 1]), max(path_nodes[i], path_nodes[i + 1]))
            fact = edge_details.get(pair, {"type": "UNKNOWN"})
            links.append(fact)
            link_types.append(fact.get("type", "UNKNOWN"))

        return {
            "found": True,
            "src": src_account_id,
            "dst": dst_account_id,
            "mode": mode,
            "hops": len(links),
            "path": path_nodes,
            "links": links,
            "link_types": link_types,
        }
    else:
        raise ValueError(f"Unknown mode: {mode}. Must be 'money' or 'any'.")


# ---------------------------------------------------------------------------
# b) rank_hub_accounts (PageRank)
# ---------------------------------------------------------------------------
def rank_hub_accounts(
    graph,
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    top_k: int = 10,
    weight: str = "amount",
) -> dict:
    """PageRank on the PAID graph restricted to a time window, weighted by amount or count.

    Returns the top accounts with score, in/out degree, and total flow.
    """
    digraph, _, _ = _build_projected_graph(
        graph,
        window_start=window_start,
        window_end=window_end,
        include_shared_devices=False,
        include_shared_phones=False,
    )

    if len(digraph) == 0:
        return {
            "window_start": window_start,
            "window_end": window_end,
            "weight": weight,
            "note": "high rank is evidence of being a hub, not proof of fraud",
            "items": _wrap([], top_k),
        }

    weight_attr = "weight" if weight == "amount" else None
    try:
        pr = nx.pagerank(digraph, weight=weight_attr, alpha=0.85, max_iter=200)
    except Exception:
        # Fallback to unweighted in case of convergence edge cases
        pr = nx.pagerank(digraph, weight=None, alpha=0.85, max_iter=200)

    # In/Out degree and total flow per node
    ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)
    items = []
    for aid, score in ranked:
        in_deg = digraph.in_degree(aid)
        out_deg = digraph.out_degree(aid)
        in_flow = sum(d.get("weight", 0) for _, _, d in digraph.in_edges(aid, data=True))
        out_flow = sum(d.get("weight", 0) for _, _, d in digraph.out_edges(aid, data=True))
        items.append({
            "account": aid,
            "score": round(score, 6),
            "in_degree": in_deg,
            "out_degree": out_deg,
            "total_flow": in_flow + out_flow,
            "in_flow": in_flow,
            "out_flow": out_flow,
        })

    return {
        "window_start": window_start,
        "window_end": window_end,
        "weight": weight,
        "note": "high rank is evidence of being a hub, not proof of fraud",
        "items": _wrap(items, top_k),
    }


# ---------------------------------------------------------------------------
# c) find_connected_components
# ---------------------------------------------------------------------------
def find_connected_components(
    graph,
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    min_size: int = 3,
    include_shared_devices: bool = True,
    max_device_sharing: int = 3,
    min_amount: Optional[float] = None,
    limit: int = 20,
) -> dict:
    """Weakly connected components of accounts linked by PAID edges (and optionally shared devices).

    Devices shared by more than max_device_sharing accounts are ignored.
    """
    _, undirected, _ = _build_projected_graph(
        graph,
        window_start=window_start,
        window_end=window_end,
        include_shared_devices=include_shared_devices,
        include_shared_phones=False,
        max_device_sharing=max_device_sharing,
        min_amount=min_amount,
    )

    victims = _get_victim_account_ids(graph)
    raw_comps = list(nx.connected_components(undirected))

    comps = []
    for idx, c in enumerate(raw_comps):
        if len(c) >= min_size:
            comps.append({
                "component_id": idx,
                "size": len(c),
                "members": sorted(c),
                "has_victim": bool(c & victims),
            })

    comps.sort(key=lambda x: x["size"], reverse=True)
    return {
        "window_start": window_start,
        "window_end": window_end,
        "include_shared_devices": include_shared_devices,
        "min_size": min_size,
        "items": _wrap(comps, limit),
    }


# ---------------------------------------------------------------------------
# d) find_communities (Louvain)
# ---------------------------------------------------------------------------
def find_communities(
    graph,
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    resolution: float = 1.0,
    limit: int = 20,
    max_device_sharing: int = 3,
    dev_weight: float = 50000.0,
) -> dict:
    """Community detection (Louvain with seed=42) on combined PAID and shared-device graph.

    Returns communities with members, size, internal money flow, and outgoing money flow.
    """
    _, undirected, _ = _build_projected_graph(
        graph,
        window_start=window_start,
        window_end=window_end,
        include_shared_devices=True,
        include_shared_phones=True,
        max_device_sharing=max_device_sharing,
        dev_weight=dev_weight,
    )

    if len(undirected) == 0:
        return {
            "window_start": window_start,
            "window_end": window_end,
            "resolution": resolution,
            "items": _wrap([], limit),
        }

    comms = nx.community.louvain_communities(
        undirected, weight="weight", resolution=resolution, seed=42
    )

    results = []
    for idx, comm in enumerate(comms):
        internal_flow = 0
        outgoing_flow = 0
        for u in comm:
            for v, data in undirected[u].items():
                w = data.get("weight", 0)
                if v in comm:
                    if u < v:
                        internal_flow += w
                else:
                    outgoing_flow += w

        results.append({
            "community_id": idx,
            "size": len(comm),
            "members": sorted(comm),
            "internal_money_flow": int(internal_flow),
            "outgoing_money_flow": int(outgoing_flow),
        })

    results.sort(key=lambda x: x["size"], reverse=True)
    return {
        "window_start": window_start,
        "window_end": window_end,
        "resolution": resolution,
        "items": _wrap(results, limit),
    }


# ---------------------------------------------------------------------------
# e) find_connected_ring
# ---------------------------------------------------------------------------
def find_connected_ring(
    graph,
    account_id: str,
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    max_device_sharing: int = 3,
    dev_weight: float = 50000.0,
) -> dict:
    """The component and community containing account_id, with connecting edges and shared hardware links."""
    _, undirected, shared_links = _build_projected_graph(
        graph,
        window_start=window_start,
        window_end=window_end,
        include_shared_devices=True,
        include_shared_phones=True,
        max_device_sharing=max_device_sharing,
        dev_weight=dev_weight,
    )

    if not undirected.has_node(account_id):
        return {
            "found": False,
            "account_id": account_id,
            "size": 0,
            "component": [],
            "community": [],
            "shared_links": [],
            "edges": _wrap([], 50),
        }

    # 1. Connected Component
    for comp in nx.connected_components(undirected):
        if account_id in comp:
            my_comp = comp
            break
    else:
        my_comp = {account_id}

    # 2. Community
    comms = nx.community.louvain_communities(
        undirected, weight="weight", resolution=1.0, seed=42
    )
    my_comm = next((c for c in comms if account_id in c), {account_id})

    # Combined ring members of interest
    ring_members = my_comp

    # Relevant shared hardware links touching the ring
    relevant_links = [
        link for link in shared_links
        if link["accounts"][0] in ring_members or link["accounts"][1] in ring_members
    ]

    # Collect edges between ring members
    edge_items = []
    seen = set()
    for u in ring_members:
        for v in undirected.neighbors(u):
            if v in ring_members:
                pair = (min(u, v), max(u, v))
                if pair not in seen:
                    seen.add(pair)
                    d = undirected[u][v]
                    edge_items.append({
                        "source": u,
                        "target": v,
                        "link_type": d.get("link_type", "PAID"),
                        "weight": int(d.get("weight", 0)),
                        "devices": d.get("devices", []),
                        "phones": d.get("phones", []),
                    })

    return {
        "found": True,
        "account_id": account_id,
        "size": len(ring_members),
        "component": sorted(my_comp),
        "community": sorted(my_comm),
        "shared_links": relevant_links,
        "edges": _wrap(edge_items, 100),
    }


# ---------------------------------------------------------------------------
# f) rank_chokepoints (Betweenness Centrality)
# ---------------------------------------------------------------------------
def rank_chokepoints(graph, account_ids: List[str], top_k: int = 5) -> dict:
    """Betweenness centrality inside the subgraph made of the given accounts.

    Finds the key transfer points money must pass through.
    """
    if not account_ids:
        return {"account_ids": [], "items": _wrap([], top_k)}

    # Fetch directed PAID edges among the specified accounts
    rows = _rows(
        graph,
        "MATCH (a:Account)-[p:PAID]->(b:Account) "
        "WHERE a.id IN $ids AND b.id IN $ids "
        "RETURN a.id, b.id, p.amount",
        ids=list(account_ids),
    )

    G = nx.DiGraph()
    G.add_nodes_from(account_ids)
    for u, v, amt in rows:
        G.add_edge(u, v, weight=int(amt) if amt is not None else 1)

    if len(G) == 0:
        return {"account_ids": account_ids, "items": _wrap([], top_k)}

    btw = nx.betweenness_centrality(G)
    ranked = sorted(btw.items(), key=lambda x: x[1], reverse=True)

    items = [
        {"account": aid, "betweenness_score": round(score, 4)}
        for aid, score in ranked
    ]

    return {
        "account_ids": list(account_ids),
        "items": _wrap(items, top_k),
    }
