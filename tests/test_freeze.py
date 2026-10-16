"""Unit tests for freeze-list ranking and memory write-back (Phase 11).

Plain Python unit tests without LLM, verifying:
1. Ravi's case freeze list ordering and amounts match ground truth.
2. Mule B (largest item) holds ~Rs 40,000 with path hops >= 2 from Ravi.
3. Decoy account is never in the freeze list and appears in not_recommended with behavioral reason.
4. Account with high inflow only is rejected.
5. Legitimate rapid-forward account from Phase 4 noise is not listed.
6. Account with only a shared device (no money trail) is rejected.
7. Every item has path hops >= 2, valid graph txn IDs, and strictly increasing timestamps.
8. total_recoverable equals sum of items.
9. recommendation_only is True.
10. Empty and unknown-ID candidates return clean errors, never crash.
11. Memory: save twice is idempotent (identical counts).
12. Memory: saving an account not in the freeze list is rejected.
13. Memory: no forbidden property names (ring, mule, decoy, plant).
14. Memory: reset_memory restores original clean state.
15. recall_past_cases: finds earlier case via shared device link.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.db import get_graph
from backend.freeze import build_freeze_list
from backend.memory import save_case_to_memory, recall_past_cases, reset_memory
from backend import queries

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "tests" / "ground_truth.json", encoding="utf-8") as fh:
    GT = json.load(fh)

RAVI = GT["victim_account_id"]
REPORT_ID = GT["report_id"]
DECOY = GT["decoy_account_id"]
EXPECTED_FREEZE = GT["expected_freeze_list"]
SHARED_DEV_RING1 = GT["shared_device_link"]["ring1_account"]
SHARED_DEV_RING2 = GT["shared_device_link"]["ring2_account"]


@pytest.fixture(scope="module")
def graph():
    g = get_graph()
    reset_memory(g)
    yield g
    reset_memory(g)


def test_ravi_freeze_list_matches_ground_truth_and_amounts(graph):
    # Candidate accounts from Ring 1 plus decoy and noise
    candidates = [
        "ACC_0462",
        "ACC_0463",
        "ACC_0464",
        "ACC_0465",
        "ACC_0466",
        DECOY,
    ]

    res = build_freeze_list(candidates=candidates, case_context=REPORT_ID, graph=graph)

    assert res["recommendation_only"] is True
    assert "items" in res
    items = res["items"]

    # Must contain the 4 Ring 1 mules that still hold money
    assert len(items) == len(EXPECTED_FREEZE)

    for idx, (item, exp) in enumerate(zip(items, EXPECTED_FREEZE), start=1):
        assert item["priority"] == idx
        assert item["account"] == exp["account"]
        assert item["amount_recoverable"] == exp["balance_held"]
        assert item["hops"] >= 2
        assert item["confidence"] in ("high", "medium")

    # Order matches ground truth: 40000, 15000, 1000, 1000
    assert items[0]["account"] == "ACC_0463"
    assert items[0]["amount_recoverable"] == 40000
    assert items[1]["account"] == "ACC_0466"
    assert items[1]["amount_recoverable"] == 15000
    assert items[2]["account"] == "ACC_0464"
    assert items[2]["amount_recoverable"] == 1000
    assert items[3]["account"] == "ACC_0465"
    assert items[3]["amount_recoverable"] == 1000


def test_largest_item_is_mule_b_holding_about_40k(graph):
    candidates = ["ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466"]
    res = build_freeze_list(candidates=candidates, case_context=REPORT_ID, graph=graph)
    items = res["items"]
    assert len(items) >= 1
    top = items[0]
    assert top["account"] == "ACC_0463"
    assert 38000 <= top["amount_recoverable"] <= 42000
    assert top["hops"] >= 2
    assert "Ravi" in top["path_text"] or RAVI in top["path_text"]


def test_decoy_never_in_freeze_list_and_in_not_recommended(graph):
    candidates = ["ACC_0463", "ACC_0466", DECOY]
    res = build_freeze_list(candidates=candidates, case_context=REPORT_ID, graph=graph)

    freeze_accounts = [it["account"] for it in res["items"]]
    assert DECOY not in freeze_accounts

    not_rec = {nr["account"]: nr["why"] for nr in res["not_recommended"]}
    assert DECOY in not_rec
    why = not_rec[DECOY].lower()
    assert "legitimate-merchant guard" in why or "distinct senders" in why or "no time-ordered money trail" in why


def test_high_inflow_only_account_rejected(graph):
    # Find an account in the graph with high inflow but no path from victim
    rows = queries._rows(
        graph,
        "MATCH (s)-[p:PAID]->(a:Account) WHERE a.id <> $ravi "
        "RETURN a.id, sum(p.amount) AS total ORDER BY total DESC LIMIT 5",
        ravi=RAVI,
    )
    assert rows
    high_inflow_acc = rows[0][0]
    if high_inflow_acc in ("ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466"):
        high_inflow_acc = rows[4][0]

    res = build_freeze_list(candidates=[high_inflow_acc], case_context=REPORT_ID, graph=graph)
    assert len(res["items"]) == 0
    not_rec = [nr["account"] for nr in res["not_recommended"]]
    assert high_inflow_acc in not_rec


def test_legitimate_rapid_forward_noise_account_not_listed(graph):
    # Phase 4 noise may have rapid hops, but not from Ravi's theft trail
    rh = queries.detect_rapid_hops(graph, window_seconds=600, limit=20)
    noise_candidates = [
        item["account"]
        for item in rh["items"]["items"]
        if item["account"] not in ("ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466")
    ]
    if noise_candidates:
        noise_acc = noise_candidates[0]
        res = build_freeze_list(candidates=[noise_acc], case_context=REPORT_ID, graph=graph)
        assert len(res["items"]) == 0
        not_rec = [nr["account"] for nr in res["not_recommended"]]
        assert noise_acc in not_rec


def test_shared_device_only_account_without_money_trail_rejected(graph):
    # ACC_0468 shares device DEV_0593 with Mule B (ACC_0463), but has no money trail from Ravi
    res = build_freeze_list(candidates=[SHARED_DEV_RING2], case_context=REPORT_ID, graph=graph)
    assert len(res["items"]) == 0
    not_rec = {nr["account"]: nr["why"] for nr in res["not_recommended"]}
    assert SHARED_DEV_RING2 in not_rec
    assert "no time-ordered money trail" in not_rec[SHARED_DEV_RING2].lower()


def test_path_hops_valid_txns_and_increasing_timestamps(graph):
    candidates = ["ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466"]
    res = build_freeze_list(candidates=candidates, case_context=REPORT_ID, graph=graph)

    assert len(res["items"]) == 4
    for it in res["items"]:
        assert it["hops"] >= 2
        facts = it["edge_facts"]
        assert len(facts) >= 2

        # Check that txn IDs exist in the graph and timestamps are strictly increasing
        prev_ts = -1
        for hop in facts:
            txn_id = hop["txn_id"]
            ts = hop["timestamp"]
            assert ts > prev_ts, f"Timestamps must strictly increase: {ts} <= {prev_ts}"
            prev_ts = ts

            # Verify txn exists in graph
            tx_row = queries._rows(graph, "MATCH (t:Transaction) WHERE t.id = $id RETURN t.id", id=txn_id)
            assert len(tx_row) == 1, f"Txn ID '{txn_id}' must exist in graph"


def test_total_recoverable_equals_sum_of_items(graph):
    candidates = ["ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466"]
    res = build_freeze_list(candidates=candidates, case_context=REPORT_ID, graph=graph)

    expected_sum = sum(it["amount_recoverable"] for it in res["items"])
    assert res["total_recoverable"] == expected_sum
    assert res["total_recoverable"] == 57000
    assert res["recommendation_only"] is True


def test_empty_and_unknown_candidates_never_crash(graph):
    # Empty candidates
    res_empty = build_freeze_list(candidates=[], case_context=REPORT_ID, graph=graph)
    assert res_empty["recommendation_only"] is True
    assert res_empty["total_recoverable"] == 0
    assert res_empty["items"] == []
    assert "reason" in res_empty

    # Unknown candidate account ID
    res_unknown = build_freeze_list(candidates=["ACC_DOES_NOT_EXIST"], case_context=REPORT_ID, graph=graph)
    assert "error" in res_unknown
    assert "hint" in res_unknown
    assert "ACC_DOES_NOT_EXIST" in res_unknown["error"]


def test_memory_save_idempotent_and_no_forbidden_properties(graph):
    reset_memory(graph)

    # 1. First build freeze list
    candidates = ["ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466"]
    res_freeze = build_freeze_list(candidates=candidates, case_context=REPORT_ID, graph=graph)
    assert len(res_freeze["items"]) == 4

    # 2. Save case once
    res1 = save_case_to_memory(
        graph=graph,
        report_id=REPORT_ID,
        summary="Investigated Ravi KYC scam; traced Ring 1 mules.",
    )
    assert res1["saved"] is True
    assert res1["accounts_flagged"] == 4

    # Check node counts
    case_count1 = queries._rows(graph, "MATCH (c:Case) RETURN count(c)")[0][0]
    flagged_count1 = queries._rows(graph, "MATCH ()-[r:FLAGGED_IN]->() RETURN count(r)")[0][0]
    assert case_count1 == 1
    assert flagged_count1 == 4

    # 3. Save case twice (idempotent)
    res2 = save_case_to_memory(
        graph=graph,
        report_id=REPORT_ID,
        summary="Updated summary for Ravi KYC scam investigation.",
    )
    assert res2["saved"] is True
    case_count2 = queries._rows(graph, "MATCH (c:Case) RETURN count(c)")[0][0]
    flagged_count2 = queries._rows(graph, "MATCH ()-[r:FLAGGED_IN]->() RETURN count(r)")[0][0]
    assert case_count2 == case_count1
    assert flagged_count2 == flagged_count1

    # 4. Verify no forbidden property names anywhere in newly written nodes or edges
    forbidden_keys = ("ring", "mule", "decoy", "plant")
    case_keys = queries._rows(graph, "MATCH (c:Case) UNWIND keys(c) AS k RETURN DISTINCT k")
    for r in case_keys:
        k = r[0].lower()
        for f in forbidden_keys:
            assert f not in k, f"Forbidden key '{k}' found on Case node"

    rel_keys = queries._rows(graph, "MATCH ()-[r:FLAGGED_IN]->() UNWIND keys(r) AS k RETURN DISTINCT k")
    for r in rel_keys:
        k = r[0].lower()
        for f in forbidden_keys:
            assert f not in k, f"Forbidden key '{k}' found on FLAGGED_IN edge"

    # 5. Saving an account that was NOT in the freeze list is rejected
    res_bad = save_case_to_memory(
        graph=graph,
        report_id=REPORT_ID,
        summary="Trying to save non-approved account",
        account_ids=["ACC_0463", "ACC_0001"],  # ACC_0001 was not in freeze list
    )
    assert "error" in res_bad
    assert "ACC_0001" in res_bad["error"]

    # 6. Reset memory restores clean state
    reset_memory(graph)
    assert queries._rows(graph, "MATCH (c:Case) RETURN count(c)")[0][0] == 0
    assert queries._rows(graph, "MATCH ()-[r:FLAGGED_IN]->() RETURN count(r)")[0][0] == 0
    assert queries._rows(graph, "MATCH (a:Account) WHERE a.is_flagged = true RETURN count(a)")[0][0] == 0


def test_recall_past_cases_finds_earlier_case_via_shared_device(graph):
    reset_memory(graph)

    # 1. Save Ravi's case (which flags Ring 1 Mule B: ACC_0463)
    build_freeze_list(candidates=["ACC_0463", "ACC_0466"], case_context=REPORT_ID, graph=graph)
    save_case_to_memory(
        graph=graph,
        report_id=REPORT_ID,
        summary="Ravi fraud report: Ring 1 mules flagged.",
    )

    # 2. Second investigation inspects Ring 2 Mule (ACC_0468), which shares DEV_0593 with ACC_0463
    recall_res = recall_past_cases(graph=graph, account_ids=[SHARED_DEV_RING2])
    items = recall_res["items"]["items"]
    assert len(items) >= 1

    found = False
    for item in items:
        if item.get("report_id") == REPORT_ID and item.get("link_type") == "shared_device":
            found = True
            assert item.get("linked_account") == SHARED_DEV_RING1
            assert "DEV_0593" in str(item.get("shared_device", ""))
            assert item.get("confidence") == "high"
            break

    assert found, "recall_past_cases must discover earlier case via shared device DEV_0593"

    # Reset
    reset_memory(graph)
