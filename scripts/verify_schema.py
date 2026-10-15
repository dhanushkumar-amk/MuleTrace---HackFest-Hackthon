"""Verify every MuleTrace node and relationship type against the live schema.

Inserts a tiny sample of every node + relationship type, runs one query per
relationship, prints PASS/FAIL, then deletes the sample data. Leaves the graph
exactly as it found it. Exits non-zero if any check fails.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph

RUN = uuid.uuid4().hex[:6]
VICTIM = f"{RUN}-victim"
MULE = f"{RUN}-mule"
DEVICE = f"{RUN}-dev"
PHONE = f"{RUN}-phone"
TX1 = f"{RUN}-tx1"
TX2 = f"{RUN}-tx2"
ATM = f"{RUN}-atm"
REPORT = f"{RUN}-report"

PASSED = True


def report(step: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if not ok:
        PASSED = False
    status = "PASS" if ok else "FAIL"
    marker = "OK " if ok else "XX "
    line = f"[{status}] {step}"
    if detail:
        line += f" - {detail}"
    print(f"{marker}{line}")


def run_check(graph, step: str, query: str, col_index: int, expected) -> None:
    """Run a query and PASS if expected is a subset of the returned values in col."""
    try:
        rows = graph.query(query).result_set or []
        got = {row[col_index] for row in rows}
        want = set(expected) if isinstance(expected, (list, tuple, set)) else {expected}
        ok = want.issubset(got)
        report(step, ok, f"got={sorted(got, key=str)}")
    except Exception as exc:  # pragma: no cover - failure path
        report(step, False, str(exc))


def main() -> int:
    graph = get_graph()

    print(f"== MuleTrace schema verification (graph={graph.name}, run={RUN}) ==")

    # --- 1. Insert one tiny example of every node type ---------------------
    create = f"""
    CREATE
      (v:Account {{id:'{VICTIM}', holder_name:'Ravi', bank:'Bank X', account_type:'individual', opened_at:1000, balance_held:85000, is_flagged:false, risk_score:0}}),
      (m:Account {{id:'{MULE}', holder_name:'Mule A', bank:'Bank Y', account_type:'mule_suspect', opened_at:1000, balance_held:40000, is_flagged:false, risk_score:0}}),
      (d:Device   {{id:'{DEVICE}', device_fingerprint:'fp-1', os:'android'}}),
      (p:Phone    {{id:'{PHONE}', number:'+91 90000 00000'}}),
      (t1:Transaction {{id:'{TX1}', amount:5000, timestamp:1100, channel:'UPI', status:'SUCCESS'}}),
      (t2:Transaction {{id:'{TX2}', amount:4000, timestamp:1200, channel:'IMPS', status:'SUCCESS'}}),
      (c:CashOutPoint {{id:'{ATM}', kind:'ATM', name:'ATM-9', location:'MG Road'}}),
      (fr:FraudReport {{id:'{REPORT}', victim_account_id:'{VICTIM}', amount:85000, reported_at:1300, description:'fake KYC call'}})
    """
    try:
        graph.query(create)
        report("insert sample nodes (6 node labels)", True)
    except Exception as exc:  # pragma: no cover - failure path
        report("insert sample nodes (6 node labels)", False, str(exc))
        _cleanup(graph)
        print("SOME CHECKS FAILED")
        return 1

    # --- 2. Wire up every relationship type --------------------------------
    rels = f"""
    MATCH (v:Account {{id:'{VICTIM}'}}), (m:Account {{id:'{MULE}'}}),
          (d:Device {{id:'{DEVICE}'}}), (p:Phone {{id:'{PHONE}'}}),
          (t1:Transaction {{id:'{TX1}'}}), (t2:Transaction {{id:'{TX2}'}}),
          (c:CashOutPoint {{id:'{ATM}'}}), (fr:FraudReport {{id:'{REPORT}'}})
    CREATE
      (v)-[:SENT]->(t1)-[:RECEIVED_BY]->(m),
      (v)-[:SENT]->(t2)-[:RECEIVED_BY]->(m),
      (v)-[:PAID {{amount:5000, timestamp:1100, txn_id:'{TX1}'}}]->(m),
      (v)-[:USES_DEVICE {{first_seen:1000, last_seen:1300}}]->(d),
      (v)-[:REGISTERED_PHONE]->(p),
      (v)-[:CASHED_OUT_AT {{amount:3000, timestamp:1250}}]->(c),
      (fr)-[:REPORTS_VICTIM]->(v),
      (v)-[:FLAGGED_IN]->(fr)
    """
    try:
        graph.query(rels)
        report("insert all 8 relationship types", True)
    except Exception as exc:  # pragma: no cover - failure path
        report("insert all 8 relationship types", False, str(exc))
        _cleanup(graph)
        print("SOME CHECKS FAILED")
        return 1

    # --- 3. One query per relationship -------------------------------------
    run_check(graph, "SENT (Account)-[:SENT]->(Transaction)", 
              f"MATCH (v:Account {{id:'{VICTIM}'}})-[:SENT]->(t:Transaction) RETURN t.id",
              0, [TX1, TX2])
    run_check(graph, "RECEIVED_BY (Transaction)-[:RECEIVED_BY]->(Account)",
              f"MATCH (:Transaction)-[:RECEIVED_BY]->(m:Account {{id:'{MULE}'}}) RETURN m.id",
              0, MULE)
    run_check(graph, "PAID (Account)-[:PAID]->(Account)",
              f"MATCH (:Account {{id:'{VICTIM}'}})-[:PAID {{txn_id:'{TX1}'}}]->(m:Account) RETURN m.id",
              0, MULE)
    run_check(graph, "USES_DEVICE (Account)-[:USES_DEVICE]->(Device)",
              f"MATCH (:Account {{id:'{VICTIM}'}})-[:USES_DEVICE]->(d:Device) RETURN d.id",
              0, DEVICE)
    run_check(graph, "REGISTERED_PHONE (Account)-[:REGISTERED_PHONE]->(Phone)",
              f"MATCH (:Account {{id:'{VICTIM}'}})-[:REGISTERED_PHONE]->(p:Phone) RETURN p.number",
              0, "+91 90000 00000")
    run_check(graph, "CASHED_OUT_AT (Account)-[:CASHED_OUT_AT]->(CashOutPoint)",
              f"MATCH (:Account {{id:'{VICTIM}'}})-[:CASHED_OUT_AT]->(c:CashOutPoint) RETURN c.id",
              0, ATM)
    run_check(graph, "REPORTS_VICTIM (FraudReport)-[:REPORTS_VICTIM]->(Account)",
              f"MATCH (:FraudReport {{id:'{REPORT}'}})-[:REPORTS_VICTIM]->(v:Account) RETURN v.id",
              0, VICTIM)
    run_check(graph, "FLAGGED_IN (Account)-[:FLAGGED_IN]->(FraudReport)",
              f"MATCH (:Account {{id:'{VICTIM}'}})-[:FLAGGED_IN]->(fr:FraudReport) RETURN fr.id",
              0, REPORT)

    # --- 4. Sanity: every node label has sample data -----------------------
    for label in ("Account", "Device", "Phone", "Transaction", "CashOutPoint", "FraudReport"):
        try:
            rows = graph.query(f"MATCH (n:{label}) RETURN count(*)").result_set or []
            n = rows[0][0] if rows else 0
            report(f"node label {label} has sample data", n >= 1, f"count={n}")
        except Exception as exc:  # pragma: no cover - failure path
            report(f"node label {label} has sample data", False, str(exc))

    # --- 5. Clean up -------------------------------------------------------
    left = _cleanup(graph)
    print("=" * 40)
    if PASSED:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


def _cleanup(graph) -> int:
    """Delete the sample nodes (and their relationships), report leftovers."""
    ids = [VICTIM, MULE, DEVICE, PHONE, TX1, TX2, ATM, REPORT]
    deleted = 0
    for node_id in ids:
        try:
            res = graph.query("MATCH (n {id:$id}) DETACH DELETE n RETURN count(*) AS c",
                              {"id": node_id})
            rows = res.result_set or []
            deleted += rows[0][0] if rows and rows[0][0] else 0
        except Exception as exc:  # pragma: no cover - failure path
            print(f"[warn] cleanup {node_id}: {exc}", file=sys.stderr)
    try:
        rows = graph.query("MATCH (n {id:$run}) RETURN count(*) AS leftover", {"run": RUN}).result_set or []
        leftover = rows[0][0] if rows and rows[0][0] else 0
    except Exception:
        leftover = 0
    report("cleanup sample data", deleted >= 8 and leftover == 0, f"deleted={deleted} leftover={leftover}")
    return deleted


if __name__ == "__main__":
    sys.exit(main())