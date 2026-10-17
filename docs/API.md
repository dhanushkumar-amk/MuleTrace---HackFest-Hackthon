# MuleTrace Backend API Reference

**Autonomous Financial Fraud Ring Investigation Engine**  
*Track 01: Graph Agent / FalkorDB + Groq + Model Context Protocol (MCP)*

---

## 1. Overview & Architecture

The MuleTrace backend exposes a high-performance REST and Server-Sent Events (SSE) API built on **FastAPI**. It provides read-only graph queries, autonomous investigation lifecycle management, event streaming, evidence-grounded explainability, and forensic timeline reconstruction.

### Critical Invariants & Safety Guarantees
1. **No Investigation Logic in API**: All graph exploration, multi-hop BFS, ring detection, decoy rejection, and memory storage logic reside exclusively in dedicated agent and algorithm modules. The API router acts purely as an orchestrator.
2. **Zero Ingestion of Answer Keys**: The backend never reads `tests/`, `docs/`, or `ground_truth.json`. No account IDs or ring names are hardcoded in code.
3. **No Raw Cypher**: No endpoint accepts raw Cypher strings or arbitrary query parameters. All queries are parameterized and strictly bounded.
4. **No Direct Account Freezing**: The system cannot freeze accounts directly. Every case and investigation response carries the required disclaimer:
   > *"recommendation for human review, nothing was frozen"*
5. **Strict Rate Limiting & Concurrency Controls**: Active live runs are constrained (default: 1 concurrent run) to adhere to LLM free-tier throughput limits. Secondary concurrent requests return `HTTP 429`.

---

## 2. Interactive Documentation & Base URLs

- **API Base URL**: `http://localhost:8000`
- **Swagger / OpenAPI Interactive UI**: `http://localhost:8000/docs`
- **ReDoc Interactive UI**: `http://localhost:8000/redoc`
- **FalkorDB Browser Interface**: `http://localhost:3000`

---

## 3. Endpoints Catalog

### System & Catalog

#### `GET /health`
Returns system dependency statuses, connectivity to FalkorDB, presence of the Groq API key, MCP bridge mode, graph node count, and persisted case counts.

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "falkordb_reachable": true,
  "groq_key_present": true,
  "mcp_mode": "in-process",
  "graph_node_count": 6669,
  "graph_nodes_count": 6669,
  "saved_cases_count": 2
}
```

#### `GET /api/reports`
Lists all filed fraud reports from FalkorDB.

**Response (`200 OK`)**:
```json
[
  {
    "id": "FR_0001",
    "victim_account": "ACC_0461",
    "amount": 85000,
    "reported_at": 1792044900,
    "description": "Victim got a 'KYC verification' call and followed scammer instructions..."
  }
]
```

#### `GET /api/tools`
Catalogs all 20 Model Context Protocol (MCP) tools available to the autonomous investigation agent, along with their functional classification (`query`, `algorithm`, `trace`, `ledger`, `freeze`, `memory`).

**Response (`200 OK`)**:
```json
[
  {
    "name": "get_fraud_report",
    "kind": "query",
    "short_description": "Retrieve details of a filed fraud report including stolen amount, reported timestamp, incident description, and victim account identity."
  },
  {
    "name": "trace_money_forward",
    "kind": "query",
    "short_description": "Forward-in-time multi-hop money flow tracing using breadth-first search."
  }
]
```

#### `POST /api/admin/reset-memory`
Clears long-term case memory (`Case` nodes, `INVOLVES`, `LINKED_TO`, `FLAGGED_IN` edges) and resets account flags between demo takes. Only enabled when environment variable `DEMO_ADMIN=1` is set; otherwise returns `HTTP 403 Forbidden`.

---

### Investigations & Execution Management

#### `POST /api/investigations`
Starts an autonomous investigation run in the background. Returns `HTTP 202 Accepted` immediately with the assigned `session_id`.

**Request Body**:
```json
{
  "report_id": "FR_0001",
  "task": "Optional custom investigation instruction",
  "save_memory": false,
  "polish": false,
  "mode": "live",
  "speed": 1.0
}
```

**Response (`202 Accepted`)**:
```json
{
  "session_id": "inv_1792045100_a1b2",
  "status": "running",
  "mode": "live",
  "replay": false,
  "fallback_available": true
}
```

*Note*: If `MAX_CONCURRENT_RUNS` (default 1) is exceeded, returns `HTTP 429 Too Many Requests`:
```json
{
  "error": "Investigation run limit reached. Active session running: 'inv_1792045100_a1b2'.",
  "hint": "Wait for the active session to complete or cancel it via POST /api/investigations/{session_id}/cancel."
}
```

#### `GET /api/investigations/{session_id}`
Returns the current status (`running`, `done`, `error`, `cancelled`) and full grounded case explanation once completed.

**Response (`200 OK`)**:
```json
{
  "session_id": "inv_1792045100_a1b2",
  "status": "done",
  "mode": "live",
  "replay": false,
  "verified": true,
  "case": {
    "case_header": {
      "case_id": "CASE_FR_0001",
      "report_id": "FR_0001",
      "victim_account": "ACC_0461",
      "victim_name": "Ravi Kumar",
      "stolen_amount": 85000,
      "total_recoverable": 85000,
      "disclaimer": "recommendation for human review, nothing was frozen"
    },
    "recommendations": [...],
    "rejections": [...],
    "freeze_list": {...},
    "verified": true,
    "disclaimer": "recommendation for human review, nothing was frozen"
  },
  "disclaimer": "recommendation for human review, nothing was frozen"
}
```

#### `POST /api/investigations/{session_id}/cancel`
Cancels an in-progress investigation session immediately.

---

### Server-Sent Events (SSE) Stream

#### `GET /api/investigations/{session_id}/events`
Delivers real-time compact event streams of agent activities over HTTP Server-Sent Events (`text/event-stream`).

**Event Types**:
- `thought`: Internal agent chain-of-thought hypothesis.
- `tool_call`: MCP tool invocation with arguments and `call_id`.
- `tool_result`: Compact summary of tool output (full detailed data is preserved on disk).
- `final`: Final grounded synthesis summary with recoverable totals and freeze counts.
- `error`: Unhandled exception or timeout notification.
- `done`: Terminal event signaling completion of the stream.

**Connection Protocol & Resilience**:
- **History Buffering**: Late-subscribing clients receive all past events recorded for that session upon connection.
- **Heartbeats**: Emits `: heartbeat\n\n` comments every 15 seconds to prevent browser/proxy timeouts.
- **Resumption with `Last-Event-ID`**: Reconnecting clients pass the standard HTTP header `Last-Event-ID: ev_4` (or query param `?last_event_id=ev_4`) to resume without duplicate events.

**Sample Stream Wire Format**:
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

id: ev_1
event: thought
data: {"type": "thought", "content": "Victim ACC_0461 lost Rs 85,000 at timestamp 1792044900. I must trace forward outgoing payments to locate mule hops."}

id: ev_2
event: tool_call
data: {"type": "tool_call", "call_id": "call_001", "tool": "trace_money_forward", "arguments": {"start_account_id": "ACC_0461", "start_time": 1792044900}}

id: ev_3
event: tool_result
data: {"type": "tool_result", "call_id": "call_001", "tool": "trace_money_forward", "summary": "Found 3 multi-hop money flow paths terminating at suspect mule accounts."}

: heartbeat

id: ev_4
event: final
data: {"type": "final", "session_id": "inv_1792045100_a1b2", "total_recoverable": 85000, "freeze_count": 2, "disclaimer": "recommendation for human review, nothing was frozen"}

id: ev_5
event: done
data: {"session_id": "inv_1792045100_a1b2"}
```

---

### Cases & Visualizations

#### `GET /api/cases`
Lists all persisted cases from `data/runtime/cases/`.

**Response (`200 OK`)**:
```json
[
  {
    "session_id": "inv_1792045100_a1b2",
    "report_id": "FR_0001",
    "case_id": "CASE_FR_0001",
    "victim_name": "Ravi Kumar",
    "total_recoverable": 85000,
    "recoverable_total": 85000,
    "verified": true,
    "created_at": 1792045200,
    "status": "COMPLETED"
  }
]
```

#### `GET /api/cases/{session_id}`
Retrieves the full case explanation JSON. Supports query parameter `?format=markdown` or `?format=text` to return pre-rendered bank-ready compliance briefs.

#### `GET /api/cases/{session_id}/highlight`
Generates graph highlight data specifically structured for UI canvas visualization and hop-by-hop animation.
- Each edge carries a chronological `sequence` number (0, 1, 2...) for step-by-step playback.
- Nodes carry UI visualization roles: `victim`, `mule`, `cash_out`, `decoy_rejected`, `infrastructure`.

---

### Graph & Side Panel Intelligence

#### `GET /api/accounts/{account_id}`
Returns comprehensive behavioral profiling for the UI side panel:
- Inflow/outflow volumes, forward latency percentiles, distinct counterparties.
- Connected devices and phones, annotated with `share_count`.
- Summary indicators `shared_device_count` and `shared_phone_count`.

#### `GET /api/graph/neighborhood`
Wraps `queries.get_neighborhood` with strict safety caps:
- Parameters: `account_id` (required), `hops` (1 to 3, default 2), `limit` (1 to 150, default 60).
- Exceeding caps returns `HTTP 400 Bad Request`.

#### `GET /api/memory/cases`
Returns historical cases stored in FalkorDB memory, cross-linked by shared accounts or devices.

---

## 4. Demo Replay Mode

For live stage presentations and hackathon demo video recordings where network jitter or third-party LLM rate limits cannot be risked, MuleTrace includes an authentic **Replay Mode**:

1. **Activation**:
   - Set environment variable `DEMO_MODE=replay`, OR
   - Pass `"mode": "replay"` in the `POST /api/investigations` payload.
2. **Behavior**:
   - Instead of calling Groq, it streams pre-recorded events from `data/demo/ravi_run.json`.
   - Simulates realistic human pacing (controlled via `?speed=1.0`).
   - Serves verified case findings that pass 100% of mathematical integrity checks.
3. **Honesty by Design**:
   - Every replay response explicitly sets `"mode": "replay"` and `"replay": true`.
   - The UI displays a clear "Recorded Run" badge to maintain transparency.
   - If a live run fails due to external rate limiting, `"fallback_available": true` is returned so the user can seamlessly trigger the recorded demo.

---

## 5. UI Integration Guidelines (Phase 14)

1. **Dashboard Loading**:
   - Call `GET /health` to verify FalkorDB is connected and display graph statistics.
   - Call `GET /api/reports` to populate the "Pending Fraud Reports" table.
   - Call `GET /api/tools` to display the agent's MCP tool belt.
2. **Triggering an Investigation**:
   - Send `POST /api/investigations` with `{ "report_id": "FR_0001" }`.
   - On receipt of `HTTP 202` with `session_id`, open an `EventSource` connection to `/api/investigations/{session_id}/events`.
3. **Streaming Animation**:
   - Render incoming `thought` events in an interactive "Agent Reasoning" terminal.
   - Display `tool_call` and `tool_result` chips.
   - Upon receiving `final` / `done`, fetch `GET /api/cases/{session_id}/highlight` to animate the money path on the graph canvas.
4. **Side Panel Detail**:
   - When a node is clicked on the graph, call `GET /api/accounts/{account_id}` to render the account dossier.
