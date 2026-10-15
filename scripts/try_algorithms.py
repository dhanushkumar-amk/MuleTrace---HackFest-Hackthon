"""Small CLI to eyeball every graph algorithm function against Ravi's case.

Usage:
    python scripts/try_algorithms.py           # all algorithms, compact output
    python scripts/try_algorithms.py path      # just one (prefix match on job name)
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph  # noqa: E402
from backend import algorithms as algo  # noqa: E402

RAVI = "ACC_0461"
CASHOUT_R1 = "ACC_0466"
MULE_B = "ACC_0463"
MULE_R2B = "ACC_0468"
R1_CHAIN = ["ACC_0461", "ACC_0462", "ACC_0464", "ACC_0465", "ACC_0466"]
THEFT_T = 1792038600


def _time(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return out, time.time() - t0


def _dump(label: str, out: dict, dt: float, keys=()) -> None:
    print(f"\n## {label}  ({dt*1000:.0f} ms)")
    if keys:
        print(f"   keys: {sorted(out.keys())}")
    text = json.dumps(out, default=str)
    print("   " + text[:1400])


def run_all(graph, only=None):
    jobs = [
        ("shortest_path_money", lambda: algo.find_shortest_path(
            graph, RAVI, CASHOUT_R1, mode="money")),
        ("shortest_path_any", lambda: algo.find_shortest_path(
            graph, MULE_B, MULE_R2B, mode="any")),
        ("rank_hubs_window", lambda: algo.rank_hub_accounts(
            graph, window_start=1789576200 - 3600, window_end=1789587900 + 3600, top_k=5)),
        ("rank_hubs_full", lambda: algo.rank_hub_accounts(
            graph, top_k=10, weight="amount")),
        ("connected_components_no_dev", lambda: algo.find_connected_components(
            graph, window_start=THEFT_T - 96*3600, window_end=THEFT_T + 3600, min_amount=5000,
            include_shared_devices=False, limit=5)),
        ("connected_components_with_dev", lambda: algo.find_connected_components(
            graph, window_start=THEFT_T - 96*3600, window_end=THEFT_T + 3600, min_amount=5000,
            include_shared_devices=True, limit=5)),
        ("find_communities", lambda: algo.find_communities(
            graph, resolution=1.0, limit=5)),
        ("find_connected_ring_mule_b", lambda: algo.find_connected_ring(
            graph, MULE_B)),
        ("rank_chokepoints_ring1", lambda: algo.rank_chokepoints(
            graph, R1_CHAIN, top_k=5)),
    ]

    for name, fn in jobs:
        if only and only not in name:
            continue
        out, dt = _time(fn)
        _dump(name, out, dt)


def main() -> int:
    graph = get_graph()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    run_all(graph, only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
