# MuleTrace — Tool Layer & Model Context Protocol (MCP) Server

Phase 9-11 establishes the tool layer and MCP integration for MuleTrace. It exposes 20 graph tools (17 queries/algorithms, 2 memory actions, and 1 freeze ranking action) through a unified registry, supports dual transports (`stdio` and `streamable-http`) plus in-process client bridging, enforces token-budget compaction (~3,000 characters) for Groq free-tier compatibility, and provides structured error handling so tools never crash or raise unhandled exceptions to the LLM.

---

## 1. Architecture & Single Source of Truth

```
                           +------------------------+
                           |  Phase 10 LLM Agent    |
                           +-----------+------------+
                                       |
                           (Groq Tool-Calling Format
                                (JSON Schema))
                                       v
                           +------------------------+
                           |   MuleTraceMCPClient   |
                           +-----------+------------+
                                       |
                  +--------------------+--------------------+
                  |                                         |
                  v                                         v
         [in-process direct]                       [stdio / HTTP JSON-RPC]
                  |                                         |
                  +--------------------+--------------------+
                                       |
                                       v
                           +------------------------+
                           |   backend/mcp_server   |
                           |   (FastMCP/MCPServer)  |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
                           | backend/tools/registry |
                           +-----------+------------+
                                       |
                 +---------------------+---------------------+
                 |                     |                     |
                 v                     v                     v
          backend/queries     backend/algorithms     backend/tools/trace
                 |                     |                     |
                 +----------+----------+                     v
                            |                      data/runtime/
                            v                     tool_calls.jsonl
                     FalkorDB Graph
```

- **Single Source of Truth (`backend/tools/registry.py`)**: Defines all tools, typed Pydantic parameter schemas, execution timeouts (10 seconds), output compaction, and prompt descriptions (<80 words).
- **Pure Client Bridge (`backend/mcp_client.py`)**: The Phase 10 agent never imports Python graph functions directly; it discovers and invokes tools exclusively via `MuleTraceMCPClient`.
- **Audit & Explainability Trace (`backend/tools/trace.py`)**: Logs every tool execution in-memory and appends records to `data/runtime/tool_calls.jsonl` with timing, result size, success status, arguments, and money paths.

---

## 2. Running the MCP Server

The server supports two distinct transports:

### Transport A: Standard I/O (`stdio`)
Default transport for local execution, CLI subprocess invocation, and integration with desktop AI hosts (e.g., Claude Desktop).

```bash
python -m backend.mcp_server
```

> **Stdio Isolation Rule:** Standard output (`stdout`) is strictly reserved for JSON-RPC MCP messages. All server logs, notices, and diagnostic messages are routed exclusively to `stderr`.

### Transport B: Streamable HTTP
Streamable HTTP on port 8765, serving the endpoint `http://127.0.0.1:8765/mcp`.

```bash
python -m backend.mcp_server --http --port 8765
```

---

## 3. Client Configuration

### Connecting via Python (`backend.mcp_client.MuleTraceMCPClient`)
Supports three modes selectable via the `MCP_MODE` environment variable or constructor argument:
- `in-process` (default): Direct zero-overhead execution inside the Python interpreter.
- `stdio`: Spawns `python -m backend.mcp_server` as a subprocess and speaks JSON-RPC.
- `http`: Connects to an external or remote streamable HTTP server endpoint.

```python
import asyncio
from backend.mcp_client import MuleTraceMCPClient

async def run():
    client = MuleTraceMCPClient(mode="in-process")
    # Discover tools in Groq tool-calling format (JSON schema)
    tools = await client.list_tools()
    
    # Execute a tool
    result = await client.call_tool("get_fraud_report", {"report_id": "FR_0001"})
    print(result)

asyncio.run(run())
```

### Claude Desktop Integration
Add the following snippet to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "muletrace": {
      "command": "c:/Users/dhanu/Documents/PROJECTS/MuleTrace - HackFest Hackthon/.venv/Scripts/python.exe",
      "args": ["-m", "backend.mcp_server"],
      "env": {
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379",
        "GRAPH_NAME": "muletrace"
      }
    }
  }
}
```

---

## 4. Registered Tools Summary (17 Tools)

| Tool Name | Kind | Summary |
| --- | --- | --- |
| `get_fraud_report` | query | Fetches filed fraud report details, incident narrative, and victim account identity. |
| `get_account_profile` | query | Computes account features (balance, age, volume, forward latency) to evaluate mule vs merchant. |
| `trace_money_forward` | query | Walks outgoing transfers chronologically forward hop-by-hop from a start account. |
| `find_cash_out_points` | query | Identifies terminal ATM withdrawals and crypto exchanges where stolen money exits. |
| `get_balance_held` | query | Inspects current recoverable balances held across candidate mule accounts. |
| `find_shared_devices` | query | Discovers co-conspirator accounts sharing digital hardware/IP identifiers. |
| `find_shared_phones` | query | Discovers synthetic identities sharing registered phone numbers. |
| `detect_rapid_hops` | query | Detects high-velocity pass-through nodes forwarding >=70% of funds within minutes. |
| `detect_fan_in` | query | Detects smurfing aggregator hubs receiving payments from many distinct senders. |
| `detect_fan_out` | query | Detects layering nodes rapidly splitting incoming money to multiple receivers. |
| `get_neighborhood` | query | Fetches the immediate 1- or 2-hop local transaction network around an account. |
| `find_shortest_path` | algorithm | Finds the shortest payment or hybrid device path between two suspect accounts. |
| `rank_hub_accounts` | algorithm | Computes windowed PageRank to flag central transfer hubs in the payment flow. |
| `find_connected_components` | algorithm | Segments the network into weakly connected components over money and device links. |
| `find_communities` | algorithm | Detects tightly-knit account clusters using Louvain modularity optimization. |
| `find_connected_ring` | algorithm | Extracts the full component, community, and hardware links around a suspect account. |
| `rank_chokepoints` | algorithm | Calculates betweenness centrality inside a candidate pool to pinpoint flow bottlenecks. |
| `build_freeze_list` | action | *(Reserved for Phase 11)* Assembles and ranks actionable freeze recommendations. |

---

## 5. Output Size & Compaction Rules

Groq free-tier and small-context models enforce strict context window limits. Every tool output passes through `compact_output`:
1. **Target Budget:** Outputs are constrained to ~3,000 characters.
2. **Field Prioritization:** Non-essential verbose metadata (e.g., merchant descriptions, address details) is dropped first.
3. **Preservation Invariant:** The fields `"path"`, `"truncated"`, and `"total"` are **strictly preserved** even when arrays are sliced.
4. **LLM Guidance:** When truncated, the payload receives `"truncated": true` and a helpful note:
   `"Result truncated to fit token limits. Narrow query using smaller time window, higher min_amount, or smaller top_k/max_hops."`

---

## 6. Error Handling Format

Tools never raise exceptions to the LLM agent. All schema validation errors, missing records, query timeouts (10 seconds), and invalid arguments return a standardized payload:

```json
{
  "error": "Account 'ACC_UNKNOWN' was not found in the graph.",
  "hint": "Verify ID formatting (e.g. account 'ACC_0461') or discover accounts first using trace_money_forward."
}
```

---

## 7. SDK Adaptation Note (MCP 2.x)

The official Python MCP SDK evolved from `mcp 1.x` to `mcp 2.x`:
- In MCP 2.x, `FastMCP` was consolidated into `from mcp.server.mcpserver import MCPServer`.
- `backend/mcp_server.py` defines `FastMCP = MCPServer` for backward compatibility.
- Dynamic tool registration builds explicit Python signatures (`inspect.Signature`) from Pydantic models so parameter types, defaults, and descriptions are seamlessly rendered into standard JSON Schema.

---

## 8. FalkorDB MCP Server for Human Inspection (Optional)

FalkorDB provides an official read-only MCP server repository ([FalkorDB/falkordb-mcp](https://github.com/FalkorDB/falkordb-mcp)).

### Human Analyst Setup
A human investigator can run `falkordb-mcp` side-by-side with MuleTrace in Claude Desktop:

```json
{
  "mcpServers": {
    "muletrace": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"]
    },
    "falkordb_direct": {
      "command": "uvx",
      "args": ["falkordb-mcp", "--host", "localhost", "--port", "6379", "--graph", "muletrace"]
    }
  }
}
```

> [!IMPORTANT]
> **Agent Security Boundary:** The autonomous MuleTrace agent is **never** granted raw Cypher access or connected to `falkordb-mcp`. The agent operates exclusively through MuleTrace's curated domain tools to guarantee bounded execution, token compliance, and prompt safety.
