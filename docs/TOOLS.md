# MuleTrace — Agent Graph Tools

The agent chooses its own tools at each step. There is **no hardcoded sequence** — the
LLM decides which tool fits the current question and calls it through MCP using Groq tool-calling format (JSON schema). All tools take JSON input and return JSON.

Total registered tools: **20** (18 query/algorithm tools + 2 action tools).

---

## 1. Primary Investigation Tools

### `get_fraud_report` (kind = "query")
- **Purpose:** Retrieve details of a filed fraud report including stolen amount, reported timestamp, incident description, and victim account identity.
- **Input:** `{ "report_id": "FR_0001" }`
- **Output:** Victim account ID, amount stolen, reported timestamp, and incident description.

### `trace_money_forward` (kind = "query")
- **Purpose:** Walk the money forward from an account/transaction within a time window.
- **Input:** `{ "account_id": "ACC_0461", "start_time": 1792038600, "window_minutes": 180, "max_hops": 6 }`
- **Output:** List of transfer steps tagged with the split path, amounts, and transaction IDs.

### `get_account_profile` (kind = "query")
- **Purpose:** Retrieve full account behavioral profile, KYC information, balance held, and shared device/phone associations.
- **Input:** `{ "account_id": "ACC_0463" }`
- **Output:** Bank, account type, balance held, in/outflow counts, forward latency, shared devices and phones.

### `get_balance_held` (kind = "query")
- **Purpose:** Query current balance held across candidate accounts.
- **Input:** `{ "account_ids": ["ACC_0463", "ACC_0466"] }`
- **Output:** Map of account IDs to their current balance sitting in the graph.

---

## 2. Graph Algorithms & Structural Tools

### `find_shared_devices` & `find_shared_phones` (kind = "query")
- **Purpose:** Discover accounts that share a physical device or phone number (mule ring fingerprint).
- **Input:** `{ "account_id": "ACC_0463" }`
- **Output:** List of shared devices/phones and all accounts linked to them.

### `detect_rapid_hops` (kind = "query")
- **Purpose:** Detect accounts rapidly forwarding >= 70% of inbound funds within 10 minutes.
- **Input:** `{ "account_ids": ["ACC_0462", "ACC_0464"] }`
- **Output:** Flagged rapid forwarders with forwarding latency and retention ratio.

### `detect_fan_in` & `detect_fan_out` (kind = "query")
- **Purpose:** Detect transaction fan-in (aggregation) or fan-out (layering dispersal) patterns.
- **Input:** `{ "account_id": "ACC_0462" }`
- **Output:** Inbound/outbound counts, volume, and degree metrics.

### `find_cash_out_points` (kind = "query")
- **Purpose:** Find where a chain ends — ATM withdrawals, crypto exchanges, or wallet exits.
- **Input:** `{ "account_ids": ["ACC_0466"] }`
- **Output:** Exit events whose proceeds leave the traceable graph.

### `rank_hub_accounts` (kind = "query")
- **Purpose:** Rank accounts by centrality / PageRank to flag repeat mule hubs.
- **Input:** `{ "top_k": 10 }`
- **Output:** Accounts ranked by influence score.

### `find_connected_ring` & `find_communities` & `find_connected_components` (kind = "query")
- **Purpose:** Uncover suspicious communities, Louvain clusters, or connected components around a seed.
- **Input:** `{ "seed_account": "ACC_0463" }`
- **Output:** Cluster members, ring size, and internal edge density.

### `find_shortest_path` (kind = "query")
- **Purpose:** Compute shortest directed money path between two accounts.
- **Input:** `{ "source_id": "ACC_0461", "target_id": "ACC_0466", "max_hops": 6 }`
- **Output:** Ordered account node list, total amount moved, and hop count.

### `get_neighborhood` & `rank_chokepoints` (kind = "query")
- **Purpose:** Inspect 1-to-2 hop neighborhoods or rank accounts by betweenness centrality.

---

## 3. Phase 11 Freeze-List & Memory Tools

### `build_freeze_list` (kind = "action")
- **Purpose:** Independently re-verify candidate suspects against graph ground truth (>= 2 hops from victim, >= 2 independent behavioral signals, legitimate merchant guard) and rank by recoverable balance descending.
- **Input:** `{ "report_id": "FR_0001", "candidate_account_ids": ["ACC_0463", "ACC_0466", "ACC_0476"] }`
- **Output:** Ranked freeze list (`recommendation_only: true`), `not_recommended` list with rejection reasons, total recoverable balance, and total cashed out.

### `save_case_to_memory` (kind = "action")
- **Purpose:** Persist verified case findings, `FLAGGED_IN`, `INVOLVES`, `LINKED_TO` edges, `is_flagged=true`, and `risk_score` for accounts listed in the freeze list.
- **Input:** `{ "report_id": "FR_0001", "summary": "Investigation completed." }`
- **Output:** Confirmation of persisted `Case` node and relationship counts.

### `recall_past_cases` (kind = "query")
- **Purpose:** Query past cases involving candidate accounts or accounts sharing devices/phones with them.
- **Input:** `{ "account_ids": ["ACC_0468"] }`
- **Output:** List of historical cases with date, outcome, summary, and linking mechanism.