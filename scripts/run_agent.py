"""Run autonomous MuleTrace agent investigation and print formatted freeze recommendations (Phase 11).

Prints the freeze list as a readable terminal table:
  Priority | Account | Bank | Amount Recoverable | Confidence | Path Text

Usage:
  python scripts/run_agent.py [--report FR_0001] [--save-memory]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent import run_investigation


def print_table(result: dict) -> None:
    print("\n" + "=" * 105)
    print(f"MULETRACE INVESTIGATION REPORT: {result['report_id']}")
    print("STATUS: RECOMMENDATION FOR HUMAN REVIEW ONLY (No automated freezing)")
    print("=" * 105)

    freeze_list = result.get("freeze_list", [])
    if not freeze_list:
        print("No freeze recommendations produced.")
    else:
        print(f"{'Priority':<10} | {'Account':<12} | {'Bank':<22} | {'Recoverable':<14} | {'Confidence':<10} | {'Path Text'}")
        print("-" * 105)
        for it in freeze_list:
            amt_str = f"Rs {it['amount_recoverable']:,}"
            print(
                f"{it['priority']:<10} | {it['account']:<12} | {it['bank'][:20]:<22} | "
                f"{amt_str:<14} | {it['confidence']:<10} | {it['path_text']}"
            )
        print("-" * 105)
        print(f"TOTAL RECOVERABLE: Rs {result['total_recoverable']:,} | TOTAL CASHED OUT: Rs {result['total_cashed_out']:,}")

    not_recommended = result.get("not_recommended", [])
    if not_recommended:
        print("\nNOT RECOMMENDED (Decoy / Low Confidence / Excluded):")
        for nr in not_recommended:
            print(f"  - {nr['account']}: {nr['why']}")

    past_cases = result.get("past_cases", [])
    if past_cases:
        print(f"\nRECALLED PAST CASES ({len(past_cases)}):")
        for pc in past_cases:
            link = pc.get("link_type", "direct")
            print(f"  - Case {pc.get('case_id')} ({pc.get('report_id')}) via {link}: {pc.get('summary')}")

    print("\nMETRICS & AUDIT:")
    print(f"  - Steps Taken:       {result.get('steps_taken')}")
    print(f"  - Claims Removed:    {result.get('claims_removed')}")
    print(f"  - Memory Saved:      {result.get('memory_saved')}")
    print(f"  - LLM Time:          {result.get('llm_time_seconds')}s")
    print(f"  - Tool Time:         {result.get('tool_time_seconds')}s")
    print(f"  - Total Duration:    {result.get('total_time_seconds')}s")
    print("=" * 105)

    if result.get("summary"):
        print("\nINVESTIGATION SUMMARY NARRATIVE:")
        print(result["summary"].strip())
        print("=" * 105 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run autonomous MuleTrace investigation.")
    parser.add_argument("--report", default="FR_0001", help="Fraud report ID (default FR_0001)")
    parser.add_argument("--save-memory", action="store_true", help="Persist findings to memory graph")
    parser.add_argument("--max-steps", type=int, default=15, help="Maximum interaction steps")
    parser.add_argument("--explain", action="store_true", help="Print verified plain-English markdown explanation report after run")
    args = parser.parse_args()

    print(f"== Launching autonomous MuleTrace agent for {args.report} ==")
    result = run_investigation(
        query_or_report_id=args.report,
        max_steps=args.max_steps,
        save_memory=args.save_memory,
    )
    print_table(result)

    if args.explain:
        from backend.explain import explain_case
        from backend.explain_text import to_markdown
        session_id = result.get("session_id")
        if session_id:
            print("\n" + "=" * 105)
            print("MULETRACE PLAIN-ENGLISH CASE EXPLANATION REPORT:")
            print("=" * 105 + "\n")
            explanation = explain_case(session_id)
            print(to_markdown(explanation))

    return 0


if __name__ == "__main__":
    sys.exit(main())
