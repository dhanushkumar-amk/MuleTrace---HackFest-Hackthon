"""Verify the loaded MuleTrace graph against the CSVs and the Phase 5 answer key.

Prints PASS/FAIL for every check and exits non-zero if any check fails. Reads the
graph CSVs for expected counts, queries the graph, and compares against
tests/ground_truth.json (the answer key is read ONLY here — never in the loader or
agent code).

Usage:
    python scripts/verify_graph.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph  # noqa: E402
from scripts.create_schema import INDEXES, existing_indexes  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "generated")
GT_PATH = os.path.join(REPO_ROOT, "tests", "ground_truth.json")
PASSED = True

# labels and the relationship anchored to them (for count checks)
NODE_CSV = {
    "Account": "accounts.csv",
    "Device": "devices.csv",
    "Phone": "phones.csv",
    "CashOutPoint": "cashout_points.csv",
    "Transaction": "transactions.csv",
    "FraudReport": "fraud_reports.csv",
}
REL_CSV = {
    "USES_DEVICE": "account_device.csv",
    "REGISTERED_PHONE": "account_phone.csv",
    "SENT": "transactions.csv",          # all txns send to one account
    "RECEIVED_BY": "transactions.csv",   # txns with a receiver
    "PAID": "paid_edges.csv",
    "CASHED_OUT_AT": "cashed_out_at.csv",
    "REPORTS_VICTIM": "fraud_reports.csv",
}
FORBIDDEN_KEYS = ("ring", "mule", "decoy", "plant")


def report(step: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if not ok:
        PASSED = False
    print(f"[{'PASS' if ok else 'FAIL'}] {step}" + (f" - {detail}" if detail else ""))


def csv_count(name):
    with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8") as fh:
        return sum(1 for _ in fh) - 1


def gcount(graph, query, params=None):
    rs = graph.query(query, params).result_set or []
    return rs[0][0] if rs and rs[0] else 0


def gset(graph, query, params=None, col=0):
    rs = graph.query(query, params).result_set or []
    return {row[col] for row in rs}


# ---------------------------------------------------------------------------
# 1-2. counts
# ---------------------------------------------------------------------------
def check_counts(graph) -> None:
    for label, fname in NODE_CSV.items():
        expected = csv_count(fname)
        got = gcount(graph, f"MATCH (n:{label}) RETURN count(n)")
        report(f"node count {label} == CSV", got == expected, f"graph={got} csv={expected}")
    for rel, fname in REL_CSV.items():
        expected = csv_count(fname)
        if rel == "SENT":
            expected = csv_count("transactions.csv")
        elif rel == "RECEIVED_BY":
            with open(os.path.join(DATA_DIR, "transactions.csv"), newline="",
                      encoding="utf-8") as fh:
                expected = sum(1 for r in csv.DictReader(fh) if r["receiver_account_id"])
        got = gcount(graph, f"MATCH ()-[r:{rel}]->() RETURN count(r)")
        report(f"relationship count {rel} == CSV", got == expected,
               f"graph={got} csv={expected}")


# ---------------------------------------------------------------------------
# 3. duplicates
# ---------------------------------------------------------------------------
def check_duplicates(graph) -> None:
    for label in NODE_CSV:
        total = gcount(graph, f"MATCH (n:{label}) RETURN count(n)")
        distinct = gcount(graph, f"MATCH (n:{label}) RETURN count(DISTINCT n.id)")
        report(f"no duplicate ids in {label}", total == distinct,
               f"total={total} distinct={distinct}")


# ---------------------------------------------------------------------------
# 4. no orphans
# ---------------------------------------------------------------------------
def check_no_orphans(graph) -> None:
    bad_sent = gcount(graph, (
        "MATCH (n:Transaction) OPTIONAL MATCH ()-[s:SENT]->(n) "
        "WITH n, count(s) AS c WHERE c <> 1 RETURN count(n)"))
    report("every Transaction has exactly one SENT", bad_sent == 0, f"bad={bad_sent}")

    # cash-out transactions (ATM/CRYPTO) legitimately have zero RECEIVED_BY; they
    # carry a CASHED_OUT_AT edge instead. So: no txn has >1, and the #with 0 equals
    # the #CASHED_OUT_AT edges.
    no_recv = gcount(graph, (
        "MATCH (n:Transaction) OPTIONAL MATCH (n)-[r:RECEIVED_BY]->() "
        "WITH n, count(r) AS c WHERE c = 0 RETURN count(n)"))
    over_recv = gcount(graph, (
        "MATCH (n:Transaction) OPTIONAL MATCH (n)-[r:RECEIVED_BY]->() "
        "WITH n, count(r) AS c WHERE c > 1 RETURN count(n)"))
    n_cash = csv_count("cashed_out_at.csv")
    report("every inter-account transaction has exactly one RECEIVED_BY, "
           "cash-out transactions have none", over_recv == 0 and no_recv == n_cash,
           f"over={over_recv} with_zero={no_recv} cashouts={n_cash}")

    txn_ids = gset(graph, "MATCH (t:Transaction) RETURN t.id")
    paid_txn = gset(graph, "MATCH ()-[p:PAID]->() RETURN DISTINCT p.txn_id")
    missing = paid_txn - txn_ids
    report("every PAID edge has a matching Transaction id", not missing,
           f"missing={len(missing)}")


# ---------------------------------------------------------------------------
# 5. indexes  6. balance sum
# ---------------------------------------------------------------------------
def check_indexes(graph) -> None:
    have = existing_indexes(graph)
    missing = [i for i in INDEXES if i not in have]
    report("all schema indexes exist", not missing, f"missing={missing}")


def check_balance(graph) -> None:
    expected = 0
    with open(os.path.join(DATA_DIR, "accounts.csv"), newline="",
              encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            expected += int(r["balance_held"])
    got = gcount(graph, "MATCH (a:Account) RETURN sum(a.balance_held)")
    report("sum(balance_held) == CSV", got == expected, f"graph={got} csv={expected}")


# ---------------------------------------------------------------------------
# 7. no suspicious property keys
# ---------------------------------------------------------------------------
def check_property_keys(graph) -> None:
    ks = gset(graph, "MATCH (n) UNWIND keys(n) AS k RETURN DISTINCT k")
    bad = sorted(k for k in ks if any(f in k.lower() for f in FORBIDDEN_KEYS))
    report("no suspicious (ring/mule/decoy/planted) property keys", not bad,
           f"keys={sorted(ks)} bad={bad}")


# ---------------------------------------------------------------------------
# 8. Ravi + Ring 1 multi-hop (answer key allowed here)
# ---------------------------------------------------------------------------
def check_ravi_and_ring1(graph, gt) -> None:
    ravi = gt["victim_account_id"]
    report(f"Ravi ({ravi}) exists", gcount(graph, f"MATCH (a:Account {{id:'{ravi}'}}) RETURN count(a)") == 1)
    report("Ravi has a linked FraudReport",
           gcount(graph, f"MATCH (f:FraudReport {{victim_account_id:'{ravi}'}})-[:REPORTS_VICTIM]->(:Account {{id:'{ravi}'}}) RETURN count(f)") >= 1)

    # multi-hop forward-in-time trace from Ravi (mirrors trace_money_forward)
    reported_at = gt["reported_at"]
    t0 = reported_at - 6300          # theft ~1h45m before report
    t1 = t0 + 1800                     # chain completes in ~10 min
    start = time.time()
    rs = graph.query(
        "MATCH p=(a:Account {id:$start})-[:PAID*1..6]->(b:Account) "
        "WHERE ALL(r IN relationships(p) WHERE r.timestamp >= $t0 AND r.timestamp <= $t1) "
        "RETURN [n IN nodes(p) | n.id] AS path, [r IN relationships(p) | r.timestamp] AS times",
        {"start": ravi, "t0": t0, "t1": t1}).result_set or []
    elapsed = time.time() - start
    # keep only strictly forward-in-time paths
    forward = [row for row in rs if all(a < b for a, b in zip(row[1], row[1][1:]))]
    reachable = set()
    for path, _ in forward:
        reachable.add(path[-1])
    r1 = gt["rings"]["1"]
    mules = set(r1["accounts"])
    found = mules <= reachable
    report("Ring 1 chain reachable from Ravi within 6 forward-in-time hops",
           found, f"found={sorted(reachable & mules)}/len={len(mules)}")
    report(f"multi-hop query timing ({(elapsed*1000):.0f} ms)", elapsed < 1.0)


# ---------------------------------------------------------------------------
# 9. shared device  10. decoy
# ---------------------------------------------------------------------------
def check_shared_device(graph, gt) -> None:
    link = gt["shared_device_link"]
    rs = graph.query(
        "MATCH (:Account {id:$b})-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(o:Account) "
        "RETURN d.id, collect(DISTINCT o.id) AS others", {"b": link["ring1_account"]}
    ).result_set or []
    matches = {row[0]: set(row[1]) for row in rs}
    ok = link["device_id"] in matches and link["ring2_account"] in matches[link["device_id"]]
    report("shared device links Ring 1 Mule B to Ring 2 (Cypher)", ok,
           f"link={link}")


def check_decoy(graph, gt) -> None:
    decoy = gt["decoy_account_id"]
    n = gcount(graph, f"MATCH (:Account {{id:'{decoy}'}})<-[p:PAID]-() RETURN count(p)")
    report(f"decoy has >=60 incoming PAID edges (got {n})", n >= 60)


# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=DATA_DIR, help="generated data directory")
    args = parser.parse_args()

    graph = get_graph()
    with open(GT_PATH, encoding="utf-8") as fh:
        gt = json.load(fh)
    print(f"== verifying graph {graph.name} ==")

    check_counts(graph)
    check_duplicates(graph)
    check_no_orphans(graph)
    check_indexes(graph)
    check_balance(graph)
    check_property_keys(graph)
    check_ravi_and_ring1(graph, gt)
    check_shared_device(graph, gt)
    check_decoy(graph, gt)

    print("=" * 40)
    if PASSED:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())