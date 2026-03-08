# Backend Workflow

Use this guide when changing code under `apps/backend/`.

## Package and imports

- The backend package path is `apps.backend`.
- New imports should use `apps.backend.*`.
- Keep tests runnable from the repo root.

## Main backend areas

- `apps/backend/main.py`: FastAPI entrypoint and HTTP routes
- `apps/backend/pipeline/`: orchestration and task flow
- `apps/backend/llm/`: providers, prompts, parsing
- `apps/backend/extractor/`: adapter-based web extraction
- `apps/backend/db/`: Google Sheets and fake DB backends
- `apps/backend/actions/`: action registry and implementations

## Editing rules

- Preserve the `Parse -> Plan -> Execute -> Store` flow.
- Do not move DB logic into routes or actions outside `apps/backend/db/`.
- Keep web extraction logic inside adapters instead of scattering site-specific parsing.
- Keep LLM logic mockable; do not require a local model for tests.

## Configuration

Backend configuration is via environment variables. See the [Environment variables](../../README.md#environment-variables) section in the repo README and `.env.example` for real LLM and Google Sheets persistence.

## Run and test

Install dependencies:

```bash
python -m pip install -r apps/backend/requirements.txt
```

Run backend:

```bash
python -m uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000
```

Run backend-related tests:

```bash
python -m pytest tests -q
```

## High-signal checks after edits

- imports still resolve through `apps.backend.*`
- mocked tests still pass
- no stale references to old `backend/` root paths remain
