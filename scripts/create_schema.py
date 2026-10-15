"""Create the MuleTrace graph indexes in FalkorDB.

Idempotent: existing indexes are detected and left alone; missing ones are created.
Use --reset to delete the whole graph and rebuild all indexes from scratch.
"""
import argparse
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis.exceptions import ResponseError

from backend.db import get_graph

# (label, property) pairs that get a RANGE range index.
INDEXES = [
    ("Account", "id"),
    ("Account", "is_flagged"),
    ("Device", "id"),
    ("Phone", "number"),
    ("Transaction", "id"),
    ("Transaction", "timestamp"),
    ("CashOutPoint", "id"),
    ("FraudReport", "id"),
]


def existing_indexes(graph):
    """Return the set of (label, property) tuples currently indexed."""
    found = set()
    rows = graph.list_indices().result_set or []
    for row in rows:
        label = row[0]
        props = row[1]
        if isinstance(props, str):
            try:
                props = ast.literal_eval(props)
            except (ValueError, SyntaxError):
                props = [p.strip(" '\"") for p in props.strip("[]").split(",") if p.strip()]
        if not isinstance(props, (list, tuple)):
            props = [props]
        for prop in props:
            prop = str(prop).strip("'\"")
            if prop:
                found.add((label, prop))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Create MuleTrace FalkorDB schema indexes")
    parser.add_argument("--reset", action="store_true", help="delete the graph, then rebuild all indexes")
    args = parser.parse_args()

    graph = get_graph()

    if args.reset:
        print("[reset] deleting graph ...")
        try:
            graph.delete()
            print("[reset] graph deleted")
        except ResponseError as exc:
            # Deletion of a not-yet-created / already-empty graph key is a no-op.
            if "empty key" not in str(exc):
                raise
            print("[reset] graph already empty; nothing to delete")
        print("[reset] recreating all indexes ...")

    # After a reset the graph key is empty and list_indices() cannot run on it,
    # so only probe existing indexes on the non-reset path.
    have = set() if args.reset else existing_indexes(graph)
    created = 0
    for label, prop in INDEXES:
        if (label, prop) in have:
            print(f"[present ] {label}({prop})")
        else:
            graph.create_node_range_index(label, prop)
            created += 1
            print(f"[created ] {label}({prop})")

    total = len(INDEXES)
    print(f"schema ready: {total - created}/{total} already present, {created} created")
    return 0


if __name__ == "__main__":
    sys.exit(main())