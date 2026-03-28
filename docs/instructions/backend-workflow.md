# Backend Workflow

Use this guide when changing code under `apps/backend/`.

## Package and imports

- The backend package path is `apps.backend`.
- New imports should use `apps.backend.*`.
- Keep tests runnable from the repo root.

## Main backend areas

- `apps/backend/main.py`: FastAPI factory and lifespan; HTTP routes under `apps/backend/api/`
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

## Production deploy over SSH (mandatory for this repo)

After backend changes are merged to `main`, the running EC2 service **must** be updated via SSH (or the equivalent GitHub Action), not only by pushing to GitHub.

1. Push `origin main`.
2. From a machine with SSH access to the instance:
   - **PowerShell:** set `EC2_HOST` (and optionally `EC2_USER`, `SSH_KEY`), then run  
     `powershell -NoProfile -ExecutionPolicy Bypass -File apps/backend/deploy/Invoke-Ec2BackendUpdate.ps1`
   - **Bash:**  
     `EC2_HOST=your.instance.dns EC2_USER=ubuntu ./apps/backend/deploy/ec2-ssh-pull-restart-from-local.sh`

The remote script is `apps/backend/deploy/ec2-pull-restart.sh` (git `fetch`/`reset` to `origin/main`, `pip install`, `systemctl restart alldoing`, local `/health` check). It uses `REPO_DIR=/home/$USER/all-doing-bot` by default.

If you cannot SSH from the agent environment, trigger **Deploy backend (EC2)** in GitHub Actions (workflow_dispatch) or ask the operator to run the script. See `AGENTS.md` and `apps/backend/deploy/ec2-runbook.md`.
