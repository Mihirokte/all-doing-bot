# CLAUDE.md — Agent Instructions for all-doing-bot

> This file provides instructions for AI coding agents building this project.
> Read `plan.md` for the full implementation plan. This file covers conventions,
> constraints, and architectural rules.

## Project Summary

A personal, always-on LLM bot that parses natural-language queries into cohorts
(named categories) and actions (repeatable tasks), executes them via a local Qwen
model on CPU, and stores results in Google Sheets.

Single user. Always running. Minimal resources.

## Tech Decisions (Already Made — Do Not Change)

| Decision | Choice | Why |
|----------|--------|-----|
| Language | Python 3.11+ | Backend + LLM bindings ecosystem |
| Web framework | FastAPI + uvicorn | Async-native, lightweight |
| LLM | Qwen3.5-2B Q4 via llama-cpp-python | Best quality/resource ratio for CPU |
| Database | Google Sheets via gspread | Free, text-only, human-readable |
| Web extraction | readability-lxml + markdownify | Python markdowner equivalent |
| Frontend | Static HTML/JS on GitHub Pages | Free hosting, no build step |
| Hosting | AWS EC2 free tier + systemd | Always-on, auto-restart |
| Task queue | asyncio (in-process) | Single user, no external deps |

## Repository Structure

```
all-doing-bot/
├── README.md
├── CLAUDE.md              # This file
├── plan.md                # Implementation plan
├── LICENSE
├── backend/
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # All configuration
│   ├── requirements.txt
│   ├── models/
│   │   └── schemas.py     # Pydantic models
│   ├── llm/
│   │   ├── engine.py      # LLM loading and inference
│   │   ├── prompts.py     # All prompt templates
│   │   └── output_parser.py
│   ├── pipeline/
│   │   ├── router.py      # Query routing
│   │   ├── stages.py      # Pipeline stage definitions
│   │   ├── executor.py    # Stage orchestration
│   │   └── task_store.py  # In-memory task state
│   ├── extractor/
│   │   ├── fetcher.py     # HTTP fetching
│   │   ├── cleaner.py     # HTML → markdown
│   │   └── cache.py       # URL content cache
│   ├── db/
│   │   ├── sheets.py      # Google Sheets CRUD
│   │   ├── catalogue.py   # Master catalogue ops
│   │   └── models.py      # DB record schemas
│   ├── actions/
│   │   ├── registry.py    # Action type registry
│   │   ├── base.py        # Abstract base action
│   │   ├── web_fetch.py   # Web fetch action
│   │   ├── api_call.py    # API call action
│   │   └── transform.py   # Data transform action
│   └── deploy/
│       ├── alldoing.service  # systemd unit file
│       └── health_check.sh   # Health monitoring script
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   ├── js/
│   │   ├── app.js
│   │   ├── api.js
│   │   └── config.js
│   └── assets/
└── tests/
    ├── test_pipeline.py
    ├── test_llm.py
    ├── test_extractor.py
    ├── test_db.py
    └── test_actions.py
```

## Architecture Rules

### 1. Structured Pipeline — Always

Every user query flows through: **Parse → Plan → Execute → Store**.

No shortcuts. No direct DB writes from query handlers. The pipeline is the
single path for all data flow.

### 2. Minimal Tokens Per LLM Call

This is the most critical constraint. The LLM runs on CPU and is slow.

- **Each LLM call must receive < 1000 input tokens.**
- Never pass full conversation history. Stages are stateless.
- Use JSON-only output with grammar enforcement.
- Truncate web content to ~2000 chars before sending to LLM.
- Decompose complex queries into multiple small LLM calls rather than one large one.

### 3. Generality Over Specificity

- The pipeline handles ALL query types through the same stages.
- New capabilities are added by creating a new action class in `actions/`, not by modifying the pipeline.
- The action registry pattern (inspired by agent-orchestrator's plugin architecture) must be maintained.

### 4. Google Sheets Schema

- One master spreadsheet with a `_catalogue` sheet.
- Each cohort gets its own sheet within that spreadsheet.
- All operations go through the `db/` module. No direct gspread calls elsewhere.

### 5. Async Throughout

- All I/O operations (web fetch, Google Sheets, LLM inference) must be async or run in thread pool executors.
- Use `asyncio.create_task` for background pipeline work.
- Never block the event loop.

## Coding Conventions

- **Type hints** on all function signatures.
- **Pydantic models** for all data structures that cross module boundaries.
- **No global mutable state** except the LLM engine singleton and task store.
- **Config via environment variables** loaded in `config.py`, never hardcoded.
- **Logging** via Python `logging` module, not `print()`.
- **Error handling**: catch at stage boundaries, log, update task status, continue.
- **No external task queue** (no Celery, no Redis). asyncio only.
- **Dependencies**: keep minimal. Every pip package must be justified.

## Testing Strategy

- **Unit tests** for each module (LLM output parsing, extractor cleaning, DB operations).
- **Mock the LLM** in tests — use canned JSON responses.
- **Mock Google Sheets** in tests — use a dict-based fake.
- **Integration test**: one end-to-end test that processes a sample query through the full pipeline with all mocks.
- Run tests with `pytest` from the repo root.

## Security Notes

- Google service account credentials go in `backend/credentials/` and are **gitignored**.
- No authentication on the API by default (single user, discuss later).
- Never log full LLM prompts in production (may contain user data).
- Sanitize URLs before fetching (no SSRF to internal IPs).

## How to Run

```bash
# Backend
cd backend
pip install -r requirements.txt
export GOOGLE_CREDS_PATH=credentials/service_account.json
export MODEL_PATH=/path/to/qwen3.5-2b-q4_k_m.gguf
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend (local dev)
cd frontend
python -m http.server 3000
```

## Key References

- [plan.md](./plan.md) — Full implementation plan with phases and acceptance criteria
- [agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) — Architecture reference
- [markdowner](https://github.com/supermemoryai/markdowner) — Web extraction approach reference
