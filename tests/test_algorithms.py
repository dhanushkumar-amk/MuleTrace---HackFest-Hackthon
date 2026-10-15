"""Pytest suite for backend/algorithms.py against the loaded FalkorDB graph.

May read tests/ground_truth.json (the answer key) — algorithms.py never does.

Run from the repo root:
    python -m pytest tests/test_algorithms.py -v -s
"""
from __future__ import annotations

import json
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_graph
from backend import algorithms as algo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "tests", "ground_truth.json"), encoding="utf-8") as fh:
    GT = json.load(fh)

RAVI = GT["victim_account_id"]
THEFT = GT["reported_at"] - 6300
R1 = GT["rings"]["1"]
R2 = GT["rings"]["2"]
R3 = GT["rings"]["3"]
DECOY = GT["decoy_account_id"]
MULES1 = set(R1["accounts"])
MULES2 = set(R2["accounts"])
MULES3 = set(R3["accounts"])
SHARED_DEV = GT["shared_device_link"]


@pytest.fixture(scope="module")
def graph():
    algo.clear_projection_cache()
    return get_graph()


def _timed(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return out, time.time() - t0


# ---------------------------------------------------------------------------
# 1. find_shortest_path
# ---------------------------------------------------------------------------
def test_shortest_path_money_mode_follows_planted_chain(graph):
    # Ravi -> Mule A -> Mule C -> Mule D -> Mule E (cashout)
    res = algo.find_shortest_path(graph, RAVI, R1["cashout_account"], mode="money")
    assert res["found"] is True
    assert res["path"] == R1["chain_cashout"]
    assert res["hops"] == 4
    assert all(t == "PAID" for t in res["link_types"])


def test_shortest_path_any_mode_links_mule_b_to_ring2(graph):
    # Mule B has no direct 1-hop PAID edge to Ring 2, but shares DEV_0593 with Mule R2B
    b_acc = SHARED_DEV["ring1_account"]
    r2_acc = SHARED_DEV["ring2_account"]

    # In money mode, it takes 6 hops through unrelated historical payments
    money_res = algo.find_shortest_path(graph, b_acc, r2_acc, mode="money")
    assert money_res["found"] is True
    assert money_res["hops"] > 1
    assert all(t == "PAID" for t in money_res["link_types"])

    # In any mode, it directly connects through the shared device (1 hop)
    any_res = algo.find_shortest_path(graph, b_acc, r2_acc, mode="any")
    assert any_res["found"] is True
    assert any_res["path"] == [b_acc, r2_acc]
    assert any_res["hops"] == 1
    assert "SHARED_DEVICE" in any_res["link_types"]
    assert any(h.get("device_id") == SHARED_DEV["device_id"] for h in any_res["links"])


def test_shared_device_threshold_ignores_noisy_devices(graph):
    b_acc = SHARED_DEV["ring1_account"]
    r2_acc = SHARED_DEV["ring2_account"]

    # When max_device_sharing is 1, the device shared by 2 accounts is ignored
    res = algo.find_shortest_path(graph, b_acc, r2_acc, mode="any", max_device_sharing=1)
    assert res["found"] is True
    # The 1-hop shared device shortcut is ignored, so it does not contain SHARED_DEVICE
    assert "SHARED_DEVICE" not in res["link_types"]
    assert res["hops"] > 1


# ---------------------------------------------------------------------------
# 2. rank_hub_accounts
# ---------------------------------------------------------------------------
def test_rank_hub_accounts_surfaces_ring3_hub(graph):
    # Ring 3 is active in its planted window (around 1789576200..1789587900)
    w_start = 1789576200 - 3600
    w_end = 1789587900 + 3600

    res = algo.rank_hub_accounts(graph, window_start=w_start, window_end=w_end, top_k=5)
    top_accs = [it["account"] for it in res["items"]["items"]]
    assert GT["ring3_hub"] in top_accs[:3]
    assert "high rank is evidence of being a hub, not proof of fraud" in res["note"]


def test_decoy_ranks_high_in_pagerank_full_month(graph):
    # Over full month, the decoy receives from 62 distinct senders and ranks high in PageRank
    res = algo.rank_hub_accounts(graph, top_k=20, weight="amount")
    ranked_accs = [it["account"] for it in res["items"]["items"]]
    decoy_item = next((it for it in res["items"]["items"] if it["account"] == DECOY), None)

    print(f"\n   [PageRank Full Graph] Decoy ({DECOY}) rank: "
          f"{ranked_accs.index(DECOY) + 1 if DECOY in ranked_accs else '>20'}, "
          f"score: {decoy_item['score'] if decoy_item else 'N/A'}")

    assert DECOY in ranked_accs, "Decoy shop should rank in top 20 PageRank over full graph"


# ---------------------------------------------------------------------------
# 3. find_connected_components
# ---------------------------------------------------------------------------
def test_connected_components_device_linkage(graph):
    # Within a 4-day window around the theft and Ring 2, filtering transactions >= 5000:
    w_start = THEFT - 96 * 3600
    w_end = THEFT + 3600

    # 1. Without shared devices -> R1 and R2 are in different components
    no_dev = algo.find_connected_components(
        graph,
        window_start=w_start,
        window_end=w_end,
        min_amount=5000,
        include_shared_devices=False,
    )
    comps_no = [set(it["members"]) for it in no_dev["items"]["items"]]
    r1_no = next((c for c in comps_no if MULES1 & c), None)
    r2_no = next((c for c in comps_no if MULES2 & c), None)
    assert r1_no is not None
    assert r2_no is not None
    assert r1_no != r2_no, "Without shared devices, Ring 1 and Ring 2 must be in different components"

    # 2. With shared devices -> R1 and R2 are merged into the same component
    with_dev = algo.find_connected_components(
        graph,
        window_start=w_start,
        window_end=w_end,
        min_amount=5000,
        include_shared_devices=True,
    )
    comps_yes = [set(it["members"]) for it in with_dev["items"]["items"]]
    r1_yes = next((c for c in comps_yes if MULES1 & c), None)
    r2_yes = next((c for c in comps_yes if MULES2 & c), None)
    assert r1_yes is not None
    assert r2_yes is not None
    assert r1_yes == r2_yes, "With shared devices, Ring 1 and Ring 2 must be merged into the same component"

    # Flag for reported victim
    victim_comp = next((it for it in with_dev["items"]["items"] if it["has_victim"]), None)
    assert victim_comp is not None
    assert RAVI in victim_comp["members"]


# ---------------------------------------------------------------------------
# 4. find_communities (Louvain)
# ---------------------------------------------------------------------------
def test_communities_reproducible_and_ring1_grouped(graph):
    c1 = algo.find_communities(graph, resolution=1.0)
    c2 = algo.find_communities(graph, resolution=1.0)

    # Deterministic with fixed seed
    assert [it["members"] for it in c1["items"]["items"]] == [it["members"] for it in c2["items"]["items"]]

    # Ring 1 members mostly in one community
    r1_comms = [set(it["members"]) for it in c1["items"]["items"] if MULES1 & set(it["members"])]
    assert len(r1_comms) >= 1
    main_r1 = max(r1_comms, key=lambda s: len(MULES1 & s))
    assert len(MULES1 & main_r1) >= 4  # at least 4 of 5 (or 5 of 5)


def test_decoy_not_in_ring1_community(graph):
    res = algo.find_communities(graph, resolution=1.0)
    comms = [set(it["members"]) for it in res["items"]["items"]]
    main_r1 = max((c for c in comms if MULES1 & c), key=lambda s: len(MULES1 & s))

    assert DECOY not in main_r1, (
        f"Decoy {DECOY} was incorrectly grouped into Ring 1 community: {main_r1}"
    )


# ---------------------------------------------------------------------------
# 5. find_connected_ring
# ---------------------------------------------------------------------------
def test_find_connected_ring_surfaces_shared_device_link(graph):
    res = algo.find_connected_ring(graph, SHARED_DEV["ring1_account"])
    assert res["found"] is True
    assert SHARED_DEV["ring1_account"] in res["component"]
    assert SHARED_DEV["ring2_account"] in res["component"]

    # Shared device is surfaced in shared_links
    assert any(
        l.get("device_id") == SHARED_DEV["device_id"]
        for l in res["shared_links"]
    )


# ---------------------------------------------------------------------------
# 6. rank_chokepoints
# ---------------------------------------------------------------------------
def test_rank_chokepoints_identifies_chain_chokepoint(graph):
    # In Ring 1 chain (Ravi -> A -> C -> D -> E), money passes through Mule D (ACC_0465) / Mule C (ACC_0464)
    r1_chain = R1["chain_cashout"]
    res = algo.rank_chokepoints(graph, r1_chain, top_k=3)
    top_chokepoints = [it["account"] for it in res["items"]["items"]]

    # Mule D (ACC_0465) or Mule C (ACC_0464) must be in the top chokepoints
    assert "ACC_0465" in top_chokepoints or "ACC_0464" in top_chokepoints
    assert res["items"]["items"][0]["betweenness_score"] > 0


# ---------------------------------------------------------------------------
# 7. Performance & Caps
# ---------------------------------------------------------------------------
def test_everything_under_2s_and_caps_hold(graph):
    w_start = THEFT - 96 * 3600
    w_end = THEFT + 3600

    probes = [
        ("find_shortest_path(money)", lambda: algo.find_shortest_path(graph, RAVI, R1["cashout_account"], mode="money")),
        ("find_shortest_path(any)", lambda: algo.find_shortest_path(graph, SHARED_DEV["ring1_account"], SHARED_DEV["ring2_account"], mode="any")),
        ("rank_hub_accounts", lambda: algo.rank_hub_accounts(graph, window_start=w_start, window_end=w_end, top_k=10)),
        ("find_connected_components", lambda: algo.find_connected_components(graph, window_start=w_start, window_end=w_end, limit=20)),
        ("find_communities", lambda: algo.find_communities(graph, limit=20)),
        ("find_connected_ring", lambda: algo.find_connected_ring(graph, SHARED_DEV["ring1_account"])),
        ("rank_chokepoints", lambda: algo.rank_chokepoints(graph, R1["chain_cashout"], top_k=5)),
    ]

    for name, fn in probes:
        _out, dt = _timed(fn)
        assert dt < 2.0, f"{name} took {dt:.2f}s (exceeded 2.0s limit)"
        print(f"   {name:<30} {dt*1000:.0f} ms")

    # Caps hold
    assert len(algo.rank_hub_accounts(graph, top_k=5)["items"]["items"]) <= 5
    assert len(algo.find_connected_components(graph, limit=10)["items"]["items"]) <= 10
    assert len(algo.find_communities(graph, limit=5)["items"]["items"]) <= 5
    assert len(algo.rank_chokepoints(graph, R1["chain_cashout"], top_k=3)["items"]["items"]) <= 3
