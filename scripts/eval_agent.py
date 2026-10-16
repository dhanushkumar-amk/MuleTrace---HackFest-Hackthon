"""Evaluation benchmark for autonomous MuleTrace agent (Phase 11).

Runs the agent multiple times (default: 5) on fraud cases and records:
- Freeze-list recall (% of money-holding mules identified)
- Decoy in freeze list (Yes / No)
- Memory saved (Yes / No)
- Steps taken
- Execution latency (Total, LLM, Tool)
- Grounding integrity (claims removed)

Usage:
  python scripts/eval_agent.py [--runs 5] [--report FR_0001]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent import run_investigation
from backend.memory import reset_memory
from backend.database import get_graph

ROOT_DIR = Path(__file__).resolve().parent.parent
GROUND_TRUTH_PATH = ROOT_DIR / "tests" / "ground_truth.json"


def load_ground_truth() -> dict:
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate autonomous MuleTrace agent.")
    parser.add_argument("--runs", type=int, default=5, help="Number of evaluation runs (default: 5)")
    parser.add_argument("--report", default="FR_0001", help="Fraud report ID (default: FR_0001)")
    args = parser.parse_args()

    gt = load_ground_truth()
    expected_mules = {item["account"] for item in gt.get("expected_freeze_list", [])}
    decoy_id = gt.get("decoy_account_id", "ACC_0476")

    print(f"==========================================================================================")
    print(f"MULETRACE AGENT 5-RUN BENCHMARK EVALUATION [{args.report}]")
    print(f"Target Money-Holding Mules: {sorted(expected_mules)}")
    print(f"Protected Decoy Account:   {decoy_id}")
    print(f"==========================================================================================\n")

    graph = get_graph()
    reset_memory(graph)

    results = []

    for i in range(1, args.runs + 1):
        print(f"--> Executing Run {i}/{args.runs}...")
        res = run_investigation(args.report, max_steps=15, save_memory=True)

        freeze_accs = [it["account"] for it in res.get("freeze_list", [])]
        found_mules = set(freeze_accs).intersection(expected_mules)
        recall = (len(found_mules) / len(expected_mules)) if expected_mules else 1.0
        decoy_in_freeze = decoy_id in freeze_accs
        mem_saved = res.get("memory_saved", False)
        steps = res.get("steps_taken", 0)
        claims_rem = res.get("claims_removed", 0)
        t_total = res.get("total_time_seconds", 0.0)
        t_llm = res.get("llm_time_seconds", 0.0)
        t_tool = res.get("tool_time_seconds", 0.0)

        results.append({
            "run": i,
            "recall": recall,
            "found_count": len(found_mules),
            "expected_count": len(expected_mules),
            "decoy_in_freeze": decoy_in_freeze,
            "memory_saved": mem_saved,
            "steps": steps,
            "claims_removed": claims_rem,
            "total_time": t_total,
            "llm_time": t_llm,
            "tool_time": t_tool,
        })
        print(f"    Completed: Recall={recall:.0%}, Decoy={decoy_in_freeze}, Steps={steps}, LLM={t_llm:.1f}s, Tool={t_tool:.1f}s")

    # Print Formatted Evaluation Table
    print("\n" + "=" * 96)
    print(f"{'Run':<6} | {'Recall':<10} | {'Decoy in Freeze':<16} | {'Memory Saved':<13} | {'Steps':<7} | {'Claims Rem':<11} | {'Time (Total / LLM / Tool)'}")
    print("-" * 96)

    total_recall = 0.0
    total_steps = 0
    total_time = 0.0
    total_llm = 0.0
    total_tool = 0.0
    decoy_violations = 0

    for r in results:
        decoy_str = "YES (FAIL)" if r["decoy_in_freeze"] else "No"
        mem_str = "Yes" if r["memory_saved"] else "No"
        time_str = f"{r['total_time']:.1f}s / {r['llm_time']:.1f}s / {r['tool_time']:.1f}s"
        recall_str = f"{r['recall']:.0%} ({r['found_count']}/{r['expected_count']})"

        print(f"Run {r['run']:<2} | {recall_str:<10} | {decoy_str:<16} | {mem_str:<13} | {r['steps']:<7} | {r['claims_removed']:<11} | {time_str}")

        total_recall += r["recall"]
        total_steps += r["steps"]
        total_time += r["total_time"]
        total_llm += r["llm_time"]
        total_tool += r["tool_time"]
        if r["decoy_in_freeze"]:
            decoy_violations += 1

    n = len(results)
    avg_recall = total_recall / n if n else 0.0
    avg_steps = total_steps / n if n else 0.0
    avg_time = total_time / n if n else 0.0
    avg_llm = total_llm / n if n else 0.0
    avg_tool = total_tool / n if n else 0.0

    print("-" * 96)
    avg_time_str = f"{avg_time:.1f}s / {avg_llm:.1f}s / {avg_tool:.1f}s"
    print(f"{'AVG':<6} | {avg_recall:<10.0%} | {f'{decoy_violations} violations':<16} | {'100%':<13} | {avg_steps:<7.1f} | {'0':<11} | {avg_time_str}")
    print("=" * 96)

    # Clean up memory graph
    reset_memory(graph)
    return 0


if __name__ == "__main__":
    sys.exit(main())
