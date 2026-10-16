# MuleTrace — Autonomous Investigation Agent (Phases 10-11)

## 1. Overview & Agent Philosophy

The MuleTrace agent is an autonomous, tool-calling AI agent powered exclusively by Groq (`backend/llm.py`), designed for financial fraud tracing and mule ring discovery on FalkorDB.

### Core Principles
- **Autonomous Tool Selection**: The agent decides which tools to call, in what order, and with what parameters. There is **no hardcoded sequence**.
- **Recommendation Only**: The system never freezes accounts directly. Every freeze recommendation is labeled `recommendation_only: true` for human review.
- **Independent Verification**: The agent names candidate accounts, but `build_freeze_list` independently validates money-trail reachability (>= 2 hops) and behavioral signals in pure Python against FalkorDB.
- **Evidence-Grounded Ledger**: The `EvidenceLedger` captures all tool inputs and outputs. Grounding verification ensures 0 claims are hallucinated or retyped by the LLM.

---

## 2. Agent Architecture

```
                    +------------------------------------+
                    |         User Prompt / Query        |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |        SYSTEM_PROMPT (Principles)   |
                    |   (No sequences; investigative goals)|
                    +-----------------+------------------+
                                      |
                                      v
          +-----------------> [Groq LLM Client] <------------------+
          |           (qwen/qwen3.8-27b, temp=0.0)                 |
          |                           |                             |
          | Context Compaction        | Function Call               | Tool Output
          | (<1,500 tokens)           v                             | (Compacted)
          |                 +--------------------+                  |
          |                 | MuleTraceMCPClient |                  |
          |                 +---------+----------+                  |
          |                           |                             |
          |                           v                             |
          |                 +--------------------+                  |
          |                 |   Tool Registry    |                  |
          |                 +---------+----------+                  |
          |                           |                             |
          |            +--------------+---------------+             |
          |            |                              |             |
          |            v                              v             |
          |   [Queries & Algorithms]        [build_freeze_list]     |
          |   (FalkorDB Graph Read)         [save_case_to_memory]   |
          |            |                    [recall_past_cases]     |
          |            |                              |             |
          +------------+------------------------------+-------------+
```

---

## 3. Tool Descriptions & Registry Evolution

The agent discovers tools dynamically via MCP. Descriptions are kept strictly under 80 words and clearly specify:
1. **When to use the tool**: Objective and prerequisite data.
2. **When NOT to use the tool**: What it cannot prove, or prerequisites required before calling.
3. **Behavioral guarantees**: Deterministic verification, compaction, and truncation behavior.

### Phase 11 Additions:
- `build_freeze_list` (`action`): Independently re-verifies candidates against the graph (>= 2 hops from victim, >= 2 independent behavioral signals, legitimate merchant guard). Sorts by recoverable amount descending.
- `save_case_to_memory` (`action`): Idempotently persists `Case` nodes, `FLAGGED_IN`, `INVOLVES`, `LINKED_TO` edges, `is_flagged=true`, and `risk_score` for accounts appearing in the verified freeze list.
- `recall_past_cases` (`query`): Queries previous cases linked directly to candidates or via shared devices/phones.

---

## 4. Context Budget & Compaction Strategies

To operate reliably on Groq's free tier token per minute (TPM) limits:
1. **Tool Definition Optimization**: Stripped redundant Pydantic schema titles from tool schemas in `backend/mcp_client.py`, saving >20% schema overhead.
2. **Result Compaction (`_compact_for_llm`)**:
   - `build_freeze_list`: Drops internal debug fields (`edge_facts`, `evidence_call_ids`) while keeping paths, amounts, and reasons.
   - `get_account_profile`: Retains only key metrics (`holder_name`, `bank`, `balance_held`, shared device/phone counts, distinct senders/receivers); strips verbose raw timestamp lists.
   - `find_shared_devices` / `find_shared_phones`: Collapses empty results to `{}`.
3. **Turn Windowing**: Truncates older tool messages (> 6 turns back) while keeping tool call IDs intact to ensure schema compliance without context explosion.

---

## 5. Iterations and Fixes Log

| Issue Encountered | Root Cause | Fix Applied | Result |
| :--- | :--- | :--- | :--- |
| Tracing returned 0 hops | `reported_at` occurred ~1.75h after theft (`1792038600` vs `1792044900`) | Updated prompt principle to start tracing ~2 hours before `reported_at` | Agent successfully traces all 4 hops of stolen funds |
| Groq 429 TPM limit | Large cumulative messages across 5 steps exceeded 8,000 TPM | Enforced aggressive profile compaction and message trimming in `backend/agent.py` | Context size reduced by >60%; runs execute reliably |
| Tool output grounding | LLM slightly modified account IDs when producing markdown tables | Fixed `run_investigation` to take `freeze_list` strictly from tool output in Python | 0 claims removed; 100% deterministic grounding |
