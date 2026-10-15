"""Print a short summary of the loaded MuleTrace graph.

Counts per label and relationship type, the 5 accounts with the most incoming
payments, the 5 devices shared by the most accounts, and the total PAID edges.

Usage:
    python scripts/graph_stats.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph  # noqa: E402

LABELS = ["Account", "Device", "Phone", "CashOutPoint", "Transaction", "FraudReport"]
RELS = ["USES_DEVICE", "REGISTERED_PHONE", "SENT", "RECEIVED_BY",
        "PAID", "CASHED_OUT_AT", "REPORTS_VICTIM"]


def main() -> int:
    graph = get_graph()
    print(f"== graph stats: {graph.name} ==")

    print("nodes:")
    for label in LABELS:
        rs = graph.query(f"MATCH (n:{label}) RETURN count(n)").result_set or []
        print(f"   {label:<14} {rs[0][0]}")

    print("relationships:")
    for rel in RELS:
        rs = graph.query(f"MATCH ()-[r:{rel}]->() RETURN count(r)").result_set or []
        print(f"   {rel:<16} {rs[0][0]}")

    print("5 accounts with most incoming PAID payments:")
    rows = graph.query(
        "MATCH (a:Account)<-[p:PAID]-() RETURN a.id, a.holder_name, count(p) AS c "
        "ORDER BY c DESC LIMIT 5").result_set or []
    for rid, name, c in rows:
        print(f"   {rid} {name} - {c}")

    print("5 devices used by the most accounts:")
    rows = graph.query(
        "MATCH (d:Device)<-[u:USES_DEVICE]-() RETURN d.id, count(u) AS c "
        "ORDER BY c DESC LIMIT 5").result_set or []
    for dev, c in rows:
        print(f"   {dev} - {c}")

    rs = graph.query("MATCH ()-[p:PAID]->() RETURN count(p)").result_set or []
    print(f"total PAID edges: {rs[0][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())