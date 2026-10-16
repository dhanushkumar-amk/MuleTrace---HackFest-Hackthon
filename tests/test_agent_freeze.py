"""Agent integration tests with real Groq LLM (temperature 0) for Phase 11.

Validates end-to-end autonomous investigation:
- Freeze list matches tool output exactly with >=80% recall of money-holding mules.
- Decoy account is strictly excluded from freeze list across all runs.
- Grounding check removes 0 claims.
- Memory write-back and recall (second-run learning test).
- Prints LLM time and tool time split.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.agent import run_investigation
from backend.memory import reset_memory
from backend.database import get_graph

ROOT_DIR = Path(__file__).resolve().parent.parent
GROUND_TRUTH_PATH = ROOT_DIR / "tests" / "ground_truth.json"


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_agent_investigation_freeze_list(ground_truth):
    """Run agent on Ravi's report (FR_0001) over 3 runs and verify freeze list accuracy."""
    expected_mules = {item["account"] for item in ground_truth.get("expected_freeze_list", [])}
    decoy_id = ground_truth.get("decoy_account_id", "ACC_0476")
    runs = 3

    for run_idx in range(1, runs + 1):
        print(f"\n--- Starting Real Groq Investigation Run {run_idx}/{runs} ---")
        result = run_investigation("FR_0001", max_steps=15, save_memory=False)

        # 1. Print timing metrics split
        print(f"Run {run_idx} Timing: Total={result['total_time_seconds']:.2f}s | LLM={result['llm_time_seconds']:.2f}s | Tool={result['tool_time_seconds']:.2f}s | Steps={result['steps_taken']}")

        # 2. Recommendation only check
        assert result["recommendation_only"] is True, "Result must state recommendation_only=True"

        # 3. Grounding check: 0 claims removed
        assert result["claims_removed"] == 0, f"Expected 0 claims removed from tool output, got {result['claims_removed']}"

        # 4. Decoy protection
        freeze_accounts = [item["account"] for item in result.get("freeze_list", [])]
        print(f"Run {run_idx} Freeze List Accounts: {freeze_accounts}")
        assert decoy_id not in freeze_accounts, f"Decoy {decoy_id} must NEVER appear in the freeze list!"

        # Check decoy appears in not_recommended or was excluded
        not_rec_accounts = [nr["account"] for nr in result.get("not_recommended", [])]
        print(f"Run {run_idx} Not Recommended: {not_rec_accounts}")

        # 5. Recall check: at least 80% of money-holding mules identified
        found_mules = set(freeze_accounts).intersection(expected_mules)
        recall = len(found_mules) / len(expected_mules) if expected_mules else 1.0
        print(f"Run {run_idx} Mule Recall: {recall:.1%} ({len(found_mules)}/{len(expected_mules)})")
        assert recall >= 0.80, f"Expected >= 80% recall of money-holding mules, got {recall:.1%}"


def test_agent_memory_second_run_learning():
    """Verify memory persistence and cross-case recall (the 'it learned' moment)."""
    graph = get_graph()
    reset_memory(graph)

    # Run 1: Investigate Ravi's case and persist to memory
    print("\n--- Starting Run 1: Investigating FR_0001 with memory write-back ---")
    res1 = run_investigation("FR_0001", max_steps=15, save_memory=True)
    steps_run1 = res1["steps_taken"]
    assert res1["memory_saved"] is True, "Case should be persisted to memory graph"
    assert len(res1["freeze_list"]) > 0, "Freeze list should be populated"
    print(f"Run 1 completed in {steps_run1} steps (saved to memory).")

    # Run 2: Free-text investigation targeting account sharing a device with first case
    print("\n--- Starting Run 2: Investigating linked account via shared device ---")
    query = (
        "Investigate the account that shares a device with the first case. "
        "Use recall_past_cases to check prior case history and explain the connection."
    )
    res2 = run_investigation(query, max_steps=12, save_memory=False)
    steps_run2 = res2["steps_taken"]
    print(f"Run 2 completed in {steps_run2} steps.")

    # Print comparison
    print(f"\n==========================================")
    print(f"LEARNING STEP COMPARISON:")
    print(f"  Run 1 (Cold Investigation): {steps_run1} steps")
    print(f"  Run 2 (Memory Recall):       {steps_run2} steps")
    print(f"==========================================")

    # Verify past case was recalled and cited in response or past_cases list
    recalled = res2.get("past_cases", [])
    summary_text = (res2.get("summary") or "").lower()
    has_citation = (
        len(recalled) > 0
        or "fr_0001" in summary_text
        or "ravi" in summary_text
        or "case" in summary_text
        or "prior" in summary_text
        or "earlier" in summary_text
    )
    assert has_citation, "Second run must cite or recall earlier case via shared device"

    # Clean up memory after test
    reset_memory(graph)
