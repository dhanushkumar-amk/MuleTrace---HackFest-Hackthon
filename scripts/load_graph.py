"""Load the merged Phase 5 CSVs (data/generated/) into the FalkorDB graph.

All nodes are MERGEd on their unique `id` and all relationships are MERGEd on their
structural key (PAID is keyed by txn_id, CASHED_OUT_AT by timestamp) so the loader
is idempotent: running it twice never creates duplicates. Rows are pushed with
batched `UNWIND $rows` queries (batch ~500) and CSV types are converted (numbers as
numbers, booleans as booleans, timestamps as integer epoch seconds).

Load order (matches docs/SCHEMA.md):
  nodes:   Account, Device, Phone, CashOutPoint, Transaction, FraudReport
  rels:    USES_DEVICE, REGISTERED_PHONE, SENT, RECEIVED_BY, PAID,
           CASHED_OUT_AT, REPORTS_VICTIM

Only graph-bound CSVs from data/generated/ are read. It never reads tests/ or docs/.

Usage:
    python scripts/load_graph.py              # idempotent load (MERGE)
    python scripts/load_graph.py --reset      # delete graph, rebuild indexes, load
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph  # noqa: E402
from scripts.create_schema import INDEXES, existing_indexes  # noqa: E402

from redis.exceptions import ResponseError  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data", "generated")
BATCH = 500


def _read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# CSV -> typed parameter maps
# ---------------------------------------------------------------------------
def accounts(row):
    return {"id": row["id"], "holder_name": row["holder_name"], "bank": row["bank"],
            "account_type": row["account_type"], "opened_at": int(row["opened_at"]),
            "balance_held": int(row["balance_held"]),
            "is_flagged": row["is_flagged"].strip().lower() == "true",
            "risk_score": int(row["risk_score"])}


def devices(row):
    return {"id": row["id"], "device_fingerprint": row["device_fingerprint"],
            "os": row["os"]}


def phones(row):
    return {"id": row["id"], "number": row["number"]}


def cashouts(row):
    return {"id": row["id"], "kind": row["kind"], "name": row["name"],
            "location": row["location"]}


def transactions(row):
    return {"id": row["id"], "amount": int(row["amount"]),
            "timestamp": int(row["timestamp"]), "channel": row["channel"],
            "status": row["status"]}


def fraud_reports(row):
    return {"id": row["id"], "victim_account_id": row["victim_account_id"],
            "amount": int(row["amount"]), "reported_at": int(row["reported_at"]),
            "description": row["description"]}


def account_device(row):
    return {"account_id": row["account_id"], "device_id": row["device_id"],
            "first_seen": int(row["first_seen"]), "last_seen": int(row["last_seen"])}


def account_phone(row):
    return {"account_id": row["account_id"], "phone_id": row["phone_id"]}


def paid_edge(row):
    return {"src": row["src"], "dst": row["dst"], "amount": int(row["amount"]),
            "timestamp": int(row["timestamp"]), "txn_id": row["txn_id"]}


def cashed_out(row):
    return {"account_id": row["account_id"], "cashout_point_id": row["cashout_point_id"],
            "amount": int(row["amount"]), "timestamp": int(row["timestamp"])}


# ---------------------------------------------------------------------------
# Batched loader
# ---------------------------------------------------------------------------
def load_batches(graph, rows, query, label):
    n = len(rows)
    t0 = time.time()
    done = 0
    for i in range(0, n, BATCH):
        batch = rows[i:i + BATCH]
        graph.query(query, {"rows": batch})
        done += len(batch)
    dt = time.time() - t0
    print(f"  [{label:<18}] {done:>6} rows in {dt:.2f}s")
    return dt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true",
                        help="delete the graph, rebuild indexes, then load")
    parser.add_argument("--dir", default=DATA_DIR, help="generated data directory")
    args = parser.parse_args()

    graph = get_graph()
    total = 0.0

    # ---- reset: delete graph + rebuild indexes ----------------------------
    if args.reset:
        try:
            graph.delete()
            print("[reset] graph deleted")
        except ResponseError as exc:
            if "empty key" not in str(exc):
                raise
            print("[reset] graph already empty; nothing to delete")
        for label, prop in INDEXES:
            graph.create_node_range_index(label, prop)
        print(f"[reset] created {len(INDEXES)} indexes")
    else:
        have = existing_indexes(graph)
        created = 0
        for label, prop in INDEXES:
            if (label, prop) not in have:
                graph.create_node_range_index(label, prop)
                created += 1
        if created:
            print(f"[index ] created {created} missing indexes "
                  f"({len(INDEXES) - created}/{len(INDEXES)} present)")

    # ---- nodes ------------------------------------------------------------
    print("== loading nodes ==")
    nodes = [
        ("accounts.csv", "Account", accounts,
         "UNWIND $rows AS r MERGE (n:Account {id:r.id}) SET n.holder_name=r.holder_name, "
         "n.bank=r.bank, n.account_type=r.account_type, n.opened_at=r.opened_at, "
         "n.balance_held=r.balance_held, n.is_flagged=r.is_flagged, n.risk_score=r.risk_score"),
        ("devices.csv", "Device", devices,
         "UNWIND $rows AS r MERGE (n:Device {id:r.id}) SET n.device_fingerprint=r.device_fingerprint, "
         "n.os=r.os"),
        ("phones.csv", "Phone", phones,
         "UNWIND $rows AS r MERGE (n:Phone {id:r.id}) SET n.number=r.number"),
        ("cashout_points.csv", "CashOutPoint", cashouts,
         "UNWIND $rows AS r MERGE (n:CashOutPoint {id:r.id}) SET n.kind=r.kind, "
         "n.name=r.name, n.location=r.location"),
        ("transactions.csv", "Transaction", transactions,
         "UNWIND $rows AS r MERGE (n:Transaction {id:r.id}) SET n.amount=r.amount, "
         "n.timestamp=r.timestamp, n.channel=r.channel, n.status=r.status"),
        ("fraud_reports.csv", "FraudReport", fraud_reports,
         "UNWIND $rows AS r MERGE (n:FraudReport {id:r.id}) SET "
         "n.victim_account_id=r.victim_account_id, n.amount=r.amount, "
         "n.reported_at=r.reported_at, n.description=r.description"),
    ]
    for fname, label, conv, q in nodes:
        rows = [conv(r) for r in _read(os.path.join(args.dir, fname))]
        total += load_batches(graph, rows, q, label)

    # ---- relationships ----------------------------------------------------
    print("== loading relationships ==")
    ad = [account_device(r) for r in _read(os.path.join(args.dir, "account_device.csv"))]
    total += load_batches(graph, ad, (
        "UNWIND $rows AS r MATCH (a:Account {id:r.account_id}), (d:Device {id:r.device_id}) "
        "MERGE (a)-[rel:USES_DEVICE]->(d) SET rel.first_seen=r.first_seen, "
        "rel.last_seen=r.last_seen"), "USES_DEVICE")

    ap = [account_phone(r) for r in _read(os.path.join(args.dir, "account_phone.csv"))]
    total += load_batches(graph, ap, (
        "UNWIND $rows AS r MATCH (a:Account {id:r.account_id}), (p:Phone {id:r.phone_id}) "
        "MERGE (a)-[:REGISTERED_PHONE]->(p)"), "REGISTERED_PHONE")

    txn_rows = _read(os.path.join(args.dir, "transactions.csv"))
    sent = [{"id": r["id"], "sender_account_id": r["sender_account_id"]} for r in txn_rows]
    total += load_batches(graph, sent, (
        "UNWIND $rows AS r MATCH (a:Account {id:r.sender_account_id}), "
        "(t:Transaction {id:r.id}) MERGE (a)-[:SENT]->(t)"), "SENT")

    recv = [{"id": r["id"], "receiver_account_id": r["receiver_account_id"]}
            for r in txn_rows if r["receiver_account_id"]]
    total += load_batches(graph, recv, (
        "UNWIND $rows AS r MATCH (t:Transaction {id:r.id}), "
        "(a:Account {id:r.receiver_account_id}) MERGE (t)-[:RECEIVED_BY]->(a)"),
        "RECEIVED_BY")

    paid = [paid_edge(r) for r in _read(os.path.join(args.dir, "paid_edges.csv"))]
    total += load_batches(graph, paid, (
        "UNWIND $rows AS r MATCH (a:Account {id:r.src}), (b:Account {id:r.dst}) "
        "MERGE (a)-[rel:PAID {txn_id:r.txn_id}]->(b) "
        "SET rel.amount=r.amount, rel.timestamp=r.timestamp"), "PAID")

    co = [cashed_out(r) for r in _read(os.path.join(args.dir, "cashed_out_at.csv"))]
    total += load_batches(graph, co, (
        "UNWIND $rows AS r MATCH (a:Account {id:r.account_id}), "
        "(c:CashOutPoint {id:r.cashout_point_id}) "
        "MERGE (a)-[rel:CASHED_OUT_AT {timestamp:r.timestamp}]->(c) "
        "SET rel.amount=r.amount"), "CASHED_OUT_AT")

    fr = [{"id": r["id"], "victim_account_id": r["victim_account_id"]}
          for r in _read(os.path.join(args.dir, "fraud_reports.csv"))]
    total += load_batches(graph, fr, (
        "UNWIND $rows AS r MATCH (fr:FraudReport {id:r.id}), "
        "(a:Account {id:r.victim_account_id}) MERGE (fr)-[:REPORTS_VICTIM]->(a)"),
        "REPORTS_VICTIM")

    print(f"== done: {total:.2f}s total load time ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())