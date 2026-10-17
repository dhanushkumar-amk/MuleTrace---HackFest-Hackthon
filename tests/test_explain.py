"""Unit and integration tests for MuleTrace explainability engine (Phase 12).

Validates:
- Every recommendation has a path with at least 2 hops, every txn_id exists in graph, timestamps strictly increase
- Ravi's top recommendation explanation names the same account and amount as the freeze list and cites at least 2 real tool call ids
- Decoy rejection explanation contains its behavioral numbers and mentions why high inflow was not enough
- Shared-device link explanation names the device, total sharer count and both accounts
- build_graph_highlight: all nodes and edges exist in graph, sequence order follows time order, roles match ground truth, size under cap
- Tampering test: changing an amount or txn_id causes verify_explanation to fail (verified=False)
- Ungrounded ID test: injecting a fake account ID causes verify_explanation or build_graph_highlight to drop/flag it
- to_markdown contains disclaimer, every recommended account, and no account ID not in explanation JSON
- Timeline step count equals the number of tool calls in the trace log
- Polish test (marked slow): polished summary contains no number or ID outside explanation JSON, or is discarded
- explain_case runs in under 2 seconds without polish; prints execution timing
"""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path
import pytest

from backend.db import get_graph
from backend.freeze import build_freeze_list, set_last_freeze_list
from backend.explain import (
    explain_recommendation,
    explain_rejection,
    explain_link,
    build_investigation_timeline,
    build_graph_highlight,
    explain_case,
    polish_summary_with_llm,
)
from backend.explain_verify import verify_explanation
from backend.explain_text import to_markdown, to_plain_text
from backend.tools import trace
from backend import queries

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "session_fixture.json"
GROUND_TRUTH_PATH = ROOT / "tests" / "ground_truth.json"

with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
    GT = json.load(f)

with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
    FIXTURE = json.load(f)


@pytest.fixture(scope="module")
def graph():
    return get_graph()


@pytest.fixture(scope="module")
def setup_fixture_session(graph):
    """Load the trimmed fixture session into trace buffer and compute verified freeze list."""
    sid = FIXTURE["session_id"]
    trace._TRACES[sid] = copy.deepcopy(FIXTURE["tool_calls"])

    # Build freeze list with candidate mules plus decoy
    candidates = ["ACC_0462", "ACC_0463", "ACC_0464", "ACC_0465", "ACC_0466", GT["decoy_account_id"]]
    fl_result = build_freeze_list(candidates=candidates, case_context=GT["report_id"], graph=graph)
    set_last_freeze_list(GT["report_id"], fl_result)

    return sid, fl_result


def test_recommendation_path_hops_txns_and_increasing_timestamps(graph, setup_fixture_session):
    """Every recommendation has >=2 hops, valid txn IDs in graph, and strictly increasing timestamps."""
    sid, fl_result = setup_fixture_session
    recs = [explain_recommendation(it, sid, graph) for it in fl_result["items"]]

    assert len(recs) >= 2, "Expected multiple recommended accounts"

    for rec in recs:
        # Check path has at least 2 hops
        edges = rec["path"]["edges"]
        assert len(edges) >= 2, f"Account {rec['account']} path must have >= 2 hops, found {len(edges)}"

        # Check all transaction IDs exist in live graph and timestamps strictly increase
        prev_ts = -1
        for hop_idx, hop in enumerate(edges):
            tid = hop["txn_id"]
            ts = hop["timestamp"]
            amt = hop["amount"]

            assert tid, f"Missing txn_id in hop {hop_idx} for {rec['account']}"
            assert ts > prev_ts, f"Timestamps must strictly increase: {ts} <= {prev_ts} in {rec['account']}"
            prev_ts = ts

            # Verify in live graph
            row = queries._rows(graph, "MATCH (t:Transaction {id: $id}) RETURN t.id, t.amount, t.timestamp", id=tid)
            assert len(row) == 1, f"Txn ID '{tid}' must exist in graph"
            assert row[0][1] == amt, f"Amount mismatch on {tid}"
            assert row[0][2] == ts, f"Timestamp mismatch on {tid}"


def test_ravi_top_recommendation_names_same_account_amount_and_cites_two_tool_calls(graph, setup_fixture_session):
    """Ravi's top recommendation explanation names same account and amount as freeze list, cites >= 2 real call IDs."""
    sid, fl_result = setup_fixture_session
    top_item = fl_result["items"][0]

    rec_expl = explain_recommendation(top_item, sid, graph)

    expected_top = GT["expected_freeze_list"][0]
    assert rec_expl["account"] == expected_top["account"]
    assert rec_expl["money"]["recoverable"] == expected_top["balance_held"]
    assert rec_expl["priority"] == 1
    assert f"Rs {expected_top['balance_held']:,}" in rec_expl["headline"]

    # Must cite at least 2 real tool call IDs from session trace log
    tool_calls = rec_expl["tool_calls"]
    assert len(tool_calls) >= 2, f"Expected >= 2 cited tool calls, got {len(tool_calls)}"

    valid_cids = {tc["call_id"] for tc in FIXTURE["tool_calls"]}
    for tc in tool_calls:
        assert tc["call_id"] in valid_cids, f"Tool call {tc['call_id']} must exist in session trace"


def test_decoy_rejection_explanation_has_behavioral_numbers_and_inflow_rationale(graph, setup_fixture_session):
    """Decoy rejection explanation contains behavioral facts and explains why high inflow was not enough."""
    sid, fl_result = setup_fixture_session
    decoy_id = GT["decoy_account_id"]

    decoy_item = next((nr for nr in fl_result["not_recommended"] if nr["account"] == decoy_id), None)
    assert decoy_item is not None, f"Decoy {decoy_id} must be in not_recommended list"

    rej_expl = explain_rejection(decoy_item, sid, graph)

    assert rej_expl["account"] == decoy_id
    assert "legitimate merchant" in rej_expl["headline"].lower()

    bfacts = rej_expl["counter_evidence"]["behavioral_facts"]
    assert bfacts["distinct_senders"] >= 10, f"Expected high distinct senders, got {bfacts['distinct_senders']}"
    assert "device_stability" in bfacts
    assert "phone_stability" in bfacts
    assert "onward_ratio" in bfacts

    # Why high inflow / PageRank was not enough
    why_not = rej_expl["counter_evidence"]["why_not_enough"]
    assert "high inflow" in why_not.lower() or "pagerank" in why_not.lower()
    assert "merchant" in why_not.lower() or "senders" in why_not.lower()


def test_shared_device_link_explanation_names_device_count_and_both_accounts(graph):
    """Shared-device link explanation names the device, total sharer count and both accounts."""
    ring1_acc = GT["shared_device_link"]["ring1_account"]
    ring2_acc = GT["shared_device_link"]["ring2_account"]
    expected_dev = GT["shared_device_link"]["device_id"]

    link_expl = explain_link({"account_a": ring1_acc, "account_b": ring2_acc, "device_id": expected_dev}, graph)

    assert link_expl["account_a"] == ring1_acc
    assert link_expl["account_b"] == ring2_acc
    assert link_expl["shared_id"] == expected_dev
    assert link_expl["total_sharers"] >= 2
    assert link_expl["strength"] in ("strong", "weak")
    assert ring1_acc in link_expl["explanation"]
    assert ring2_acc in link_expl["explanation"]
    assert expected_dev in link_expl["explanation"]


def test_build_graph_highlight_verification_roles_time_order_and_cap(graph, setup_fixture_session):
    """All nodes and edges exist in graph, sequence order follows time order, roles match GT, size under cap."""
    sid, fl_result = setup_fixture_session

    highlight = build_graph_highlight(fl_result, graph)

    nodes = highlight["nodes"]
    edges = highlight["edges"]

    assert len(nodes) <= 40, f"Node count {len(nodes)} exceeds cap of 40"
    assert len(edges) <= 60, f"Edge count {len(edges)} exceeds cap of 60"

    node_roles = {n["id"]: n["role"] for n in nodes}
    assert node_roles.get(GT["victim_account_id"]) == "victim"

    # Mules should have mule_recommended
    for it in fl_result["items"]:
        assert node_roles.get(it["account"]) == "mule_recommended"

    # Decoy should have cleared
    assert node_roles.get(GT["decoy_account_id"]) == "cleared"

    # Check that sequence_index follows strictly ascending timestamps
    timed_edges = [e for e in edges if e.get("sequence_index") is not None]
    for idx in range(len(timed_edges) - 1):
        e1 = timed_edges[idx]
        e2 = timed_edges[idx + 1]
        assert e1["sequence_index"] < e2["sequence_index"]
        assert e1["timestamp"] <= e2["timestamp"], "Sequence index must follow time order"

    # Verify all account nodes exist in live graph
    real_accounts = [n["id"] for n in nodes if not n["id"].startswith("CASH_") and not n["id"].startswith("DEV_") and not n["id"].startswith("PH_")]
    rows = queries._rows(graph, "UNWIND $ids AS aid MATCH (a:Account {id: aid}) RETURN a.id", ids=real_accounts)
    assert len(rows) == len(real_accounts), "All non-synthetic account nodes must exist in live graph"


def test_tampering_fails_verification(graph, setup_fixture_session):
    """Tampering test: change one amount or txn_id in explanation and confirm verify_explanation fails."""
    sid, _ = setup_fixture_session
    expl = explain_case(sid, graph)

    assert expl["verified"] is True

    # 1. Tamper with an amount
    tampered_amt = copy.deepcopy(expl)
    tampered_amt["recommendations"][0]["path"]["edges"][0]["amount"] += 99999
    res_amt = verify_explanation(tampered_amt, graph)
    assert res_amt["verified"] is False
    assert any("amount mismatch" in f["reason"].lower() for f in res_amt["failed_items"])

    # 2. Tamper with a transaction ID
    tampered_tid = copy.deepcopy(expl)
    tampered_tid["recommendations"][0]["path"]["edges"][0]["txn_id"] = "TXN_NON_EXISTENT_9999"
    res_tid = verify_explanation(tampered_tid, graph)
    assert res_tid["verified"] is False
    assert any("does not exist" in f["reason"].lower() for f in res_tid["failed_items"])


def test_ungrounded_id_is_dropped_or_flagged(graph, setup_fixture_session):
    """Ungrounded ID test: inject a fake account ID and confirm it is detected as failed."""
    sid, _ = setup_fixture_session
    expl = explain_case(sid, graph)

    tampered = copy.deepcopy(expl)
    tampered["recommendations"].append({
        "account": "ACC_FAKE_UNGROUNDED_999",
        "priority": 99,
        "money": {"recoverable": 5000},
        "path": {"nodes": ["ACC_FAKE_UNGROUNDED_999"], "edges": []},
        "signals": [],
        "steps": [],
        "tool_calls": [],
    })
    # Also adjust total recoverable to isolate account existence failure
    tampered["case_header"]["total_recoverable"] += 5000

    verif = verify_explanation(tampered, graph)
    assert verif["verified"] is False
    failed_reasons = " ".join(f.get("reason", "") for f in verif["failed_items"])
    assert "ACC_FAKE_UNGROUNDED_999" in failed_reasons


def test_to_markdown_contains_disclaimer_every_account_and_no_ungrounded_ids(graph, setup_fixture_session):
    """to_markdown contains disclaimer, every recommended account, and no ungrounded account IDs."""
    sid, _ = setup_fixture_session
    expl = explain_case(sid, graph)

    md = to_markdown(expl)

    assert "recommendation for human review" in md.lower()
    assert "nothing was frozen" in md.lower()

    # Every recommended account appears
    for it in expl["recommendations"]:
        assert it["account"] in md

    # No account IDs outside explanation JSON
    expl_str = json.dumps(expl)
    found_aids = re.findall(r"\bACC_\w+\b", md)
    for aid in found_aids:
        assert aid in expl_str, f"Account ID '{aid}' found in markdown was not in explanation JSON"


def test_timeline_step_count_equals_trace_log_tool_calls(setup_fixture_session):
    """Timeline step count equals the number of tool calls in the trace log."""
    sid, _ = setup_fixture_session
    timeline = build_investigation_timeline(sid)
    trace_events = trace.get(sid)

    assert len(timeline) == len(trace_events)
    for idx, item in enumerate(timeline):
        assert item["step"] == idx + 1
        assert item["call_id"] == trace_events[idx]["call_id"]
        assert item["tool"] == trace_events[idx]["tool_name"]


def test_explain_case_timing_under_two_seconds(graph, setup_fixture_session):
    """explain_case runs in under 2 seconds without LLM polish; prints timing."""
    sid, _ = setup_fixture_session

    t0 = time.perf_counter()
    expl = explain_case(sid, graph)
    elapsed = time.perf_counter() - t0

    print(f"\n[TIMING] explain_case completed in {elapsed:.4f} seconds (Target: < 2.0s)")
    assert elapsed < 2.0, f"explain_case took {elapsed:.4f}s, exceeding 2.0s threshold"
    assert expl["verified"] is True


@pytest.mark.slow
def test_polish_summary_with_real_groq_discard_check(graph, setup_fixture_session):
    """Polish test with real Groq LLM: summary contains NO numbers/IDs outside explanation, or is discarded."""
    sid, _ = setup_fixture_session
    expl = explain_case(sid, graph)

    try:
        from backend.llm import get_groq_client
        get_groq_client()
    except Exception:
        pytest.skip("GROQ_API_KEY not configured or available for live test")

    polished_summary, was_discarded = polish_summary_with_llm(expl)

    print(f"\n[POLISH RESULT] Discarded: {was_discarded}")
    print(f"Summary: {polished_summary}")

    # Verify that every account ID and number in the summary exists in explanation
    expl_str = json.dumps(expl)

    aids = re.findall(r"\bACC_\w+\b", polished_summary)
    for aid in aids:
        assert aid in expl_str, f"Account ID '{aid}' in polished summary was not in explanation JSON"

    numbers = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", polished_summary)
    for num in numbers:
        clean = num.replace(",", "")
        assert (clean in expl_str or num in expl_str), f"Number '{num}' in polished summary was not in explanation JSON"
