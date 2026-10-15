"""Pytest suite for backend/queries.py against the loaded FalkorDB graph.

May read tests/ground_truth.json (the answer key) — the loader/agent never do.

Run from the repo root:
    python -m pytest tests/test_queries.py -v
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.db import get_graph  # noqa: E402
from backend import queries as q  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "tests", "ground_truth.json"), encoding="utf-8") as fh:
    GT = json.load(fh)

RAVI = GT["victim_account_id"]
THEFT = GT["reported_at"] - 6300
R1 = GT["rings"]["1"]
R2 = GT["rings"]["2"]
R3 = GT["rings"]["3"]
DECOY = GT["decoy_account_id"]
MULES1, MULES2, MULES3 = set(R1["accounts"]), set(R2["accounts"]), set(R3["accounts"])
ALL_MULES = MULES1 | MULES2 | MULES3


@pytest.fixture(scope="module")
def graph():
    return get_graph()


def _timed(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return out, time.time() - t0


# ---------------------------------------------------------------------------
# trace_money_forward
# ---------------------------------------------------------------------------
def test_trace_money_forward_finds_ring1(graph):
    res = q.trace_money_forward(graph, RAVI, THEFT, max_hops=8)
    paths = [p["path"] for p in res["paths"]["items"]]
    reachable = set(a for p in paths for a in p)
    assert MULES1 <= reachable  # A,B,C,D,E all reachable
    assert [RAVI, R1["accounts"][0], R1["accounts"][1]] in paths  # ... ->A->B
    assert R1["chain_cashout"] in paths  # Ravi ->A->C->D->E
    # every hop strictly forward in time
    for p in res["paths"]["items"]:
        assert all(g > 0 for g in p["hop_gaps"])
    # a cash-out point exists at the end of the chain
    cash = q.find_cash_out_points(graph, list(MULES1))
    assert any(c["account"] == R1["cashout_account"] for c in cash["items"]["items"])


def test_trace_does_not_follow_edges_before_start(graph):
    # Ravi's purchase at the decoy is dated ~11 days before the theft -> not followed
    res = q.trace_money_forward(graph, RAVI, THEFT, max_hops=8)
    reached = set(a for p in res["paths"]["items"] for a in p["path"])
    assert DECOY not in reached
    # a trace starting after an edge must not include that edge either
    late = q.trace_money_forward(graph, RAVI, THEFT + 100_000, max_hops=4)
    assert all(p["hops"][0]["timestamp"] >= THEFT + 100_000 for p in late["paths"]["items"])


# ---------------------------------------------------------------------------
# freeze ordering vs ground truth
# ---------------------------------------------------------------------------
def test_freeze_candidates_match_ground_truth(graph):
    res = q.trace_money_forward(graph, RAVI, THEFT, max_hops=8)
    paths = [p["path"] for p in res["paths"]["items"]]
    # accounts reachable via >=2 hops from Ravi
    reached2 = {p[-1] for p in paths if len(p) >= 3}
    bal = q.get_balance_held(graph, list(MULES1))
    cands = sorted(reached2 & MULES1, key=lambda a: (-bal.get(a, 0), a))
    expected = [it["account"] for it in GT["expected_freeze_list"]]
    assert cands == expected
    for it in GT["expected_freeze_list"]:
        assert bal[it["account"]] == it["balance_held"]


# ---------------------------------------------------------------------------
# shared device
# ---------------------------------------------------------------------------
def test_shared_device_links_ring1_to_ring2(graph):
    link = GT["shared_device_link"]
    res = q.find_shared_devices(graph, link["ring1_account"])  # Mule B
    devs = {d["device_id"]: d for d in res["items"]["items"]}
    assert link["device_id"] in devs
    assert link["ring2_account"] in devs[link["device_id"]]["sharing_accounts"]
    assert devs[link["device_id"]]["share_count"] == 2  # small family-style share


# ---------------------------------------------------------------------------
# fan-in / rapid hops
# ---------------------------------------------------------------------------
def test_fan_in_surfaces_ring3(graph):
    res = q.detect_fan_in(graph, min_senders=3)
    top = {it["account"] for it in res["items"]["items"]}
    assert bool(top & (MULES3))  # a collector or the hub appears near the top
    assert res["items"]["truncated"] in (True, False)  # always annotated


def test_rapid_hops_finds_ring1_and_ring2_mules(graph):
    res = q.detect_rapid_hops(graph)
    found = {it["account"] for it in res["items"]["items"]}
    assert found & MULES1
    assert found & MULES2


def test_legit_rapid_cases_are_not_mules(graph):
    res = q.detect_rapid_hops(graph)
    found = {it["account"] for it in res["items"]["items"]}
    legit = found - ALL_MULES
    assert legit, "no non-mule account flagged by rapid-hop rule -> data too clean"


# ---------------------------------------------------------------------------
# decoy distinguishability
# ---------------------------------------------------------------------------
def test_decoy_profile_distinguishes_from_mule(graph):
    decoy = q.get_account_profile(graph, DECOY)
    mule = q.get_account_profile(graph, R1["accounts"][0])  # Mule A
    assert decoy["distinct_senders"] >= 60
    assert len(decoy["devices"]["items"]) == 1
    assert len(decoy["phones"]["items"]) == 1
    decoy_min = decoy["forward_latency"]["min"]
    mule_min = mule["forward_latency"]["min"]
    assert decoy_min is not None and mule_min is not None
    assert decoy_min >= mule_min * 10  # decoy forwards on a slow weekly schedule


def test_decoy_traps_naive_rule_but_not_behavioural(graph):
    profile = q.get_account_profile(graph, DECOY)
    # naive "high inflow" rule fires...
    assert profile["inflow_total"] > 50_000
    # ...but rapid/onward behaviour does not
    rap = q.detect_rapid_hops(graph, DECOY)
    assert len(rap["items"]["items"]) == 0


# ---------------------------------------------------------------------------
# caps + timing
# ---------------------------------------------------------------------------
def test_everything_under_1s(graph):
    probes = [
        ("get_fraud_report", lambda: q.get_fraud_report(graph, "FR_0001")),
        ("get_account_profile(decoy)", lambda: q.get_account_profile(graph, DECOY)),
        ("trace_money_forward", lambda: q.trace_money_forward(graph, RAVI, THEFT)),
        ("find_cash_out_points", lambda: q.find_cash_out_points(graph, list(MULES1))),
        ("get_balance_held", lambda: q.get_balance_held(graph, list(MULES1))),
        ("find_shared_devices", lambda: q.find_shared_devices(graph, R1["accounts"][1])),
        ("find_shared_phones", lambda: q.find_shared_phones(graph, R3["collectors"][0])),
        ("detect_rapid_hops(all)", lambda: q.detect_rapid_hops(graph)),
        ("detect_fan_in", lambda: q.detect_fan_in(graph, min_senders=3)),
        ("detect_fan_out", lambda: q.detect_fan_out(graph, R1["accounts"][0])),
        ("get_neighborhood", lambda: q.get_neighborhood(graph, RAVI)),
    ]
    for name, fn in probes:
        _out, dt = _timed(fn)
        assert dt < 1.0, f"{name} took {dt:.2f}s"
        print(f"   {name:<24} {dt*1000:.0f} ms")


def test_list_caps_hold(graph):
    assert len(q.detect_fan_in(graph, min_senders=3)["items"]["items"]) <= 20
    assert len(q.detect_rapid_hops(graph)["items"]["items"]) <= 20
    assert len(q.trace_money_forward(graph, RAVI, THEFT)["paths"]["items"]) <= 50
    n = q.get_neighborhood(graph, RAVI)["nodes"]
    assert len(n["items"]) <= 60
    assert "truncated" in n and "total" in n  # capped with {truncated,total}


def test_fraud_report_and_balances(graph):
    rep = q.get_fraud_report(graph, "FR_0001")
    assert rep["found"] and rep["victim"]["id"] == RAVI and rep["report"]["amount"] == 85_000
    bal = q.get_balance_held(graph, [R1["accounts"][1], R1["accounts"][4]])
    assert bal[R1["accounts"][1]] == 40_000   # B
    assert bal[R1["accounts"][4]] == 15_000   # E


def test_fan_out_detects_split(graph):
    res = q.detect_fan_out(graph, R1["accounts"][0])  # Mule A splits 85k
    assert any(len(e["splits"]) >= 2 for e in res["items"]["items"])