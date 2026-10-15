"""Small CLI to eyeball every core query against Ravi's case.

Usage:
    python scripts/try_queries.py            # all queries, compact output
    python scripts/try_queries.py trace dev  # just one (prefix match on function)
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph  # noqa: E402
from backend import queries as q  # noqa: E402

RAVI = "ACC_0461"
THEFT_T = 1792038600  # 2h before 'now' (2026-10-15 12:00 IST)


def _time(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return out, time.time() - t0


def _dump(label, out, dt, keys=()):
    print(f"\n## {label}  ({dt*1000:.0f} ms)")
    if keys:
        print(f"   keys: {sorted(out.keys())}")
    text = json.dumps(out, default=str)
    print("   " + text[:1400])


def run_all(graph, only=None):
    theft_t = THEFT_T
    jobs = [
        ("report", lambda: q.get_fraud_report(graph, "FR_0001")),
        ("profile_ravi", lambda: q.get_account_profile(graph, RAVI)),
        ("profile_decoy", lambda: q.get_account_profile(graph, "ACC_0476")),
        ("trace_forward", lambda: q.trace_money_forward(graph, RAVI, theft_t, max_hops=8)),
        ("cashout_ring1", lambda: q.find_cash_out_points(
            graph, ["ACC_0461", "ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466"])),
        ("balances", lambda: q.get_balance_held(graph, ["ACC_0463", "ACC_0466", "ACC_0475"])),
        ("shared_devices_B", lambda: q.find_shared_devices(graph, "ACC_0463")),
        ("shared_phones_r3", lambda: q.find_shared_phones(graph, "ACC_0472")),
        ("rapid_hops_top", lambda: q.detect_rapid_hops(graph)),
        ("rapid_hops_A", lambda: q.detect_rapid_hops(graph, "ACC_0462")),
        ("fan_in", lambda: q.detect_fan_in(graph, min_senders=3)),
        ("fan_out_A", lambda: q.detect_fan_out(graph, "ACC_0462")),
        ("neighborhood", lambda: q.get_neighborhood(graph, RAVI, hops=2)),
    ]
    for name, fn in jobs:
        if only and only not in name:
            continue
        out, dt = _time(fn)
        _dump(name, out, dt)


def main() -> int:
    import os
    graph = get_graph()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    run_all(graph, only)
    return 0


if __name__ == "__main__":
    sys.exit(main())