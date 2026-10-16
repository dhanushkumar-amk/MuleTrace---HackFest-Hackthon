# Freeze-List Ranking and Memory Write-Back Specification (Phase 11)

## 1. Overview and Core Philosophy

MuleTrace is an AI-powered financial fraud investigation system built for FalkorDB (Track 01 & Track 02). 
A central tenet of the system is:

> **The system NEVER executes an automated account freeze. Every output is strictly a recommendation for human review.**

While the autonomous agent discovers money trails, identifies mule rings, and proposes suspects, the candidate freeze list is independently re-verified against the graph in deterministic Python (`backend/freeze.py`). Even if an LLM hallucinates or is prompted to freeze an arbitrary account, the underlying engine rejects accounts failing money-trail or behavioral checks.

---

## 2. Freeze-List Scoring & Verification Rules

`build_freeze_list(candidates, case_context)` re-verifies each candidate account against FalkorDB:

### A. Money-Trail Verification
1. The candidate must be reachable from the victim's account via a strictly time-ordered sequence of `PAID` edges.
2. The shortest money-trail path must be at least **2 hops** away from the victim (`hops >= 2`). Immediate Layer 1 accounts that merely pass funds through with zero retained balance are excluded from priority freezing.
3. Every path records transaction IDs, amounts, and strictly increasing timestamps.

### B. Independent Behavioral Signals
An account must exhibit **Signal 3 (victim money trail)** plus at least **2 additional independent behavioral signals** (or total signals >= 3) to qualify for freeze ranking:
1. **Rapid Forwarding**: >= 70% of inbound funds forwarded onward within 10 minutes (detected via `detect_rapid_hops`).
2. **Fan-Out Split**: Splitting inbound stolen funds across multiple outbound recipients (detected via `detect_fan_out`).
3. **Victim Trail Reachability**: Verified arrival of stolen funds along the time-ordered directed path.
4. **Low Forward Latency**: Median onward forwarding latency significantly lower than normal retail account baselines (< 15 minutes).
5. **Shared Infrastructure**: Sharing a device (`DEV_*`) or phone (`PH_*`) with another candidate or mule account.

*Note: High inflow or high PageRank alone NEVER counts as a signal.*

### C. Legitimate-Merchant Guard (Decoy Protection)
In organized UPI mule operations, fraudsters deliberately route a portion of stolen money to innocent third-party merchants (grocery stores, retail outlets, recharge portals) to create decoy trails.
- **Guard Condition**: If an account has many distinct unrelated senders (>= 15 senders, or >= 5 senders with 0 outbound forwarding), slow or no onward forwarding, and a stable single device and phone, it is automatically intercepted by the merchant guard.
- **Outcome**: The account is placed in the `not_recommended` list with a detailed behavioral rationale (e.g. *"Legitimate merchant profile: high distinct senders with zero rapid forwarding"*), preventing false-positive freezes.

### D. Recoverable Money at Stake & Downstream Cashed Out
- `amount_recoverable`: Current balance held in the graph (`Account.balance_held`).
- `amount_already_cashed_out`: ATM or branch cash withdrawals downstream of this account along the money trail, calculated for investigative context.

### E. Ranking & Tiebreaking Order
Candidates are ranked into Priority $1 \dots N$:
1. **Primary Key**: `amount_recoverable` descending (prioritize accounts where maximum victim money can still be saved).
2. **First Tiebreaker**: Earliest position in the chain / shortest hops (freeze upstream choke-points first before downstream dispersal).
3. **Second Tiebreaker**: Count of independent behavioral signals descending.

### F. Confidence Classification
- **High**: >= 3 independent behavioral signals AND `amount_recoverable > 0`.
- **Medium**: Exactly 2 independent behavioral signals AND `amount_recoverable > 0`.
- **Low / Excluded**: Accounts with 0 balance held (flagged as *"already emptied, do not prioritize"*), or accounts with insufficient signals. Placed in `not_recommended` or unranked.

---

## 3. Ground Truth Verification: Ravi Kumar's Case (FR_0001)

When evaluated on the reference case `FR_0001` (Ravi Kumar, victim `ACC_0461`, Rs 100,000 theft), `build_freeze_list` produces:

| Priority | Account | Bank | Recoverable | Confidence | Path Text |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `ACC_0463` | Axis Bank | **Rs 40,000** | High | `ACC_0461 -> ACC_0462 -> ACC_0463` |
| **2** | `ACC_0466` | State Bank of India | **Rs 15,000** | High | `ACC_0461 -> ACC_0462 -> ACC_0464 -> ACC_0465 -> ACC_0466` |
| **3** | `ACC_0464` | HDFC Bank | **Rs 1,000** | High | `ACC_0461 -> ACC_0462 -> ACC_0464` |
| **4** | `ACC_0465` | ICICI Bank | **Rs 1,000** | High | `ACC_0461 -> ACC_0462 -> ACC_0464 -> ACC_0465` |

- **Total Recoverable**: **Rs 57,000**
- **Total Cashed Out Downstream**: **Rs 28,000** (at ATM by `ACC_0466`)
- **Excluded / Not Recommended**:
  - `ACC_0476` (Decoy): *Legitimate merchant guard: 62 distinct senders, single device/phone, zero forwarding.*
  - `ACC_0462` (Layer 1 Mule A): *Hops < 2 and balance held is Rs 0 (already emptied).*

---

## 4. Memory Model & Graph Write-Back (Track 02 Bonus)

The write-back engine (`backend/memory.py` via `save_case_to_memory`) persists verified investigation findings back to FalkorDB.

### Graph Schema Extensions

```mermaid
graph TD
    FR[FraudReport<br/>id: FR_0001]
    C[Case<br/>id: CASE_FR_0001<br/>status: completed]
    A1[Account: ACC_0463<br/>is_flagged: true<br/>risk_score: 0.90]
    A2[Account: ACC_0466<br/>is_flagged: true<br/>risk_score: 0.90]
    PC[Case: Earlier Case<br/>id: CASE_FR_0000]

    C -->|INVOLVES| A1
    C -->|INVOLVES| A2
    A1 -->|FLAGGED_IN {confidence, priority, amount}| FR
    A2 -->|FLAGGED_IN {confidence, priority, amount}| FR
    C -.->|LINKED_TO| PC
```

### Write Constraints & Invariants
1. **Allowed Writes Only**:
   - `Case` nodes: `{id, report_id, created_at, summary, status}`.
   - `(:Account)-[:FLAGGED_IN {confidence, priority, amount_recoverable, signals, at}]->(:FraudReport)`.
   - `(:Case)-[:INVOLVES]->(:Account)`.
   - `(:Case)-[:LINKED_TO]->(:Case)`.
   - `Account.is_flagged = true` and `Account.risk_score` (float $0.0 \dots 1.0$).
2. **Forbidden Labels & Properties**:
   - Never writes labels like `Mule`, `Decoy`, `Ring`, or properties like `ring_id`.
3. **Strict Validation**:
   - Only accounts appearing in the last verified `build_freeze_list` result may be written to memory.
4. **Idempotence**:
   - Uses `MERGE` on unique IDs (`Case.id`, `FLAGGED_IN` edges) so multiple executions update in place without duplicate nodes or edges.

### Recall Tool: `recall_past_cases(account_ids)`
Allows the agent on subsequent investigations to query whether candidate accounts (or accounts sharing devices/phones with them) were involved in prior cases, enabling cross-case intelligence and faster ring discovery.
