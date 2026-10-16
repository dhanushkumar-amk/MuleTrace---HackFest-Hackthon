"""Reset memory nodes and relationships without reloading the graph (Phase 11).

Removes only:
- Case nodes
- FLAGGED_IN, INVOLVES, LINKED_TO edges
Resets:
- Account.is_flagged = false
- Account.risk_score = 0.0

Leaves all base accounts, devices, phones, cashout points, transactions, and fraud reports intact.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph
from backend.memory import reset_memory


def main() -> int:
    graph = get_graph()
    print(f"== Resetting MuleTrace memory on graph '{graph.name}' ==")
    res = reset_memory(graph)
    print(f"Result: {res['message']}")
    print("Memory reset complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
