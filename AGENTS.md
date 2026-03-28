# AGENTS.md

Repo-level instructions for coding agents working on `all-doing-bot`.

Read these first:

- [README.md](./README.md)
- [docs/implementation-plan.md](./docs/implementation-plan.md)
- [docs/architecture/overview.md](./docs/architecture/overview.md)
- [docs/instructions/backend-workflow.md](./docs/instructions/backend-workflow.md) when changing backend code
- [docs/instructions/frontend-workflow.md](./docs/instructions/frontend-workflow.md) when changing frontend code

## Production backend — SSH update (mandatory)

After **any** change under `apps/backend/` (or anything that affects the running FastAPI service on EC2), the agent **must** deploy that code to the production host **over SSH** in the same session whenever the environment has network access and SSH credentials (or can run non-interactively). Leaving `main` updated on GitHub **without** updating the EC2 process is incomplete.

1. **Push** `main` first (see workspace push rules).
2. **Run the remote update** (same steps as `.github/workflows/deploy-ec2.yml`):
   - **Windows (PowerShell):**  
     `powershell -NoProfile -ExecutionPolicy Bypass -File apps/backend/deploy/Invoke-Ec2BackendUpdate.ps1`  
     with `EC2_HOST` set (and `EC2_USER` / `SSH_KEY` if not default). The script pipes `ec2-pull-restart.sh` to `ssh user@host bash -s`.
   - **macOS / Linux / Git Bash:**  
     `EC2_HOST=... EC2_USER=ubuntu ./apps/backend/deploy/ec2-ssh-pull-restart-from-local.sh`
3. **If SSH is not possible** (no key in this environment, headless CI without secrets): state that explicitly in the reply and tell the human to run one of the commands above or **Actions → Deploy backend (EC2) → Run workflow** (requires repo secrets `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`).

Reference: [apps/backend/deploy/ec2-runbook.md](./apps/backend/deploy/ec2-runbook.md), [docs/deployment/aws-credentials-and-deploy.md](./docs/deployment/aws-credentials-and-deploy.md).

## Monorepo Layout

```text
all-doing-bot/
├── AGENTS.md
├── README.md
├── apps/
│   ├── backend/
│   └── frontend/
├── docs/
│   ├── architecture/
│   ├── implementation-plan.md
│   └── instructions/
└── tests/
```

## Core Rules

### Structured pipeline only

Every user request must continue to flow through:

`Parse -> Plan -> Execute -> Store`

Do not bypass the pipeline by writing directly from request handlers into storage.

### Backend import convention

The backend now lives under `apps/backend`, and Python imports should use the package path:

- `apps.backend.*`

Do not introduce new `backend.*` imports.

### LLM runtime model

The backend supports three provider modes:

- `local`
- `remote`
- `mock`

All LLM-facing code must remain testable without a downloaded model or live remote provider.

### Extraction architecture

Web extraction must go through the adapter system in `apps/backend/extractor/adapters/`.

- generic behavior belongs in `GenericAdapter`
- site-specific behavior belongs in dedicated adapters
- action and pipeline code should consume normalized extraction results, not site-specific parsing logic

### Data boundaries

- Use Pydantic models for cross-module payloads.
- Keep Google Sheets access inside `apps/backend/db/`.
- Keep configuration in `apps/backend/config.py` via environment variables.

### Async and safety

- Do not block the event loop for I/O work.
- Use logging, not `print()`.
- Catch failures at stage boundaries and return structured failure states.
- Do not log secrets, raw credentials, or full sensitive prompts.

## Testing Expectations

Run tests from the repo root:

```bash
python -m pytest tests -q
```

Use mocks/fakes for:

- LLM providers
- HTTP extraction paths
- Google Sheets

Important testing dependencies already justified in the repo:

- `psutil` for RAM-aware provider selection
- `respx` for mocked `httpx` behavior

## Local Commands

Install backend dependencies:

```bash
python -m pip install -r apps/backend/requirements.txt
```

Run backend:

```bash
python -m uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000
```

Run frontend locally:

```bash
cd apps/frontend
python -m http.server 3000
```

## Documentation Ownership

- `AGENTS.md`: repo-wide agent rules
- `docs/implementation-plan.md`: phased project plan
- `docs/architecture/overview.md`: structure and system map
- `docs/instructions/backend-workflow.md`: backend editing/testing guidance
- `docs/instructions/frontend-workflow.md`: frontend editing/testing guidance
