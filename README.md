# all-doing-bot

`all-doing-bot` is a personal, always-on LLM-powered automation bot that turns natural-language requests into structured pipelines. A query is parsed into a cohort and an action, executed through a staged backend pipeline, and stored in Google Sheets.

## Architecture

```text
GitHub Pages / static frontend
        |
        v
FastAPI backend
Parse -> Plan -> Execute -> Store
        |
        v
Google Sheets / Drive
```

The backend now supports three LLM runtime modes:

- `local`: GGUF model through `llama-cpp-python`
- `remote`: free-tier OpenAI-compatible provider
- `mock`: deterministic canned responses for development and tests

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

Run tests:

```bash
python -m pytest tests -q
```

## Environment variables

For real LLM output and real persistence, configure the backend via a `.env` file (copy from `.env.example`).

| Variable | Required | Description |
|----------|----------|-------------|
| `REMOTE_LLM_API_KEY` | For real LLM | API key for remote OpenAI-compatible provider. If unset, the backend may use mock or local-only. |
| `REMOTE_LLM_BASE_URL` | No | Base URL for remote LLM API (default: `https://api.groq.com/openai/v1`). |
| `REMOTE_LLM_MODEL` | No | Model name for remote API (default: `llama-3.1-8b-instant`). |
| `LLM_PROVIDER_PRIORITY` | No | Comma-separated provider order: `local`, `remote`, `mock` (default: `local,remote,mock`). |
| `GOOGLE_CREDS_PATH` | For real persistence | Path to Google service account JSON. If unset, backend uses in-memory fake persistence. |
| `SPREADSHEET_ID` | For real persistence | Google Sheet ID for catalogue and cohort data. |
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
- `REMOTE_LLM_API_KEY=<your-groq-key>` (or another provider key).

Backend endpoints currently have no authentication. For production, consider adding API key or OAuth verification if the app is public.

## Documentation

- [AGENTS.md](./AGENTS.md): primary repo-level instructions for coding agents
- [docs/implementation-plan.md](./docs/implementation-plan.md): phased implementation plan
- [docs/architecture/overview.md](./docs/architecture/overview.md): monorepo and system structure overview
- [docs/deployment/aws-credentials-and-deploy.md](./docs/deployment/aws-credentials-and-deploy.md): AWS credentials for deploy agents, IAM roles, and EC2 setup/update
- [docs/instructions/backend-workflow.md](./docs/instructions/backend-workflow.md): backend-specific workflow guidance
- [docs/instructions/frontend-workflow.md](./docs/instructions/frontend-workflow.md): frontend-specific workflow guidance

## Status

Active implementation is underway. The repo now uses a monorepo-style layout with `apps/backend` and `apps/frontend`, while tests remain at the repo root.

## License

See [LICENSE](./LICENSE).
