"""CLI tool to explain an investigation case in plain English, Markdown, or JSON (Phase 12).

CRITICAL COMPLIANCE NOTICE:
Every explanation represents a recommendation for human review. Nothing is frozen automatically.

Usage:
    python scripts/explain_case.py --session <id> [--format text|markdown|json] [--polish]
    python scripts/explain_case.py --latest [--format text|markdown|json] [--polish]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.explain import (
    explain_case,
    load_case_explanation,
    list_case_explanations,
    polish_summary_with_llm,
)
from backend.explain_text import to_markdown, to_plain_text
from backend.tools import trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain a MuleTrace investigation case.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session", help="Investigation trace session ID (e.g. session_1792173229108)")
    group.add_argument("--latest", action="store_true", help="Explain the most recent investigation session")
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="markdown", help="Output format (default markdown)")
    parser.add_argument("--polish", action="store_true", help="Apply optional LLM plain-English summary polish (temperature 0)")
    args = parser.parse_args()

    session_id = args.session
    if args.latest:
        saved_cases = list_case_explanations()
        if saved_cases:
            session_id = saved_cases[0].get("session_id")
        else:
            all_sessions = trace.list_sessions()
            if all_sessions:
                # filter out 'default' if other sessions exist
                named = [s for s in all_sessions if s != "default"]
                session_id = named[-1] if named else all_sessions[-1]
            else:
                print("Error: No past sessions found on disk or memory.", file=sys.stderr)
                return 1

    if not session_id:
        print("Error: Could not determine session ID.", file=sys.stderr)
        return 1

    # Load from disk if present, else build on the fly
    explanation = load_case_explanation(session_id)
    if not explanation:
        try:
            explanation = explain_case(session_id)
        except Exception as exc:
            print(f"Error generating explanation for session '{session_id}': {exc}", file=sys.stderr)
            return 1

    # Apply optional LLM polish if requested
    if args.polish:
        polished_text, discarded = polish_summary_with_llm(explanation)
        explanation["polished_summary"] = polished_text
        explanation["polish_discarded"] = discarded
        if discarded:
            print("[INFO] LLM polished summary was DISCARDED by Python verification (grounding check failed). Fallback summary retained.", file=sys.stderr)
        else:
            print("[INFO] LLM polished summary PASSED strict verification (100% grounded).", file=sys.stderr)

    if args.format == "json":
        print(json.dumps(explanation, indent=2))
    elif args.format == "text":
        print(to_plain_text(explanation))
    else:
        print(to_markdown(explanation))

    return 0


if __name__ == "__main__":
    sys.exit(main())
