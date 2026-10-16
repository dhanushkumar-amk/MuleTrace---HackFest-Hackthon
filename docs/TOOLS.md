# MuleTrace — Agent Graph Tools

The agent chooses its own tools at each step. There is **no hardcoded sequence** — the
LLM decides which tool fits the current question and calls it through MCP using Groq tool-calling format (JSON schema). All tools
take JSON input and return JSON.

## Tools

### `trace_money_forward`
- **Purpose:** Walk the money forward from an account/transaction within a time window.
- **Input:** `{ "account": "acct_1", "start_time": "...", "window_min": 15 }`
- **Output:** list of transfer steps tagged with the split path.
- **Graph feature:** Cypher multi-hop traversal (time-bounded).
```json
{ "steps": [
  { "from": "acct_1", "to": "acct_A", "amount": 85000, "path": ["acct_1","acct_A"] },
  { "from": "acct_A", "to": "acct_B", "amount": 40000, "path": ["acct_1","acct_A","acct_B"] }
] }
```

### `find_shortest_path`
- **Purpose:** Find the shortest money path between two accounts.
- **Input:** `{ "from": "acct_A", "to": "acct_E", "max_hops": 6 }`
- **Output:** ordered node list + total amount moved.
- **Graph feature:** shortest path algorithm.
```json
{ "path": ["acct_A","acct_B","acct_D","acct_E"], "amount": 40000, "hops": 3 }
```

### `find_cash_out_points`
- **Purpose:** Find where a chain ends — ATM withdrawals or crypto exchange transfers.
- **Input:** `{ "account": "acct_E", "window_min": 30 }`
- **Output:** cash-out events whose proceeds sit outside the traceable graph.
- **Graph feature:** Cypher terminal-node query (nodes with cash-out label).
```json
{ "events": [ { "from": "acct_E", "type": "crypto_exchange", "amount": 15000, "time": "..." } ] }
```

### `rank_hub_accounts`
- **Purpose:** Rank accounts by centrality to flag repeat mule hubs.
- **Input:** `{ "top_k": 10 }`
- **Output:** accounts ranked by influence score.
- **Graph feature:** PageRank.
```json
{ "ranks": [ { "account": "acct_A", "score": 3.2, "in_degree": 12, "out_degree": 8 } ] }
```

### `find_connected_ring`
- **Purpose:** Find suspicious communities / connected components around a seed.
- **Input:** `{ "seed": "acct_B", "method": "components" }`
- **Output:** members of the ring/community with a representative size.
- **Graph feature:** connected components / community detection (Louvain).
```json
{ "ring": { "members": ["acct_B","acct_F","acct_G"], "edges": 6, "size": 3 } }
```

### `find_shared_devices`
- **Purpose:** Link accounts that share a phone/device — a common mule fingerprint.
- **Input:** `{ "seed": "acct_B" }`
- **Output:** accounts reachable via shared-device edges.
- **Graph feature:** shared-device lookup (device nodes, 1–2 hop).
```json
{ "device": "dev_7", "accounts": ["acct_B","acct_F"], "note": "second ring discovered" }
```

### `get_account_balance_held`
- **Purpose:** Return the balance / money still held in an account at report time.
- **Input:** `{ "account": "acct_B", "at_time": "..." }`
- **Output:** current balance and inflow minus outflow attributable to the trace.
- **Graph feature:** Cypher aggregation on incoming/outgoing transaction edges.
```json
{ "account": "acct_B", "balance": 40000, "attributable_to_trace": 40000 }
```

### `build_freeze_list`
- **Purpose:** Assemble and rank the final freeze list from traced balances.
- **Input:** `{ "items": [ { "account": "acct_B", "held": 40000, "path": [ "acct_1","acct_A","acct_B" ] } ] }`
- **Output:** ranked freeze list (desc) with paths.
- **Graph feature:** combiner tool (ranks prior tool outputs).
```json
{ "freeze_list": [
  { "rank": 1, "account": "acct_B", "held": 40000, "path": ["acct_1","acct_A","acct_B"] },
  { "rank": 2, "account": "acct_E", "held": 15000, "path": ["acct_1","acct_A","acct_C","acct_D","acct_E"] }
] }
```

## Tool-selection rule
The agent must **choose its own tools** and may call any tool in any order, skipping or
repeating as the graph suggests. No tool sequence is hardcoded or enforced by the app;
the LLM decides based on the running investigation state.