# MuleTrace — Explainability Engine (Phase 12)

## 1. Overview & Core Philosophy

MuleTrace is an AI-powered financial fraud investigation system built for FalkorDB (Track 01 & Track 02). 
A foundational principle of Phase 12 is:

> **Facts come strictly from data (FalkorDB graph queries and trace log), NEVER from LLM generation. The LLM must not write or alter any fact, path, amount, or identifier in an explanation.**

Every explanation produced by the engine carries the explicit disclaimer:
`"recommendation for human review, nothing was frozen"`.

---

## 2. Explanation Schema

The explainability engine (`backend/explain.py`) provides pure Python, unit-testable functions yielding structured JSON models for UI rendering and compliance auditing.

### A. Case Explanation (`explain_case(session_id)`)
```json
{
  "case_header": {
    "case_id": "CASE_FR_0001",
    "session_id": "session_1792173229108",
    "report_id": "FR_0001",
    "victim_name": "Ravi Kumar",
    "victim_account": "ACC_0461",
    "amount_stolen": 85000,
    "reported_at": 1792044900,
    "total_recoverable": 57000,
    "total_cashed_out": 28000,
    "recommendation_only": true
  },
  "disclaimer": "recommendation for human review, nothing was frozen",
  "verified": true,
  "verification": {
    "verified": true,
    "badge": "verified: true",
    "checks_passed": 36,
    "total_checks": 36,
    "failed_items": []
  },
  "recommendations": [...],
  "rejections": [...],
  "links": [...],
  "timeline": [...],
  "highlight": {...},
  "other_patterns": [...],
  "limitations": [...]
}
```

### B. Recommendation Item (`explain_recommendation`)
- `account`: Target candidate account ID.
- `priority`: Rank priority (1..N).
- `headline`: One-line summary (e.g. *"Freeze first: holds Rs 40,000"*).
- `path`: Ordered nodes (`id`, `label`, `bank`) and edges (`txn_id`, `amount`, `timestamp`, `gap_seconds`).
- `path_text`: Directed chain string (`Ravi -> ACC_0462 -> ACC_0463`).
- `signals`: Ordered risk signals with plain-English names, values, and evidence tool call IDs.
- `money`: `{"recoverable": 40000, "cashed_out_downstream": 0}`.
- `confidence`: `"high" | "medium" | "low"`.
- `steps`: Ordered list of human-readable "because" lines, each citing its tool call ID.
- `counter_evidence`: Innocent merchant hypothesis check and verdict.
- `tool_calls`: Audit list of relevant tool calls (`call_id`, `tool`, `args_summary`, `duration_ms`).

### C. Rejection Item (`explain_rejection`)
- `account`: Cleared account ID.
- `headline`: e.g. *"Not recommended: behaves like a legitimate merchant"*.
- `counter_evidence`: Behavioral facts (`distinct_senders`, `forward_latency`, `device_stability`, `phone_stability`, `onward_ratio`) and explanation of why high inflow or high PageRank was not enough.
- `steps`: Deterministic justification lines citing tool call IDs.

### D. Cross-Ring Link (`explain_link`)
- `account_a`, `account_b`: Linked accounts across disparate rings.
- `shared_type`: `"device"` or `"phone"`.
- `shared_id`: Hardware or phone identifier.
- `total_sharers`: Count of accounts co-using the identifier.
- `strength`: `"strong"` (rare sharing $\le 3$) or `"weak"` ($> 3$).
- `path`: `[account_a, shared_id, account_b]`.

### E. Graph Highlight Subgraph (`build_graph_highlight`)
- `nodes`: `[{id, role, label}]` capped at 40 nodes.
- `edges`: `[{source, target, type, txn_id, amount, timestamp, role, sequence_index}]` capped at 60 edges.
- `sequence_index`: Strictly ascending 1..N order based on timestamps, allowing the UI to animate the money flow hop by hop in time order.
- `legend`: Visual definitions for `victim`, `mule_recommended`, `cash_out`, `cleared`, `linked_ring`, `shared_device`, `other`.

---

## 3. Sample Explanations (Ravi Kumar FR_0001)

### Top Recommendation Explanation (Mule B / ACC_0463)
```markdown
### 1. Freeze ACC_0463, holds Rs 40,000 [HIGH CONFIDENCE]
- **Path**: `Ravi -> ACC_0462 -> ACC_0463`
- **Why**: Received funds directly along time-ordered money trail from victim, Shares hardware device with other suspect or mule accounts, Multi-recipient dispersal pattern on trail.
- **Checked for innocent explanation**: Innocent explanation ruled out. Account demonstrates characteristics of an active mule holding stolen funds.
- **Audit Evidence Trail**:
  - Because received funds originating from the victim's stolen money trail at 2 hops (linked to call_002)
  - Because currently holds Rs 40,000 in recoverable balance (linked to call_004)
  - Because co-uses hardware device infrastructure with other fraud network accounts (linked to call_011)
  - Because participated in fan-out dispersal of stolen funds (linked to call_002)
  - Because verified by automated graph rules and ranked at priority #1 (linked to call_020)
```

### Decoy Rejection Explanation (ACC_0476)
```markdown
### ACC_0476: Not recommended: behaves like a legitimate merchant
- **Behavioral Facts**: 62 distinct senders, forward latency median > 3600s, single private hardware device, onward ratio 0.04.
- **Superficially Suspicious Signals Considered**: High inflow (Rs 420,000) and high PageRank reflect legitimate retail customer volume with 62 distinct senders, private single-device infrastructure, and slow/no onward forwarding (onward ratio 0.04). High inflow or PageRank alone is never sufficient evidence of mule activity.
```

---

## 4. Verification Engine (`backend/explain_verify.py`)

Every generated case explanation passes through `verify_explanation(explanation)`:
1. **Account Existence**: Batched Cypher query confirms every named account exists in FalkorDB.
2. **Transaction Existence & Accuracy**: Every `txn_id` cited along recommendation paths exists in the graph, with amount and timestamp matching the live `Transaction` record exactly.
3. **Strict Time Ordering**: Timestamps strictly increase along each recommendation path ($t_i > t_{i-1}$).
4. **Call ID Provenance**: Every cited `call_id` in signals, steps, and tool panels exists in the session trace log.
5. **Conservation of Money**: Sum of recoverable amounts across all recommendations matches `total_recoverable`.

If all checks pass, the explanation receives `"verified": true` and badge `VERIFIED: TRUE`. If any check fails, `"verified": false` is set with detailed itemized failure reasons.

---

## 5. Traceability: Facts From Data, Not From LLM

| Conventional Agent Approach | MuleTrace Deterministic Explainability |
| :--- | :--- |
| LLM synthesizes explanation text from scratch | Explanation structure built deterministically in Python from graph queries and trace log |
| Susceptible to hallucinated amounts, dates, or accounts | 0 invented tokens; verified against live FalkorDB graph |
| Difficult to verify which tool proved which claim | Every claim step explicitly references an immutable `call_id` from the trace log |
| Unpredictable legal and regulatory exposure | Verifiable audit log meeting strict banking compliance requirements (RBI / FinCEN) |

### Optional LLM Polish Safeguard
When optional summary polish is enabled (`--polish`), the LLM (Groq, temperature 0) receives only the completed explanation JSON. A strict post-generation Python check extracts every number and account ID in the generated text; if any number or identifier is not present verbatim in the explanation JSON, the polished output is **immediately discarded** and the deterministic fallback summary is retained.
