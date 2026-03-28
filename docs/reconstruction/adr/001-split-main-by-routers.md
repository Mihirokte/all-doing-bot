# ADR-001: Split `main.py` by HTTP routers

- **Status:** Accepted (target state)
- **Date:** 2026-03-29

## Context

`apps/backend/main.py` holds FastAPI setup, `/chat` business logic, formatting helpers, cohort endpoints, admin, and health. This violates locality of behaviour and makes unit testing expensive.

## Decision

Introduce `apps/backend/api/routes_*.py` modules and a thin `create_app()` factory. Services (`services/chat_service.py`, …) own orchestration; routers only validate IO and map errors to HTTP.

## Consequences

- **Positive:** Clear OpenAPI grouping, smaller files, easier mocks.
- **Negative:** Short-term import churn; all PRs must update tests that patch `main`.

## Migration

Vertical slice: chat routes first, then pipeline, then admin.
