# all-doing-bot — Implementation Plan

> This document is the authoritative, phased implementation plan for the all-doing-bot project.
> Every requirement from the original specification is captured here. Coding agents should
> read this end-to-end before writing any code.

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Phase 0 — Infrastructure & Model Selection](#phase-0--infrastructure--model-selection)
4. [Phase 1 — Core Backend (FastAPI)](#phase-1--core-backend-fastapi)
5. [Phase 2 — LLM Integration & Structured Pipeline](#phase-2--llm-integration--structured-pipeline)
6. [Phase 3 — Web Content Extraction](#phase-3--web-content-extraction-markdowner-approach)
7. [Phase 4 — Google Sheets DB Layer](#phase-4--google-sheets-db-layer)
8. [Phase 5 — Cohort & Action System](#phase-5--cohort--action-system)
9. [Phase 6 — Frontend (GitHub Pages)](#phase-6--frontend-github-pages)
10. [Phase 7 — Reliability & Operations](#phase-7--reliability--operations)
11. [End-to-End Example Walkthrough](#end-to-end-example-walkthrough)
12. [Open Questions & Future Work](#open-questions--future-work)

---

## 1. Project Vision

Build a **personal, always-on LLM bot** that:

- Accepts natural-language queries from a single user.
- Parses each query into a **cohort** (a named category/collection) and an **action** (a repeatable task).
- Executes the action through an **async pipeline** powered by a locally-hosted Qwen model running on CPU.
- Stores structured results in **Google Sheets** (one sheet per cohort).
- Exposes a lightweight **frontend on GitHub Pages** for interaction.

The system is designed for **one active user** (personal use). The emphasis is on:

- **Structured, general pipelines** — every new capability flows through the same parse → plan → execute → store stages.
- **Minimal token usage per LLM call** — decompose work into small, focused prompts.
- **Extensibility** — adding new action types should not require architectural changes.

### Reference Projects

| Project | What we borrow |
|---------|---------------|
| [ComposioHQ/agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) | Plugin architecture, session state machine, event-driven reaction loops, work delegation patterns. The depth and software design of their system is the benchmark for ours. |
| [supermemoryai/markdowner](https://github.com/supermemoryai/markdowner) | Web page → clean markdown conversion pipeline (Readability + Turndown). We replicate this in Python for token-efficient web content ingestion. |

---

## 2. Architecture Overview

```
┌──────────────────────┐
│   GitHub Pages UI    │  Static HTML/JS/CSS
│   (Frontend)         │  Polls backend via GET
└──────────┬───────────┘
           │ HTTPS (GET requests)
           ▼
┌──────────────────────┐
│   FastAPI Backend     │  Always-on Python process
│                      │  on AWS free-tier EC2
│  ┌────────────────┐  │
│  │  Query Router   │  │  Receives user query
│  └───────┬────────┘  │
│          ▼           │
│  ┌────────────────┐  │
│  │  LLM Pipeline   │  │  Parse → Plan → Execute → Store
│  │  (Qwen on CPU)  │  │  Each stage = small, focused LLM call
│  └───────┬────────┘  │
│          ▼           │
│  ┌────────────────┐  │
│  │  Action Engine  │  │  Web scraping, API calls, data transforms
│  └───────┬────────┘  │
│          ▼           │
│  ┌────────────────┐  │
│  │  Web Extractor  │  │  HTML → clean markdown (markdowner approach)
│  └───────┬────────┘  │
│          ▼           │
│  ┌────────────────┐  │
│  │  DB Interface   │  │  Google Sheets CRUD via gspread
│  └────────────────┘  │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Google Sheets / Drive│  Master catalogue + per-cohort sheets
└──────────────────────┘
```

### Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| LLM | **Multi-provider engine**: local GGUF via **llama.cpp**, free-tier remote API, or mock provider | Keeps the backend runnable on low-RAM hosts and fully testable without a downloaded model. |
| LLM bindings | **llama-cpp-python** | Native Python bindings for llama.cpp, supports structured JSON output. |
| Backend | **FastAPI** + **uvicorn** | Async-native, lightweight, good for single-user. |
| Task queue | **asyncio** (in-process) | No need for Celery/Redis for a single user. Simple `asyncio.create_task`. |
| Database | **Google Sheets** via **gspread** + service account | Text-only storage, free, shareable, human-readable. |
| Web extraction | **Adapter registry**: generic readability/markdownify plus Twitter/Reddit adapters | Site-specific extraction prevents common failures on feeds, blocked pages, and walled-garden platforms. |
| Frontend | **GitHub Pages** (static HTML/JS) | Free hosting, simple deployment. |
| Hosting | **AWS EC2 t2.micro** (free tier) | 1 vCPU, 1 GB RAM. Sufficient for quantized small model + FastAPI. |
| Process management | **systemd** + **cron** restart | Always-on with scheduled daily restart for cleanup. |

---

## Phase 0 — Infrastructure & Model Selection

### Objectives
- Provision AWS EC2 instance.
- Configure the LLM provider chain (local, remote, mock).
- Set up process management for always-on operation.

### Tasks

#### 0.1 AWS EC2 Setup
- Launch a **t2.micro** (or t3.micro) instance with Ubuntu 22.04+.
- Configure security group: open port 443/8000 for backend, SSH for management.
- Attach an elastic IP for stable addressing.
- Install Python 3.11+, pip, git, build-essential.

#### 0.2 LLM Provider Setup
- Configure the provider priority in `config.py` / environment variables:
  - `LLM_PROVIDER_PRIORITY=local,remote,mock`
  - `MODEL_PATH=/path/to/model.gguf` (optional local mode)
  - `REMOTE_LLM_API_KEY=...` (optional remote mode)
  - `REMOTE_LLM_BASE_URL=https://api.groq.com/openai/v1`
  - `REMOTE_LLM_MODEL=llama-3.1-8b-instant`
- Install `llama-cpp-python` only if local mode is desired:
  ```
  CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python
  ```
- Local provider checks available RAM before model load and skips itself when the model will not fit.
- Remote provider uses an OpenAI-compatible free-tier API.
- Mock provider remains available for development and test environments where no model or API key exists.

#### 0.3 Runtime Modes And Memory Budget
| Mode | Requirement | Notes |
|------|-------------|-------|
| Local | ~2 GB RAM recommended for Qwen3.5-2B Q4 | Suitable when using swap, a larger instance, or a smaller local model. |
| Remote | API key only | No local model memory cost; uses a free-tier external endpoint. |
| Mock | No model, no API key | Development and tests only; deterministic canned responses. |

> The backend is no longer blocked on local model RAM. On a low-RAM host, the LLM engine falls through from local to remote to mock based on availability and configured priority.

#### 0.4 Process Management
- Create a **systemd service file** (`/etc/systemd/system/alldoing.service`) for the FastAPI server.
- Create a **cron job** for daily restart at a fixed downtime (e.g., 03:00 UTC):
  ```
  0 3 * * * systemctl restart alldoing
  ```
- Add a health-check cron (every 5 min) that restarts if the process is down.

### Acceptance Criteria
- [ ] EC2 instance running and accessible via SSH.
- [ ] At least one provider (local, remote, or mock) responds to a test prompt.
- [ ] systemd service starts the backend on boot.
- [ ] Cron restarts happen at scheduled time.

---

## Phase 1 — Core Backend (FastAPI)

### Objectives
- Stand up the HTTP server with query submission and result polling endpoints.
- Implement the async task queue.

### Planned File Structure
```
apps/backend/
├── main.py              # FastAPI app, endpoint definitions
├── config.py            # Environment variables, model paths, Google creds path
├── models/
│   └── schemas.py       # Pydantic models for request/response
├── pipeline/
│   ├── __init__.py
│   ├── router.py        # Query routing and task lifecycle
│   └── task_store.py    # In-memory task state (dict-based, single user)
└── requirements.txt
```

### Tasks

#### 1.1 FastAPI Application (`main.py`)
- `GET /query?q=<user_query>` — Accepts a natural language query.
  - Generates a unique `task_id` (UUID).
  - Spawns an async task for the pipeline.
  - Returns `{ "task_id": "...", "status": "accepted" }`.
- `GET /status/<task_id>` — Polls for task result.
  - Returns `{ "task_id": "...", "status": "processing|completed|failed", "result": {...} }`.
- `GET /cohorts` — Lists all cohorts from the master catalogue.
- `GET /cohort/<name>` — Returns entries for a specific cohort.
- `GET /health` — Health check endpoint.

#### 1.2 Task Store (`pipeline/task_store.py`)
- Simple in-memory dict: `task_id → { status, query, result, created_at, updated_at }`.
- Since there is only 1 user, no persistence needed across restarts (tasks are ephemeral).
- Cleanup: remove completed tasks older than 1 hour.

#### 1.3 Async Task Runner (`pipeline/router.py`)
- On query receipt, `asyncio.create_task(run_pipeline(task_id, query))`.
- The pipeline function updates the task store at each stage.
- Errors are caught and stored as `status: "failed"` with error details.

#### 1.4 CORS Configuration
- Allow requests from the GitHub Pages domain.

### Acceptance Criteria
- [ ] `GET /query?q=hello` returns a task_id.
- [ ] `GET /status/<id>` returns the task's current state.
- [ ] Backend starts with `python -m uvicorn apps.backend.main:app`.
- [ ] CORS allows GitHub Pages origin.

---

## Phase 2 — LLM Integration & Structured Pipeline

### Objectives
- Integrate the provider-based LLM engine.
- Build the multi-stage pipeline with minimal token usage per call.
- Enforce structured JSON output from the LLM with validation and retry.

### Planned File Structure
```
apps/backend/
├── llm/
│   ├── __init__.py
│   ├── engine.py        # Multi-provider engine: local, remote, mock
│   ├── prompts.py       # All prompt templates (kept short, structured)
│   └── output_parser.py # Multi-strategy JSON extraction and schema validation
├── pipeline/
│   ├── stages.py        # Pipeline stage definitions
│   └── executor.py      # Stage orchestration
```

### Tasks

#### 2.1 LLM Engine (`llm/engine.py`)
- Implement a singleton `LLMEngine` that tries providers in priority order.
- Providers:
  - **LocalProvider** — GGUF via llama-cpp-python with RAM-aware load checks.
  - **RemoteProvider** — OpenAI-compatible HTTP API for free-tier hosted inference.
  - **MockProvider** — deterministic canned responses for development and tests.
- Expose:
  - `generate(prompt: str, max_tokens: int, json_mode: bool) -> str`
  - `generate_structured(prompt: str, schema: type[BaseModel], max_retries: int = 1) -> BaseModel | None`

#### 2.2 Prompt Templates (`llm/prompts.py`)
Each prompt is a focused, minimal template. The key principle: **never send more context than the current stage needs.**

**Stage 1 — Parse** (input: raw user query, output: structured intent)
```
System: You extract structured intent from user queries. Respond in JSON only.
User: {query}
Expected output: {
  "cohort_name": "twitter_ai_agents",
  "cohort_description": "Latest Twitter posts about AI agents",
  "action_type": "web_fetch",
  "action_params": { "source": "twitter", "keyword": "ai agents" },
  "summary": "Fetch latest Twitter posts related to AI agents"
}
```

**Stage 2 — Plan** (input: parsed intent, output: execution steps)
```
System: You are a task planner. Given this intent, output a list of execution steps in JSON.
User: {parsed_intent_json}
Expected output: {
  "steps": [
    { "action": "search_web", "params": { "query": "twitter ai agents latest posts", "max_results": 10 } },
    { "action": "extract_content", "params": { "urls": ["..."] } },
    { "action": "summarize", "params": { "content": "..." } }
  ]
}
```

**Stage 3 — Execute** (handled by action engine, may invoke LLM for summarization/transformation)

**Stage 4 — Store** (format data for DB insertion, may use LLM to normalize)

#### 2.3 Output Parser (`llm/output_parser.py`)
- Extract JSON using layered recovery:
  1. direct parse
  2. markdown code block extraction
  3. balanced brace/bracket matching
  4. greedy repair for truncated JSON
  5. key-value regex fallback
- Validate extracted payloads against Pydantic schemas.
- Auto-correct common issues:
  - missing strings -> `""`
  - missing lists -> `[]`
  - missing dicts -> `{}`
  - numeric values in string fields -> `str(value)`
- Retry once with a corrective prompt if parsing or validation fails.

#### 2.4 Pipeline Executor (`pipeline/executor.py`)
- Orchestrates stages sequentially: Parse → Plan → Execute → Store.
- Each stage receives only its required input (not the full conversation).
- Updates task store after each stage.
- If the LLM determines it needs to spawn sub-tasks (e.g., process 10 URLs), it generates a batch plan, and the executor processes them.

### Design Principle: Token Efficiency

| Strategy | Description |
|----------|------------|
| **Stage isolation** | Each LLM call gets only the data it needs, not the full history. |
| **JSON-only output** | Prompts require JSON-only output and the parser repairs common model mistakes. |
| **Low max_tokens** | 256-512 per call. Larger only when summarizing content. |
| **Pre-processing** | Web content converted to markdown and truncated before LLM sees it. |
| **No chat memory** | Pipeline stages are stateless; no conversation history accumulates. |

### Acceptance Criteria
- [ ] LLM engine responds via local, remote, or mock provider.
- [ ] Parse stage extracts correct JSON from "Create a bot which fetches me latest twitter posts related to ai agents".
- [ ] Pipeline runs end-to-end from query to structured output.
- [ ] Parser tests cover malformed JSON, truncation, wrong field types, and missing fields.
- [ ] Each LLM call uses < 1000 input tokens.

---

## Phase 3 — Web Content Extraction (Adapter Architecture)

### Objectives
- Convert arbitrary web pages into clean, token-efficient markdown.
- Support site-specific extraction strategies for brittle platforms such as Twitter/X and Reddit.
- Preserve both article-style content and list/feed-style content.

### Planned File Structure
```
apps/backend/
├── extractor/
│   ├── __init__.py
│   ├── fetcher.py       # HTTP fetching with retry, rate limiting
│   ├── cleaner.py       # Adapter orchestrator
│   └── cache.py         # Simple file/dict cache for extracted content
│   └── adapters/
│       ├── base.py      # BaseAdapter + ExtractionResult
│       ├── generic.py   # readability-lxml + markdownify + BeautifulSoup fallback
│       ├── twitter.py   # syndication + Nitter + search fallback
│       ├── reddit.py    # Reddit .json extraction
│       └── registry.py  # Domain → adapter mapping
```

### Tasks

#### 3.1 HTML Fetcher (`extractor/fetcher.py`)
- Use `httpx` (async) with sensible timeouts and browser-like headers.
- Handle redirects, rate limiting (429), and retries with backoff.
- Expose both raw text fetching and response-level access for adapters that need status codes or JSON payloads.

#### 3.2 Adapter Orchestrator (`extractor/cleaner.py`)
- `cleaner.py` chooses an adapter via `registry.get_adapter(url)`.
- The adapter returns a normalized `ExtractionResult`:
  - `content` for article-style pages
  - `items` for feed/list/search-result pages
  - `metadata` for platform-specific context

#### 3.3 Generic Adapter (`extractor/adapters/generic.py`)
Default markdowner-style flow:

1. **Parse** HTML with `lxml` or `BeautifulSoup`.
2. **Strip** `<script>`, `<style>`, `<iframe>`, `<noscript>`, `<nav>`, `<footer>` tags.
3. **Extract** main content using `readability-lxml` (Python port of Mozilla Readability).
4. **Fallback** to BeautifulSoup body extraction if readability produces little or empty text.
5. **Convert** to markdown using `markdownify` (Python port of Turndown).
6. **Truncate** at sentence boundaries instead of cutting mid-sentence.
7. **Detect feed/list pages** and populate `items` instead of flattening everything into a single blob.

#### 3.4 Site-Specific Adapters
- **Twitter/X adapter**:
  - try syndication endpoints
  - try configured Nitter instances
  - try search-based fallback
  - return a graceful error result if all access methods fail
- **Reddit adapter**:
  - append `.json`
  - parse posts/comments from Reddit's JSON payload
  - return list-style items

#### 3.5 Content Cache (`extractor/cache.py`)
- In-memory dict with TTL (1 hour default).
- Key: URL hash, Value: extracted result + timestamp.
- Prevents re-fetching the same URL within the TTL window.

### Acceptance Criteria
- [ ] Given a URL, returns a normalized `ExtractionResult`.
- [ ] Scripts, styles, nav, and ads are stripped.
- [ ] Output is ≤ 2000 chars when using `content`, truncated at sentence boundaries.
- [ ] Feed/list pages are represented as `items`.
- [ ] Twitter/X failures return graceful error results instead of crashing.
- [ ] Reddit URLs extract structured items through the `.json` endpoint.
- [ ] Cache prevents duplicate fetches.

---

## Phase 4 — Google Sheets DB Layer

### Objectives
- Use Google Sheets as the persistent database.
- Implement a clean CRUD interface that the rest of the system calls.

### Planned File Structure
```
apps/backend/
├── db/
│   ├── __init__.py
│   ├── sheets.py        # Google Sheets CRUD operations
│   ├── catalogue.py     # Master catalogue management
│   └── models.py        # DB record schemas (Pydantic)
├── credentials/
│   └── .gitkeep         # Service account JSON goes here (gitignored)
```

### Tasks

#### 4.1 Google Cloud Setup (Manual, Documented)
- Create a Google Cloud project.
- Enable Google Sheets API and Google Drive API.
- Create a service account, download JSON key.
- Share the master spreadsheet with the service account email.

#### 4.2 Master Catalogue (`db/catalogue.py`)

The **master spreadsheet** has a sheet called `_catalogue` with columns:

| Column | Description |
|--------|------------|
| `cohort_name` | Unique identifier (snake_case) |
| `cohort_description` | Human-readable description |
| `action_type` | Type of action (web_fetch, api_call, transform, etc.) |
| `action_params` | JSON string of action parameters |
| `created_at` | ISO timestamp |
| `last_run` | ISO timestamp of last action execution |
| `sheet_name` | Name of the cohort's data sheet |
| `entry_count` | Number of entries in the cohort |

Operations:
- `list_cohorts() → List[Cohort]`
- `get_cohort(name: str) → Cohort`
- `create_cohort(cohort: Cohort) → None` (also creates the cohort's sheet)
- `update_cohort(name: str, updates: dict) → None`
- `delete_cohort(name: str) → None` (also deletes the cohort's sheet)

#### 4.3 Cohort Data Sheets (`db/sheets.py`)

Each cohort gets its own sheet in the spreadsheet. Common columns:

| Column | Description |
|--------|------------|
| `entry_id` | Auto-incrementing ID |
| `content` | The main text content |
| `source` | URL or origin of the data |
| `metadata` | JSON string of extra fields |
| `created_at` | ISO timestamp |

Operations:
- `add_entries(cohort_name: str, entries: List[Entry]) → None`
- `get_entries(cohort_name: str, limit: int, offset: int) → List[Entry]`
- `clear_entries(cohort_name: str) → None`

#### 4.4 Rate Limiting
- Google Sheets API has quotas (60 requests/min for reads, 60 for writes).
- Implement a simple rate limiter (token bucket or sleep-based) in the sheets client.
- Batch writes where possible (append multiple rows in one call).

### Acceptance Criteria
- [ ] Can create a cohort and see it in Google Sheets.
- [ ] Can add entries to a cohort sheet.
- [ ] Can list all cohorts from the catalogue.
- [ ] Rate limiting prevents API quota errors.

---

## Phase 5 — Cohort & Action System

### Objectives
- Connect the LLM pipeline to the action engine and DB.
- Implement the full flow: query → cohort creation → action execution → data storage.

### Planned File Structure
```
apps/backend/
├── actions/
│   ├── __init__.py
│   ├── registry.py      # Action type registry
│   ├── base.py          # Base action class (abstract)
│   ├── web_fetch.py     # Fetch web content action
│   ├── api_call.py      # Generic API call action
│   └── transform.py     # Data transformation action
```

### Tasks

#### 5.1 Action Registry (`actions/registry.py`)
- Maps `action_type` strings to action handler classes.
- New actions are registered by adding a class, no other changes needed.
- Pattern inspired by agent-orchestrator's plugin architecture.

```python
# Conceptual (not actual code):
REGISTRY = {
    "web_fetch": WebFetchAction,
    "api_call": ApiCallAction,
    "transform": TransformAction,
}
```

#### 5.2 Base Action (`actions/base.py`)
- Abstract class with `async execute(params: dict) → List[Entry]`.
- Handles common concerns: logging, error wrapping, timeout.

#### 5.3 Web Fetch Action (`actions/web_fetch.py`)
- Takes `{ source, keyword, max_results }`.
- Uses the web extractor (Phase 3) to fetch and clean content.
- For sources like Twitter: builds search URL, fetches results, extracts each post.
- Returns structured entries ready for DB insertion.

#### 5.4 LLM-Assisted Processing
- After raw data is fetched, the LLM may be invoked to:
  - **Summarize** long content.
  - **Extract** specific fields (e.g., post author, date, engagement).
  - **Filter** irrelevant results.
- Each of these is a small, focused LLM call (< 500 tokens input).

#### 5.5 Pipeline Integration
- The executor (Phase 2) calls into the action system during the Execute stage.
- After execution, the Store stage writes entries to the cohort's Google Sheet.
- The catalogue is updated with `last_run` and `entry_count`.

#### 5.6 Follow-Up / Chained Actions
- The LLM may determine that a query requires multiple actions (e.g., fetch from 3 sources, then merge).
- The Plan stage outputs these as sequential steps.
- The executor processes them in order, feeding output of one into the next.

### Acceptance Criteria
- [ ] "Create a bot which fetches me latest twitter posts related to ai agents" creates:
  - A `twitter_ai_agents` cohort in the catalogue.
  - A `twitter_ai_agents` sheet with fetched/summarized posts.
- [ ] New action types can be added by creating a single new file.
- [ ] Chained actions execute in sequence.

---

## Phase 6 — Frontend (GitHub Pages)

> **Note**: UI details are deferred for later discussion. This phase provides the minimal viable frontend.

### Objectives
- Static site hosted on GitHub Pages.
- Allows query submission and result viewing.

### Planned File Structure
```
apps/frontend/
├── index.html           # Main page
├── css/
│   └── style.css
├── js/
│   ├── app.js           # Main application logic
│   ├── api.js           # Backend API client
│   └── config.js        # Backend URL configuration
└── assets/
```

### Tasks

#### 6.1 Core UI Components
- **Query input**: Text field + submit button.
- **Status display**: Shows task status (processing/completed/failed) with polling.
- **Cohort browser**: Lists all cohorts, click to view entries.
- **Entry viewer**: Shows entries for a selected cohort in a table/card layout.

#### 6.2 API Client (`js/api.js`)
- `submitQuery(query)` → calls `GET /query?q=...`
- `pollStatus(taskId)` → calls `GET /status/<id>` every 2 seconds.
- `listCohorts()` → calls `GET /cohorts`.
- `getCohortEntries(name)` → calls `GET /cohort/<name>`.

#### 6.3 Deployment
- Push `apps/frontend/` to a `gh-pages` branch or configure GitHub Pages from the `apps/frontend/` directory.
- Configure the backend URL in `config.js`.

### Acceptance Criteria
- [ ] Page loads on GitHub Pages.
- [ ] Can submit a query and see the result.
- [ ] Can browse cohorts and their entries.

---

## Phase 7 — Reliability & Operations

### Objectives
- Ensure the system runs reliably 24/7 for a single user.
- Handle failures gracefully.

### Tasks

#### 7.1 systemd Service
- Service file with `Restart=always` and `RestartSec=10`.
- `WorkingDirectory` and `ExecStart` pointing to the backend.
- Logging to journald.

#### 7.2 Scheduled Restart
- Cron job: `0 3 * * * systemctl restart alldoing`
- Purpose: clear accumulated memory, reset any stuck states.

#### 7.3 Health Monitoring
- Cron job every 5 minutes: curl the `/health` endpoint, restart if unresponsive.
- Simple bash script:
  ```bash
  curl -sf http://localhost:8000/health || systemctl restart alldoing
  ```

#### 7.4 Logging
- Python `logging` module with rotating file handler.
- Log levels: INFO for pipeline stages, WARNING for retries, ERROR for failures.
- Log each LLM call with input token count and latency.

#### 7.5 Error Recovery
- Failed pipeline tasks: store error in task store, log, move on.
- Google Sheets API failures: retry with backoff (3 attempts).
- LLM failures: retry once with simplified prompt, then fail the task.
- Web fetch failures: skip the URL, log, continue with remaining URLs.

#### 7.6 Rate Limiting for External APIs
- Google Sheets: token bucket, 50 req/min.
- Web fetching: max 1 request/second per domain.
- LLM: sequential processing (single user, no concurrency needed).

### Acceptance Criteria
- [ ] Backend survives a `kill -9` and restarts automatically.
- [ ] Daily restart happens at scheduled time.
- [ ] Health check detects and recovers from a hung process.
- [ ] Logs are rotated and don't fill disk.

---

## End-to-End Example Walkthrough

**User query**: `"Create a bot which fetches me latest twitter posts related to ai agents"`

### Step 1: Query Received
```
GET /query?q=Create+a+bot+which+fetches+me+latest+twitter+posts+related+to+ai+agents
→ { "task_id": "abc-123", "status": "accepted" }
```

### Step 2: Parse Stage (LLM Call #1)
- **Input** (< 200 tokens): System prompt + user query.
- **Output**:
  ```json
  {
    "cohort_name": "twitter_ai_agents",
    "cohort_description": "Latest Twitter posts about AI agents",
    "action_type": "web_fetch",
    "action_params": { "source": "twitter", "keyword": "ai agents", "max_results": 10 }
  }
  ```

### Step 3: Plan Stage (LLM Call #2)
- **Input** (< 300 tokens): System prompt + parsed intent JSON.
- **Output**:
  ```json
  {
    "steps": [
      { "action": "search_web", "params": { "query": "site:twitter.com ai agents", "max_results": 10 } },
      { "action": "extract_content", "params": { "urls": ["<from search results>"] } },
      { "action": "summarize_entries", "params": { "max_length": 200 } }
    ]
  }
  ```

### Step 4: Execute Stage
1. **Web search**: Fetch search results for "site:twitter.com ai agents".
2. **Content extraction**: For each URL, run the markdowner pipeline → clean markdown.
3. **LLM Call #3** (per entry, < 500 tokens each): Summarize/extract structured fields from markdown.

### Step 5: Store Stage
1. **Create cohort**: Add row to `_catalogue` sheet.
2. **Create sheet**: New sheet `twitter_ai_agents` in the spreadsheet.
3. **Add entries**: Batch-write all extracted/summarized posts.

### Step 6: Result Ready
```
GET /status/abc-123
→ {
    "task_id": "abc-123",
    "status": "completed",
    "result": {
      "cohort_name": "twitter_ai_agents",
      "entries_added": 8,
      "message": "Created cohort 'twitter_ai_agents' with 8 Twitter posts about AI agents."
    }
  }
```

---

## Open Questions & Future Work

| # | Question | Impact | Decision Needed By |
|---|----------|--------|-------------------|
| 1 | **Resolved**: LLM engine now supports local, remote, and mock providers with RAM-aware local loading and fallback ordering. | Phase 0 | Implemented |
| 2 | **Resolved**: Twitter access now uses layered fallbacks (syndication, Nitter, search fallback) with graceful error results. | Phase 3/5 | Implemented |
| 3 | **Frontend framework**? Plain HTML/JS vs lightweight framework (Alpine.js, Preact). | Phase 6 | Before Phase 6 |
| 4 | **Authentication**? Currently no auth. Backend is open. Options: (a) API key in query param, (b) IP whitelisting, (c) none (security through obscurity + single user). | Phase 1 | Before production deployment |
| 5 | **Recurring actions**? Should cohorts auto-refresh on a schedule (e.g., fetch new tweets daily)? | Phase 5 | Future enhancement |
| 6 | **Multi-spreadsheet**? If a single spreadsheet hits sheet limits (200 sheets), need a strategy. | Phase 4 | Future enhancement |

---

## Implementation Order & Dependencies

```
Phase 0 (Infra)
    │
    ▼
Phase 1 (Backend)  ──────────────────┐
    │                                 │
    ▼                                 ▼
Phase 2 (LLM Pipeline)    Phase 4 (Google Sheets DB)
    │                                 │
    ▼                                 │
Phase 3 (Web Extractor)              │
    │                                 │
    └──────────┬──────────────────────┘
               ▼
         Phase 5 (Cohort & Action System)
               │
               ▼
         Phase 6 (Frontend)
               │
               ▼
         Phase 7 (Reliability)
```

- Phases 2 and 4 can be developed **in parallel** after Phase 1.
- Phase 3 can be developed in parallel with Phase 4.
- Phase 5 requires Phases 2, 3, and 4 to be complete.
- Phase 6 can begin once Phase 1 endpoints are defined (even before full pipeline works).
- Phase 7 should be applied incrementally throughout but finalized last.
