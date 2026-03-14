# Single EC2 Hardening Baseline

Production baseline for queue-first runtime on one EC2 in a VPC.

## Core services

- FastAPI API service
- Worker service (`python -m apps.backend.workers.run_worker`)
- Redis (queue + durable run state)
- Reverse proxy (TLS termination)

## Network and security

- Expose only `443` publicly (and `80` for ACME/TLS bootstrap when needed).
- Keep API app port and Redis private to host/VPC.
- Use IAM role + AWS Secrets Manager/SSM for secrets.
- Enable CloudWatch logs/metrics and alarms.

## Recommended env

- `REDIS_URL=redis://<redis-host>:6379/0`
- `ORCHESTRATOR_LEGACY_FALLBACK_ENABLED=false`
- `CHAT_WEB_SEARCH_ENABLED=false` (if short-query web search remains disabled)

## Operational checks

- Health: `GET /health`
- Queue run path: submit `GET /query?q=...`, poll `GET /status/{task_id}` and confirm `result.raw.execution_mode` is queue-based.
- Worker liveness: confirm worker logs include `step_worker_received` and `step_completed`.
