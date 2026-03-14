# all-doing-bot

`all-doing-bot` is a personal, always-on LLM-powered automation bot that turns natural-language requests into structured pipelines. A query is parsed into a cohort and an action, executed through a staged backend pipeline, and stored in Google Sheets.

## Architecture

```text
GitHub Pages / static frontend
        |
        v
FastAPI backend (optional: Redis queue + worker)
Parse -> Plan -> Execute -> Store
        |
        v
Google Sheets / Drive
```

- **Queue-first runtime (default)**: Orchestrator dispatches step jobs through the queue abstraction and collects step results before Store.
- **With REDIS_URL**: External worker process(es) execute actions from Redis; run state and step results are durable.
- **Without Redis**: Queue path remains primary using inline worker-compatible execution in-process.
- **Legacy fallback**: Optional emergency rollback to old in-process executor with `ORCHESTRATOR_LEGACY_FALLBACK_ENABLED=true`.

The backend supports multiple LLM runtime modes:

- `ollama` (default): local Qwen model (e.g. `qwen3.5:4b`)
- `local`: GGUF model through `llama-cpp-python`
- `mock`: deterministic canned responses for development and tests
- `remote`: optional OpenAI-compatible provider (opt-in)

## Repository Layout

```text
all-doing-bot/
├── AGENTS.md
├── README.md
├── LICENSE
├── apps/
│   ├── backend/
│   └── frontend/
├── docs/
│   ├── implementation-plan.md
│   ├── architecture/
│   └── instructions/
└── tests/
```

## Quick Start

Install backend dependencies from the repo root:

```bash
python -m pip install -r apps/backend/requirements.txt
```

Run the backend from the repo root:

```bash
python -m uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000
```

Run the frontend locally:

```bash
cd apps/frontend
python -m http.server 3000
```

Run the worker (when using Redis):

```bash
REDIS_URL=redis://localhost:6379/0 python -m apps.backend.workers.run_worker
```

Run tests:

```bash
python -m pytest tests -q
```

Regressive checks (no test files): start backend, then `curl http://localhost:8000/health`, `curl "http://localhost:8000/query?q=..."`, and poll `GET /status/<task_id>` until completed.

## Environment variables

For real LLM output and real persistence, configure the backend via a `.env` file (copy from `.env.example`).

| Variable | Required | Description |
|----------|----------|-------------|
| `REMOTE_LLM_API_KEY` | Optional | API key for remote OpenAI-compatible provider (opt-in only). Default runtime does not require this. |
| `REMOTE_LLM_BASE_URL` | No | Base URL for remote LLM API (default: `https://api.groq.com/openai/v1`). |
| `REMOTE_LLM_MODEL` | No | Model name for remote API (default: `llama-3.1-8b-instant`). |
| `LLM_PROVIDER_PRIORITY` | No | Comma-separated provider order (default: `ollama,local,mock` for no-key local Qwen runtime). |
| `GOOGLE_CREDS_PATH` | For real persistence | Path to Google service account JSON. If unset, backend uses in-memory fake persistence. |
| `SPREADSHEET_ID` | For real persistence | Google Sheet ID for catalogue and cohort data. |
| `CHAT_WEB_SEARCH_ENABLED` | No | Set to `true` to enable web search for short search-like queries (requires SearXNG). Default: disabled. |
| `REDIS_URL` | For queue | When set, pipeline enqueues steps to Redis; run a worker to process them (`python -m apps.backend.workers.run_worker`). Enables durable run state. |
| `ORCHESTRATOR_LEGACY_FALLBACK_ENABLED` | No | Default `false`. If `true`, fall back to legacy in-process execution only when queue path fails. |
| `CORS_ALLOW_ORIGINS` | No | Comma-separated origins for CORS (e.g. `http://localhost:3000`). |
| `HOST` | No | Bind host (default: `0.0.0.0`). |
| `PORT` | No | Bind port (default: `8000`). |

Optional for local GGUF: `MODEL_PATH` — path to a local model file when using the `local` provider.

## Before deploying (frontend + backend)

**Frontend** (`apps/frontend/index.html`): Set before going live:
- `window.BACKEND_URL` — your backend host (e.g. EC2 or Render URL).
- `window.GOOGLE_CLIENT_ID` — Google OAuth client ID; see [docs/deployment/google-oauth-github-pages.md](docs/deployment/google-oauth-github-pages.md) (fixes “Error 401: invalid_client”).

The dev bypass button is shown only on localhost; it is hidden in production.

**Backend** (env on EC2/Render/etc.):
- `CORS_ALLOW_ORIGINS=https://your-github-pages-url.github.io` (comma-separated if multiple).
- Local-first default: keep `OLLAMA_MODEL=qwen3.5:4b` and `LLM_PROVIDER_PRIORITY=ollama,local,mock`.
- `REMOTE_LLM_API_KEY` is optional only if you explicitly want remote fallback.

Backend endpoints currently have no authentication. For production, consider adding API key or OAuth verification if the app is public.

## Documentation

- [docs/PRODUCT.md](./docs/PRODUCT.md): **product roundup** — what it is, what it can do, web search status, comparison with Open Claw, queue/worker mode
- [AGENTS.md](./AGENTS.md): primary repo-level instructions for coding agents
- [docs/implementation-plan.md](./docs/implementation-plan.md): phased implementation plan
- [docs/architecture/overview.md](./docs/architecture/overview.md): monorepo and system structure overview
- [docs/architecture/action-contracts.md](./docs/architecture/action-contracts.md): action contracts, error taxonomy, idempotency
- [docs/architecture/durable-checkpoints.md](./docs/architecture/durable-checkpoints.md): durable run state and checkpoints (Redis)
- [docs/deployment/single-ec2-hardening.md](./docs/deployment/single-ec2-hardening.md): single EC2 with Docker Compose, Caddy, Redis, worker, TLS, backup
- [docs/deployment/aws-credentials-and-deploy.md](./docs/deployment/aws-credentials-and-deploy.md): AWS credentials for deploy agents, IAM roles, and EC2 setup/update
- [docs/instructions/backend-workflow.md](./docs/instructions/backend-workflow.md): backend-specific workflow guidance
- [docs/instructions/frontend-workflow.md](./docs/instructions/frontend-workflow.md): frontend-specific workflow guidance

## Status

Active implementation. The repo uses a monorepo layout with `apps/backend` and `apps/frontend`. OpenClaw-style runtime is now queue-first with action contracts, telemetry, browser automation capability, dead-letter handling, and durable run checkpoints.

## License

See [LICENSE](./LICENSE).
