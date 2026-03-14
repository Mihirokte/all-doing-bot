# all-doing-bot — Product Overview

> **Status**: Active implementation. Web search is **disabled** in the chat path (SearXNG dependency removed from short-query flow). Pipeline and full product capabilities are documented below.

---

## What is all-doing-bot?

**all-doing-bot** is a **personal, always-on LLM-powered automation bot** that turns natural-language requests into structured pipelines. You send a query → the system parses it into a **cohort** (named collection) and an **action** (task type) → runs a staged backend pipeline → stores results in **Google Sheets** (or in-memory when not configured).

It is designed for **one active user**, with minimal token usage, extensible actions, and a single web frontend (GitHub Pages or local static).

---

## Architecture (one sentence)

**GitHub Pages / static frontend → FastAPI backend (Parse → Plan → Execute → Store) → Google Sheets / Drive.** Optionally: **Redis queue + worker** for decoupled step execution and durable run state.

### OpenClaw-style migration (in place)

- **Action contracts**: Versioned capability schema, error taxonomy, retry policy, idempotency keys (`docs/architecture/action-contracts.md`).
- **Run telemetry**: Structured events (run_accepted, intent_parsed, plan_ready, step_dispatched, step_completed, run_stored, run_failed) and action_exec (latency, outcome, error_code) for correlation and metrics.
- **Queue + worker**: When `REDIS_URL` is set, the orchestrator enqueues step jobs; a separate worker process (`python -m apps.backend.workers.run_worker`) executes actions with retries and dead-letter handling. API stays stateless and polls for step results.
- **Durable checkpoints**: Run metadata (query, parsed, plan, status) and step results stored in Redis for replay and restart (`docs/architecture/durable-checkpoints.md`).
- **Single-EC2 baseline**: Docker Compose (Caddy, API, worker, Redis), TLS, SG, secrets, backup (`docs/deployment/single-ec2-hardening.md`).

---

## What can it do?

### 1. **Short-query chat** (GET `/chat?q=...`)

- **Under ~100 characters**: Treated as “chat”. Single LLM call, no cohort.
- **Web search is disabled**: Queries that look like “search” (e.g. “find latest AI news”) are **no longer** sent to SearXNG or deep search. The backend answers with the LLM only (no live web results).
- When web search was enabled: search-like queries triggered deep retrieval (SearXNG → optional crawl/fetch → rank → answer). That path is off until web search is fixed or re-enabled.

### 2. **Long-query pipeline** (GET `/query?q=...`)

- **Over ~100 characters**: Full pipeline runs in the background.
- **Parse**: LLM extracts structured intent → `cohort_name`, `cohort_description`, `action_type`, `action_params`.
- **Plan**: LLM produces execution steps (e.g. `search_web`, `web_fetch`, `api_call`, `transform`).
- **Execute**: Action engine runs each step (web fetch, API call, transform, or search_web if configured).
- **Store**: Results are written to the cohort’s Google Sheet (or in-memory fake).

So the product can:

- **Create named cohorts** from natural language (“Create a bot that fetches me latest Twitter posts about AI agents” → cohort `twitter_ai_agents`).
- **Run actions**: `web_fetch` (URLs → extracted markdown), `api_call` (generic HTTP), `transform` (data), `search_web` (SearXNG — only when pipeline plans it and SearXNG is available).
- **Persist to Google Sheets**: One sheet per cohort; master catalogue in `_catalogue`.
- **Chat without persistence**: Short questions get a single LLM reply (no web search).

### 3. **APIs**

| Endpoint | Purpose |
|----------|--------|
| `GET /health` | Health check for cron/monitoring |
| `GET /chat?q=...` | Short query → one LLM response (no web search) |
| `GET /query?q=...` | Long query → task_id, pipeline runs async |
| `GET /status/<task_id>` | Poll task status and result |
| `GET /cohorts` | List all cohorts from catalogue |
| `GET /cohort/<name>` | Entries for a cohort |
| `POST /admin/clear-data` | Clear cohorts and in-memory task sessions |

### 4. **LLM runtime**

- **Ollama** (local, OpenAI-compatible): e.g. `qwen3.5:4b`.
- **Local GGUF**: via `llama-cpp-python` (optional).
- **Remote**: OpenAI-compatible API (e.g. Groq).
- **Mock**: Canned responses for tests and when no model/API key is set.

Priority order is configurable via `LLM_PROVIDER_PRIORITY`.

### 5. **Web extraction**

- Adapter-based: generic (Readability + markdownify), plus site-specific (Twitter, Reddit).
- Optional **Cloudflare Browser Rendering** for crawling URLs to full markdown (used when available for fetch/crawl, not for the disabled chat search path).

### 6. **Frontend**

- Static “Intelligence Terminal” UI: query box, chat feed, task status, cohort list, archives overlay, profile (clear data).
- Quick tags for example queries (e.g. “AI NEWS”, “PYTHON TRENDS”).
- Google Sign-In optional; dev bypass on localhost.
- **No frontend changes required for queue/worker mode**; the same API (query, status, chat, cohorts) is used whether the backend runs in-process or with Redis + worker.

---

## What is disabled or optional?

- **Web search in chat**: Disabled. No SearXNG / deep search in the short-query path. Re-enable by setting `CHAT_WEB_SEARCH_ENABLED=true` and ensuring SearXNG is running and configured.
- **SearXNG**: Optional. Only used when pipeline runs a `search_web` step; chat no longer uses it.
- **Google persistence**: Optional. Without `GOOGLE_CREDS_PATH` and spreadsheet config, backend uses in-memory fake storage.
- **Cloudflare crawl**: Optional. Used to enrich fetch/crawl when configured.
- **Queue/worker**: Optional. Set `REDIS_URL` and run the worker for decoupled execution and durable run state; otherwise pipeline runs in-process.

---

## Comparison: all-doing-bot vs Open Claw (open source)

| Aspect | all-doing-bot | Open Claw (github.com/openclaw/openclaw) |
|--------|----------------|------------------------------------------|
| **Language / stack** | Python, FastAPI, static HTML/JS | TypeScript, Node.js ≥22 |
| **Interface** | Single web UI (GitHub Pages / static) | Multi-platform: WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Teams, etc. |
| **Deployment** | Your server (e.g. EC2), one backend + static frontend | Runs on your devices (macOS, Linux, Windows WSL2); install via `npm install -g openclaw` |
| **Core behavior** | Natural language → **structured pipeline** (parse → plan → execute → store) → **cohorts** in Google Sheets | “Digital employee” that can act across apps; speak/listen (macOS/iOS/Android), browse and fill forms, run shell, access files |
| **Memory / context** | Stateless pipeline; no long-lived conversation memory | Remembers context and preferences over time |
| **Data store** | Google Sheets (one sheet per cohort) + in-memory task store | Data on your devices; privacy-focused |
| **LLM** | Multi-provider: Ollama, local GGUF, remote API, mock | Multiple providers (OpenAI, Anthropic, local, etc.) |
| **Web search** | Optional SearXNG in pipeline; **disabled in chat** | Can browse the web and fill forms |
| **Extensibility** | Action registry: add new action types (web_fetch, api_call, transform, search_web) | Plugin/ecosystem for integrations |
| **Scope** | Personal automation bot: “turn requests into cohorts and stored results” | General-purpose personal AI assistant across messaging and tools |

**Summary**: Open Claw is a broad “AI that does things” on your devices and in your messaging apps. all-doing-bot is a focused **pipeline bot** that turns natural language into **named cohorts and stored results** (e.g. in Google Sheets), with a single web UI and no messaging integrations. Both are open source and personal/self-hostable; Open Claw is multi-channel and device-centric; all-doing-bot is pipeline- and spreadsheet-centric with web search currently disabled in chat.

---

## Repo layout (reference)

```text
all-doing-bot/
├── AGENTS.md
├── README.md
├── docs/
│   ├── PRODUCT.md
│   ├── implementation-plan.md
│   ├── architecture/       # overview, action-contracts, durable-checkpoints
│   ├── deployment/        # single-ec2-hardening, aws, google-oauth, etc.
│   └── instructions/
├── apps/
│   ├── backend/            # FastAPI, pipeline, LLM, actions, db, orchestration, workers, telemetry
│   └── frontend/           # Static HTML/JS/CSS
└── tests/
```

---

## Quick start (recap)

- Backend: `python -m uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000`
- Frontend: `cd apps/frontend && python -m http.server 3000`
- Env: see `.env.example` and README for `REMOTE_LLM_*`, `GOOGLE_CREDS_PATH`, `SPREADSHEET_ID`, `CORS_ALLOW_ORIGINS`, etc.

See [README.md](../README.md) and [implementation-plan.md](./implementation-plan.md) for full details.
