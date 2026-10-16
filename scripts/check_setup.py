"""Verify the MuleTrace setup end to end.

Checks:
  (a) connects to FalkorDB
  (b) creates a test graph with two nodes and one edge
  (c) reads it back with a Cypher query
  (d) deletes the test graph
  (e) checks GROQ_API_KEY is set and makes one tiny LLM call (Groq)

Prints PASS / FAIL for every step and exits non-zero if any step fails.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

TEST_GRAPH = "muletrace_setup_check"
PASSED = True


def report(step: str, ok: bool, detail: str = "") -> None:
    global PASSED
    status = "PASS" if ok else "FAIL"
    marker = "OK " if ok else "XX "
    if not ok:
        PASSED = False
    line = f"[{status}] {step}"
    if detail:
        line += f" - {detail}"
    print(f"{marker}{line}")


def main() -> int:
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    llm_provider = os.getenv("LLM_PROVIDER", "groq")
    llm_api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY", "")
    llm_model = os.getenv("LLM_MODEL", "")

    print(f"== MuleTrace setup check (FalkorDB {host}:{port}) ==")

    # (a) Connect to FalkorDB
    try:
        from falkordb import FalkorDB

        db = FalkorDB(host=host, port=port)
        db.list_graphs()  # round-trip to the server
        report("a. connect to FalkorDB", True, f"{host}:{port}")
    except Exception as exc:  # pragma: no cover - failure path
        report("a. connect to FalkorDB", False, str(exc))
        return 1

    graph = db.select_graph(TEST_GRAPH)

    # (b) Create a test graph: two nodes, one edge
    try:
        graph.query(
            "CREATE (a:SetupCheck {name:'alpha'}) "
            "-[:TRANSFER {amount:100}]-> "
            "(b:SetupCheck {name:'beta'})"
        )
        report("b. create test graph (2 nodes, 1 edge)", True)
    except Exception as exc:  # pragma: no cover - failure path
        report("b. create test graph (2 nodes, 1 edge)", False, str(exc))

    # (c) Read it back with Cypher
    try:
        result = graph.query(
            "MATCH (a:SetupCheck {name:'alpha'}) "
            "-[r:TRANSFER]->(b:SetupCheck {name:'beta'}) "
            "RETURN a.name, b.name, r.amount"
        )
        rows = result.result_set
        if rows and len(rows) == 1:
            report("c. read graph back via Cypher", True, f"rows={rows[0]}")
        else:
            report("c. read graph back via Cypher", False, f"unexpected rows: {rows}")
    except Exception as exc:  # pragma: no cover - failure path
        report("c. read graph back via Cypher", False, str(exc))

    # (d) Delete the test graph
    try:
        graph.delete()
        report("d. delete test graph", True)
    except Exception as exc:  # pragma: no cover - failure path
        report("d. delete test graph", False, str(exc))

    # (e) LLM test call
    if not llm_api_key:
        report(
            "e. LLM connectivity",
            False,
            "GROQ_API_KEY is not set in .env (add your Groq key)",
        )
    elif llm_provider != "groq":
        report(
            "e. LLM connectivity",
            False,
            f"unsupported LLM_PROVIDER={llm_provider!r} (expected 'groq')",
        )
    else:
        try:
            from backend.llm import get_groq_client, get_llm_model

            client = get_groq_client()
            model = llm_model or get_llm_model()
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                max_tokens=5,
            )
            content = (resp.choices[0].message.content or "").strip()
            report("e. LLM connectivity", True, f"model={model} reply={content!r}")
        except Exception as exc:  # pragma: no cover - failure path
            report("e. LLM connectivity", False, str(exc))

    print("=" * 40)
    if PASSED:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())