# MuleTrace

AI agent for the Graph Hacks hackathon (FalkorDB, Track 01: Agents That Act on Connected Data). It traces UPI fraud money through chains of mule accounts stored in a FalkorDB graph, ranks which accounts to freeze, and explains every decision with the exact graph path.

**Status: Phase 1 — project setup only.** Graph schema, seed data, and agent logic come next.

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
├── data/                 # local data (unused in Phase 1)
├── backend/
│   ├── db.py             # get_graph() -> FalkorDB graph
│   ├── main.py           # FastAPI app, GET /health, CORS
│   ├── graph_tools.py    # Phase 2
│   └── agent.py          # Phase 2
├── frontend/             # React + Vite app
├── scripts/
│   └── check_setup.py    # verifies the full setup
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

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