# Core Cypher queries (Phase 7)

`backend/queries.py` exposes plain Python functions over the loaded FalkorDB graph.
Each takes a `Graph` (from `backend/db.py`), uses **parameterized Cypher** (no
string-concatenated values), and returns JSON-serializable dicts. Every returned
list is capped and annotated with `{"truncated": bool, "total": N}`. Timings below
are representative runs on the loaded `muletrace` graph (~476 accounts, ~5.0k PAID
edges). Run them by hand with `python scripts/try_queries.py`.

> **Time-ordered path walking** (`trace_money_forward`) is BFS in Python, not a
> single variable-length Cypher query: a single-query form with a pairwise
> time-ordering predicate (`all(i IN range(0,size(ts)-2) WHERE ts[i]<ts[i+1])`)
> times out at 6–8 hops on this connected graph. See docs/SCHEMA.md.

---

## `get_fraud_report(report_id)`
- **Params:** `report_id` (string)
- **Cypher:**
  ```cypher
  MATCH (f:FraudReport {id:$id})-[:REPORTS_VICTIM]->(v:Account)
  RETURN f.id, f.amount, f.reported_at, f.description, f.victim_account_id,
         v.id, v.holder_name, v.bank, v.balance_held
  ```
- **Example (trimmed):**
  ```json
  {"found": true, "report": {"id": "FR_0001", "amount": 85000,
    "reported_at": 1792044900, "victim_account_id": "ACC_0461"},
   "victim": {"id": "ACC_0461", "holder_name": "Ravi Kumar",
    "bank": "HDFC Bank", "balance_held": 12600}}
  ```
- **Runtime:** ~1–2 ms

## `get_account_profile(account_id)`
Behaviour features with **no labels** (tells a decoy shop from a mule).
- **Params:** `account_id`
- **Cypher:** a handful of aggregations, e.g. sender/receiver counts:
  ```cypher
  MATCH (s:Account)-[p:PAID]->(:Account {id:$id}) RETURN count(DISTINCT s.id)
  MATCH (:Account {id:$id})-[p:PAID]->(r:Account) RETURN count(DISTINCT r.id)
  MATCH (:Account {id:$id})-[:USES_DEVICE]->(d:Device) RETURN d.id, d.os
  MATCH (:Account {id:$id})-[c:CASHED_OUT_AT]->(p:CashOutPoint)
        RETURN p.kind, p.name, p.location, c.amount, c.timestamp
  ```
  Forward latency is computed in Python from in/out PAID timestamps.
- **Example (decoy, trimmed):**
  ```json
  {"account_id": "ACC_0476", "account_type": "merchant",
   "balance_held": 160642, "distinct_senders": 62, "distinct_receivers": 1,
   "inflow_total": 159642, "outflow_total": 20000,
   "forward_latency": {"min": 7200, "median": 307260},
   "devices": {"total": 1, "items": [{"os": "android", "share_count": 1}]},
   "phones": {"total": 1, "items": [{"share_count": 1}]},
   "cash_outs": {"total": 2, "items": [{"kind": "ATM", "amount": 8000}, ...]}}
  ```
- **Runtime:** ~20 ms

## `trace_money_forward(start_account_id, start_time, max_hops=8, min_amount=None)`
Follow PAID money forward in time (each hop later than the previous). BFS in Python.
- **Params:** `start_account_id`, `start_time` (epoch), `max_hops`, `min_amount`
- **Cypher (per frontier hop):**
  ```cypher
  MATCH (a:Account)-[p:PAID]->(b:Account) WHERE a.id IN $ids
  RETURN a.id, b.id, p.amount, p.timestamp, p.txn_id
  ```
- **Example (Ravi at theft time, trimmed):**
  ```json
  {"paths": {"total": 5, "items": [
     {"path": ["ACC_0461","ACC_0462","ACC_0464","ACC_0465","ACC_0466"],
      "hops": [{"account":"ACC_0462","txn_id":"TXN_005011","amount":85000,
                "timestamp":1792038600}, ...],
      "hop_gaps": [150, 180, 120]}]}}
  ```
- **Runtime:** ~4–6 ms (capped at 50 paths)

## `find_cash_out_points(account_ids)`
- **Params:** `account_ids` (list)
- **Cypher:**
  ```cypher
  MATCH (a:Account)-[c:CASHED_OUT_AT]->(p:CashOutPoint)
  WHERE a.id IN $ids RETURN a.id, p.kind, p.name, p.location,
  c.amount, c.timestamp ORDER BY a.id, c.timestamp
  ```
- **Example (Ring 1):**
  ```json
  {"items": {"total":1,"items":[{"account":"ACC_0466","kind":"ATM",
    "name":"State Bank ATM - MG Road","amount":28000,
    "timestamp":1792039170}]}}
  ```
- **Runtime:** ~1 ms

## `get_balance_held(account_ids)`
- **Cypher:** `MATCH (a:Account) WHERE a.id IN $ids RETURN a.id, a.balance_held`
- **Example:** `{"ACC_0463": 40000, "ACC_0466": 15000}`
- **Runtime:** ~1 ms

## `find_shared_devices(account_id)` / `find_shared_phones(account_id)`
Other accounts sharing a device/phone, with the total share count (so a 2–3
account family-share is distinguishable).
- **Cypher:**
  ```cypher
  MATCH (:Account {id:$id})-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(o:Account)
  WHERE o.id <> $id RETURN d.id, collect(DISTINCT o.id)
  ```
- **Example (Mule B):**
  ```json
  {"items":{"total":1,"items":[{"device_id":"DEV_0593",
    "sharing_accounts":["ACC_0468"],"share_count":2,
    "first_seen":1723185000,"last_seen":1792042200}]}}
  ```
- **Runtime:** ~6–10 ms

## `detect_rapid_hops(account_id=None, window_seconds=600)`
Accounts that forwarded ≥70% of an incoming amount within the window, with the
matched in/out transactions. `account_id=None` scans the whole graph → top 20.
- **Cypher (fetch):** `MATCH (s:Account)-[p:PAID]->(t:Account) RETURN ...`
- **Example (Mule A):**
  ```json
  {"items":{"total":14,"items":[{"account":"ACC_0462",
     "in":{"txn_id":"TXN_005011","from":"ACC_0461","amount":85000},
     "out_amount":85000,"out_count":2,
     "matched_out":[{"txn_id":"TXN_005012","to":"ACC_0463","amount":40000},
                    {"txn_id":"TXN_005013","to":"ACC_0464","amount":45000}]}, ...]}}
  ```
- **Runtime:** ~120 ms

## `detect_fan_in(window_seconds=86400, min_senders=6)`
Smurf aggregators: accounts receiving from many distinct senders in a window, then
forwarding onward; ranked by onward-forward ratio, top 20. Ring 3 is **layered**
(2–3 senders per sink), so use a low `min_senders` (e.g. 3) to surface it.
- **Example (min_senders=3):**
  ```json
  {"items":{"total":81,"items":[{"account":"ACC_0475","sender_count":3,
    "total_received":44522,"onward_forward_ratio":1.0},
    {"account":"ACC_0472","sender_count":3,"total_received":18369,
     "onward_forward_ratio":1.0}, ...]}}
  ```
- **Runtime:** ~110 ms

## `detect_fan_out(account_id, window_seconds=3600)`
Accounts that split an incoming amount to ≥2 receivers quickly.
- **Example (Mule A):** `in: 85k`, `splits: [40k→B, 45k→C]`
- **Runtime:** ~120 ms

## `get_neighborhood(account_id, hops=2, limit=60)`
Nodes/edges for the UI graph view (money = PAID edges), capped.
- **Example:**
  ```json
  {"nodes":{"truncated":true,"total":345,"items":[
     {"id":"ACC_0001","label":"Account",
      "props":{"holder_name":"Matthew Rana","account_type":"individual",
               "balance_held":2774}}, ...]},
   "edges": {"total": ..., "items": [{"source":"ACC_0461","target":"ACC_0462",
      "type":"PAID","props":{...}}]}}
  ```
- **Runtime:** ~30 ms