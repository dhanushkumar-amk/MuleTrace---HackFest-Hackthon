# Graph Algorithms (Phase 8)

This document details the graph algorithms used in MuleTrace, the discovery of native FalkorDB procedures vs. Python (NetworkX) fallbacks, and the specification of each algorithm function in `backend/algorithms.py`.

---

## 1. Native FalkorDB Procedure Discovery & Evaluation

A discovery query on the running FalkorDB instance (`CALL dbms.procedures()`) returned 10 `algo.*` procedures:
- `algo.BFS`
- `algo.HarmonicCentrality`
- `algo.MSF`
- `algo.SPpaths`
- `algo.SSpaths`
- `algo.WCC`
- `algo.betweenness`
- `algo.labelPropagation`
- `algo.maxFlow`
- `algo.pageRank`

Each procedure was inspected for parameters, return signatures, edge filtering capabilities, and time-window support:

| Algorithm / Tool | Native FalkorDB Procedure | Implementation Choice | Rationale & Findings |
|---|---|---|---|
| **Shortest Path** (`mode="money"`) | Cypher `shortestPath(...)` in `WITH`/`RETURN` | **Native FalkorDB** | Native Cypher `WITH shortestPath((a)-[:PAID*..10]->(b)) AS p` executes directly in FalkorDB in < 1 ms and returns nodes and relationships. |
| **Shortest Path** (`mode="any"`) | `algo.SPpaths` / `algo.BFS` | **NetworkX** | `algo.SPpaths` accepts a single map configuration and cannot traverse heterogeneous edge types or filter shared devices by account sharing threshold ($\le 3$). NetworkX builds a hybrid multigraph (PAID + shared hardware) and computes `nx.shortest_path`. |
| **Hub Centrality** (PageRank) | `algo.pageRank` | **NetworkX** | `algo.pageRank('Account', 'PAID')` takes at most 2 arguments. It **cannot** filter by time window (`window_start`, `window_end`), cannot weight by transfer amount, and does not compute in/out degree or total flow. NetworkX `nx.pagerank` runs in ~25–50 ms on windowed subgraphs with arbitrary weighting. |
| **Weakly Connected Components** (WCC) | `algo.WCC` | **NetworkX** | Native `algo.WCC()` runs only globally over all 6,669 nodes (including transactions, phones, devices), cannot take relationship/label arguments or time windows, and cannot selectively inject shared devices ($\le 3$ accounts). NetworkX `nx.connected_components` on windowed subgraphs accurately isolates rings. |
| **Community Detection** (Louvain) | `algo.labelPropagation` | **NetworkX (Louvain)** | Native `algo.labelPropagation()` runs only globally without edge weighting or time filtering. NetworkX `nx.community.louvain_communities(..., seed=42)` provides deterministic, weighted community detection with internal/external flow tracking. |
| **Connected Ring Analysis** | *None* | **NetworkX** | Composite analysis combining components, Louvain communities, and shared hardware link attribution around a seed account. |
| **Chokepoint Centrality** (Betweenness) | `algo.betweenness` | **NetworkX** | Native `algo.betweenness()` runs globally across all 6,669 nodes and cannot compute betweenness centrality restricted to an arbitrary subset of candidate account IDs. NetworkX computes directed betweenness on the subgraph in ~1–2 ms. |

---

## 2. Algorithm Functions in `backend/algorithms.py`

Subgraphs are pulled with parameterized Cypher queries and cached in-memory with a 5-minute TTL (`_PROJECTION_CACHE`).

---

### `find_shortest_path(graph, src_account_id, dst_account_id, max_hops=10, mode="money"|"any")`
- **What it does:** Finds the shortest connection between two accounts. `mode="money"` follows directed PAID edges only. `mode="any"` allows hops through shared devices and phones (shared by $\le 3$ accounts).
- **Params:** `src_account_id`, `dst_account_id`, `max_hops` (default 10), `mode` ("money" or "any"), `max_device_sharing` (default 3).
- **Example output (mode="money", trimmed):**
  ```json
  {
    "found": true, "src": "ACC_0461", "dst": "ACC_0466", "mode": "money", "hops": 4,
    "path": ["ACC_0461", "ACC_0462", "ACC_0464", "ACC_0465", "ACC_0466"],
    "links": [{"type": "PAID", "amount": 85000, "timestamp": 1792038600, "txn_id": "TXN_005011"}, ...],
    "link_types": ["PAID", "PAID", "PAID", "PAID"], "total_amount": 217000
  }
  ```
- **Example output (mode="any", trimmed):**
  ```json
  {
    "found": true, "src": "ACC_0463", "dst": "ACC_0468", "mode": "any", "hops": 1,
    "path": ["ACC_0463", "ACC_0468"],
    "links": [{"type": "SHARED_DEVICE", "device_id": "DEV_0593"}],
    "link_types": ["SHARED_DEVICE"]
  }
  ```
- **Runtime:** ~1 ms (`mode="money"`), ~140 ms cold / ~2 ms cached (`mode="any"`).
- **What it can/cannot prove:** Proves topological reachability and shortest hop count; cannot prove fraudulent intent without examining timing and amounts.

---

### `rank_hub_accounts(graph, window_start=None, window_end=None, top_k=10, weight="amount"|"count")`
- **What it does:** Runs PageRank on the PAID graph restricted to a time window, weighted by payment amount or transaction count. Returns top accounts with in/out degree and flow volumes.
- **Params:** `window_start`, `window_end`, `top_k` (default 10), `weight` ("amount" or "count").
- **Example output (Ring 3 window, trimmed):**
  ```json
  {
    "window_start": 1789572600, "window_end": 1789591500, "weight": "amount",
    "note": "high rank is evidence of being a hub, not proof of fraud",
    "items": {
      "truncated": true, "total": 123,
      "items": [
        {"account": "ACC_0475", "score": 0.0459, "in_degree": 3, "out_degree": 0, "total_flow": 44522},
        {"account": "ACC_0448", "score": 0.02254, "in_degree": 4, "out_degree": 0, "total_flow": 8034}
      ]
    }
  }
  ```
- **Runtime:** ~25–50 ms.
- **What it can/cannot prove:** Surfaces high-volume aggregators and structural hubs; cannot prove fraud (busy merchants like the decoy also rank high).

---

### `find_connected_components(graph, window_start=None, window_end=None, min_size=3, include_shared_devices=True, max_device_sharing=3, min_amount=None, limit=20)`
- **What it does:** Computes connected components of accounts linked by PAID edges and optionally shared hardware ($\le 3$ accounts). Annotates components that contain a reported fraud victim.
- **Params:** `window_start`, `window_end`, `min_size` (default 3), `include_shared_devices` (default True), `max_device_sharing` (default 3), `min_amount` (optional threshold), `limit` (default 20).
- **Example output (trimmed):**
  ```json
  {
    "window_start": 1791693000, "window_end": 1792042200, "include_shared_devices": true,
    "items": {
      "truncated": true, "total": 28,
      "items": [
        {"component_id": 16, "size": 12, "members": ["ACC_0110", "ACC_0461", "ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466", "ACC_0467", "ACC_0468", "ACC_0469", "ACC_0470", "ACC_0471"], "has_victim": true}
      ]
    }
  }
  ```
- **Runtime:** ~20 ms.
- **What it can/cannot prove:** Proves membership in an interconnected money/device network; cannot prove individual culpability within the component without tracing specific paths.

---

### `find_communities(graph, window_start=None, window_end=None, resolution=1.0, limit=20, max_device_sharing=3, dev_weight=50000.0)`
- **What it does:** Louvain community detection (`seed=42`) on the combined PAID and shared-device graph. Computes internal and outgoing money flow.
- **Params:** `window_start`, `window_end`, `resolution` (default 1.0), `limit` (default 20), `max_device_sharing` (default 3), `dev_weight` (default 50000.0).
- **Example output (trimmed):**
  ```json
  {
    "resolution": 1.0,
    "items": {
      "truncated": true, "total": 18,
      "items": [
        {"community_id": 1, "size": 45, "members": ["ACC_0021", ...], "internal_money_flow": 1619552, "outgoing_money_flow": 2076888}
      ]
    }
  }
  ```
- **Runtime:** ~60 ms.
- **What it can/cannot prove:** Separates distinct transaction clusters (keeping legitimate merchants isolated from mule rings); cannot determine which clusters are criminal without seed reports.

---

### `find_connected_ring(graph, account_id, window_start=None, window_end=None, max_device_sharing=3, dev_weight=50000.0)`
- **What it does:** Surfaces the connected component, community, and hardware links around a target account. Powers the demo moment connecting Ring 1 to Ring 2.
- **Params:** `account_id`, `window_start`, `window_end`, `max_device_sharing` (default 3), `dev_weight` (default 50000.0).
- **Example output (Mule B, trimmed):**
  ```json
  {
    "found": true, "account_id": "ACC_0463", "size": 476,
    "component": ["ACC_0001", ...],
    "community": ["ACC_0461", "ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466", "ACC_0467", "ACC_0468", ...],
    "shared_links": [
      {"type": "SHARED_DEVICE", "device_id": "DEV_0593", "accounts": ["ACC_0463", "ACC_0468"]}
    ],
    "edges": {"truncated": false, "total": 19, "items": [...]}
  }
  ```
- **Runtime:** ~60 ms.
- **What it can/cannot prove:** Pinpoints hidden cross-ring links (e.g. shared phones/devices); cannot determine if a device was stolen, spoofed, or shared innocently.

---

### `rank_chokepoints(graph, account_ids, top_k=5)`
- **What it does:** Computes directed betweenness centrality within the induced subgraph of candidate accounts to identify key transfer bottleneck nodes.
- **Params:** `account_ids` (list of strings), `top_k` (default 5).
- **Example output (Ring 1 chain, trimmed):**
  ```json
  {
    "account_ids": ["ACC_0461", "ACC_0462", "ACC_0464", "ACC_0465", "ACC_0466"],
    "items": {
      "truncated": false, "total": 5,
      "items": [
        {"account": "ACC_0464", "betweenness_score": 0.3333},
        {"account": "ACC_0462", "betweenness_score": 0.25},
        {"account": "ACC_0465", "betweenness_score": 0.25},
        {"account": "ACC_0461", "betweenness_score": 0.0},
        {"account": "ACC_0466", "betweenness_score": 0.0}
      ]
    }
  }
  ```
- **Runtime:** ~1–2 ms.
- **What it can/cannot prove:** Identifies the structural bottlenecks through which traced funds must pass; cannot prove whether the chokepoint account holder is an organizer or a victim.
