# MuleTrace

AI agent for the Graph Hacks hackathon (FalkorDB, Track 01: Agents That Act on Connected Data). It traces UPI fraud money through chains of mule accounts stored in a FalkorDB graph, ranks which accounts to freeze, and explains every decision with the exact graph path.

**Status: Phase 4 — synthetic normal-world dataset ready.** Fraud rings (Phase 5) and FalkorDB loading (Phase 6) come next.

## Project summary

- [`docs/SCOPE.md`](docs/SCOPE.md) — what we build (and deliberately don't), Track 01
  criteria mapping, risks.
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — the exact 2-minute demo, second by second.
- [`docs/TOOLS.md`](docs/TOOLS.md) — the 8 agent graph tools and their JSON contracts.
- [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) — 12 testable pass/fail checks.
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — node/relationship schema, tool mappings, Mermaid diagram.

## Stack
- **Database:** FalkorDB (Docker), graph named `muletrace`
- **Backend:** FastAPI + the `falkordb` Python client
- **LLM:** Groq (OpenAI-compatible `groq` SDK)
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
│   ├── graph_tools.py    # Phase 2
│   └── agent.py          # Phase 2
├── frontend/             # React + Vite app
├── scripts/
│   ├── check_setup.py    # verifies the full setup
│   ├── create_schema.py  # creates FalkorDB indexes
│   ├── verify_schema.py  # verifies node/edge types against the schema
│   ├── generate_data.py  # Phase 4: builds the synthetic normal dataset
│   ├── validate_data.py  # Phase 4: PASS/FAIL checks + reproducibility
│   └── datagen/          # generator core (accounts, devices, transactions, cashout)
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

## Synthetic dataset (Phase 4)

Generate the normal (non-fraud) base world and validate it:

```bash
# generate data/generated/ (seed=7, scale=1.0) and refresh data/sample/
python scripts/generate_data.py
# custom seed / size
python scripts/generate_data.py --seed 42 --scale 1.5
# validate: PASS/FAIL checks + reproducibility (regenerates into a temp dir)
python scripts/validate_data.py
```

9 plain CSVs are written (accounts, phones, account_phone, devices,
account_device, cashout_points, transactions, paid_edges, cashed_out_at) plus a
`meta.json` describing the 30-day window. Output is fully reproducible from
`(seed, scale)`. Account IDs `ACC_0461..ACC_0500` are reserved for Phase 5's
mule + decoy accounts.

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
# then set LLM_API_KEY=<your Groq key> in .env
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
| `LLM_API_KEY` | *(empty)* | Groq API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | LLM model |