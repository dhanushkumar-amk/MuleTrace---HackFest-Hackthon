# MuleTrace

AI agent for the Graph Hacks hackathon (FalkorDB, Track 01: Agents That Act on Connected Data). It traces UPI fraud money through chains of mule accounts stored in a FalkorDB graph, ranks which accounts to freeze, and explains every decision with the exact graph path.

**Status: Phase 11 — Freeze-list ranking, decoy protection, and memory write-back (Track 02 bonus) implemented and verified.** Phase 12 (Explainability views) comes next.

## Project summary

- [`docs/SCOPE.md`](docs/SCOPE.md) — what we build (and deliberately don't), Track 01
  criteria mapping, risks.
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — the exact 2-minute demo, second by second.
- [`docs/TOOLS.md`](docs/TOOLS.md) — the 8 agent graph tools and their JSON contracts.
- [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) — 12 testable pass/fail checks.
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — node/relationship schema, tool mappings, Mermaid diagram.
- [`docs/QUERIES.md`](docs/QUERIES.md) — Phase 7: core Cypher queries, parameters, example outputs and runtimes.
- [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) — Phase 8: graph algorithms, native discovery vs NetworkX, example outputs and runtimes.
- [`docs/DATA_NOTES.md`](docs/DATA_NOTES.md) — the planted rings + decoy (presenter notes; the agent never reads this).
- [`docs/BROWSER_QUERIES.md`](docs/BROWSER_QUERIES.md) — ready-to-paste FalkorDB Browser queries.

## Stack
- **Database:** FalkorDB (Docker), graph named `muletrace`
- **Backend:** FastAPI + the `falkordb` Python client + `networkx`
- **LLM:** Groq (`groq` Python SDK)
- **Frontend:** React + Vite (JS), `react-force-graph-2d`

## Project layout
```
muletrace/
├── data/
│   ├── generated/        # synthetic data (gitignored, regenerate anytime)
│   └── sample/           # committed sample (first 20 rows) of each file
├── backend/
│   ├── db.py             # get_graph() -> FalkorDB graph
│   ├── main.py           # FastAPI app, GET /health, CORS
│   ├── queries.py        # Phase 7: core read-only Cypher queries
│   ├── algorithms.py     # Phase 8: graph algorithms (shortest path, PageRank, WCC, Louvain, betweenness)
│   ├── graph_tools.py    # Phase 2
│   └── agent.py          # Phase 2
├── frontend/             # React + Vite app
├── scripts/
│   ├── check_setup.py    # verifies the full setup
│   ├── create_schema.py  # creates FalkorDB indexes
│   ├── verify_schema.py  # verifies node/edge types against the schema
│   ├── generate_data.py  # Phase 4: builds the synthetic normal dataset
│   ├── plant_fraud.py    # Phase 5: plants rings + decoy on the base world
│   ├── validate_data.py  # base-data PASS/FAIL checks + reproducibility
│   ├── validate_fraud.py # Phase 5: fraud answer-key checks
│   ├── load_graph.py     # Phase 6: batched idempotent load into FalkorDB
│   ├── verify_graph.py   # Phase 6: verify loaded graph vs CSVs + answer key
│   ├── graph_stats.py    # Phase 6: quick graph summary
│   ├── try_queries.py    # Phase 7: CLI runner for core queries
│   ├── try_algorithms.py # Phase 8: CLI runner for graph algorithms
│   └── datagen/          # generator core (accounts, devices, transactions, cashout)
├── tests/
│   ├── ground_truth.json # Phase 5 answer key (rings, freeze list) - committed
│   ├── test_queries.py   # Phase 7: pytest suite for core queries
│   └── test_algorithms.py# Phase 8: pytest suite for graph algorithms
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

## Synthetic dataset (Phases 4 + 5) & Analysis (Phases 7 + 8)

Generate the normal base world, then plant the fraud rings + decoy on top, then
validate. Final data lands in `data/generated/` (gitignored) and the answer key in
`tests/ground_truth.json` (committed). A pristine base snapshot is kept in
`data/generated/base/` so `plant_fraud.py` is idempotent.

```bash
# 1) build the normal base world (seed=7, scale=1.0) and refresh data/sample/
python scripts/generate_data.py

# 2) plant 3 fraud rings + the decoy + Ravi's FraudReport on top of the base
python scripts/plant_fraud.py          # --seed defaults to 7

# 3) validate base-data invariants (auto-adjusts for planted data)
python scripts/validate_data.py

# 4) validate the fraud answer-key invariants (rings, freeze list, decoy, etc.)
python scripts/validate_fraud.py

# 5) load the merged data into FalkorDB (idempotent; --reset to rebuild)
python scripts/load_graph.py --reset

# 6) verify the loaded graph against the CSVs + answer key
python scripts/verify_graph.py

# 7) quick summary of the graph
python scripts/graph_stats.py

# 8) run the Phase 7 & Phase 8 test suites
python -m pytest tests/test_queries.py tests/test_algorithms.py -v -s

# 9) run the interactive runners
python scripts/try_queries.py
python scripts/try_algorithms.py

# 10) Phase 11: run freeze list unit tests
python -m pytest tests/test_freeze.py -v

# 11) Phase 11: run autonomous agent on Ravi's report
python scripts/run_agent.py --report FR_0001 --save-memory

# 12) Phase 11: run 5-run agent benchmark evaluation
python scripts/eval_agent.py --runs 5
```

Start FalkorDB with `docker compose up -d` (Browser UI: http://localhost:3000).
9 plain CSVs are written (accounts, phones, account_phone, devices,
account_device, cashout_points, transactions, paid_edges, cashed_out_at) plus
`meta.json`, and (after planting) `fraud_reports.csv`. Output is fully
reproducible from `(seed, scale)`. Account IDs `ACC_0461..ACC_0500` are the
reserved Phase 5 range (mules + decoy all live here). See
[`docs/DATA_NOTES.md`](docs/DATA_NOTES.md) for the exact planted rings + decoy,
and beware: to regenerate with a *different* seed, delete `data/generated/base/`
first so it is re-snapshotted.

## Quick start

### 1. Start FalkorDB
```bash
docker compose up -d
# Browser UI: http://localhost:3000   (database: localhost:6379)
```

### 2. Python backend
```bash
# create a venv (Windows: `py -3.11` launcher, or plain `python` if you have it)
py -3.11 -m venv .venv

# activate it
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# install dependencies
pip install -r requirements.txt
```

### 3. Configure environment
```bash
# copy the template (already done; add your key to .env)
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
# then set GROQ_API_KEY=<your Groq key> in .env
```

### 4. Verify the setup
```bash
python scripts/check_setup.py
# every step should print PASS
```

### 5. Run the backend API
```bash
uvicorn backend.main:app --reload --port 8000
# health check: http://localhost:8000/health
```

### 6. Run the frontend
```bash
cd frontend
npm install
npm run dev
# dev server: http://localhost:5173
```

## Config keys (.env)
| Key | Default | Purpose |
| --- | --- | --- |
| `FALKORDB_HOST` | `localhost` | FalkorDB host |
| `FALKORDB_PORT` | `6379` | FalkorDB port |
| `GRAPH_NAME` | `muletrace` | FalkorDB graph name |
| `LLM_PROVIDER` | `groq` | LLM provider |
| `GROQ_API_KEY` | *(empty)* | Groq API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | LLM model |