# Contributing — mental model

Read **`docs/reconstruction/RECON.md`** and **`ARCHITECTURE.md`** before large changes.

## What this repo is

A **single-user** bot: natural language → **either** short `/chat` (gate + optional web + transcript) **or** long `/query` (parse → plan → execute → store). Durable rows live in **Google Sheets** cohorts. Optional **Redis** moves step execution to a worker.

## Non-negotiables

1. **Pipeline discipline** — Do not write from HTTP handlers directly into Sheets for pipeline-shaped work; use the executor path (see `AGENTS.md`).
2. **Imports** — Backend code uses `apps.backend.*` only.
3. **Tests** — `python -m pytest tests -q` from repo root before push.
4. **LLM testability** — New code must run with **mock** provider in CI.

## Where to change what

| Goal | Start here |
|------|------------|
| New action type | `actions/`, `contracts.py`, `registry.py`, tests in `test_actions.py` |
| Search provider | `connectors/`, `config.py` |
| Chat behaviour | `main.py` (today) → `services/chat_service.py` (target) |
| Pipeline stages | `pipeline/executor.py`, `agents/parse_plan.py`, `llm/prompts.py` |
| UI copy / layout | `apps/frontend/` + `DESIGN_SYSTEM.md` |

## PR style

- One logical change per PR.
- If you touch architecture, add a line to **`docs/reconstruction/CHANGES.md`** under “Decisions”.
