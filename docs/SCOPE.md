# MuleTrace — Scope Lock

## Product statement
MuleTrace is an AI agent that, given a reported UPI fraud, traces the stolen money
through chains of mule accounts in a FalkorDB graph, ranks which accounts to freeze
first, and explains every recommendation with the exact graph path.

## Track 01 criteria mapping
| Track 01 focus | How MuleTrace satisfies it |
| --- | --- |
| Multi-hop reasoning | The agent follows money a hop at a time (Ravi → A → B → …) instead of asking a single flat question |
| Graph queries/algorithms as agent tools | Every capability is exposed as a discrete tool (shortest path, PageRank, community detection, etc.) the agent calls |
| Tool selection through MCP | Tools are registered on an MCP server; the LLM picks which tool to call for the current step |
| Actions based on what the graph shows | The agent only freezes accounts the actual graph path says still hold money — no guessing |
| Explainable results | Every freeze recommendation carries its full path, e.g. `Ravi → A → B: Rs 40,000 still held` |

## IN SCOPE (the only things we build)
- **Dataset (synthetic):** ~500 accounts, 5,000 normal transactions, 3 planted fraud
  rings, 1 decoy.
- **Agent:** takes a fraud report (victim account, amount, time) and returns a ranked
  freeze list.
- **6–8 graph tools** the agent chooses from (see `TOOLS.md`).
- **Explainability:** every recommendation includes its graph path.
- **Web UI:** graph view where the money chain lights up, plus a text explanation.

## OUT OF SCOPE (we will NOT build)
- Real bank or UPI integrations
- Authentication / login
- Real personal data
- ML model training
- Multi-tenant support
- Deployment or hosting
- Mobile app
- Freezing money for real
- Anything not needed for the demo

## Risks & mitigations
| Risk | Mitigation |
| --- | --- |
| Data too clean → agent looks trivial | Plant noise: a decoy, normal busy accounts, small worthless hops; vary ring shapes |
| Agent picks the wrong tool | All tools share a strict JSON contract; agent is instructed and acceptance checks target tool health |
| Graph UI too slow on large draws | Cap rendered nodes (~500) and highlight only the returned path; cached layout |
| Running out of time | 3-day plan: seed → tools → agent → UI; docs already scope-locked, no features creep |
| LLM output not parseable | Every tool call returns typed JSON; agent output is validated and re-prompted once on failure |