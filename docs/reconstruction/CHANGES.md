# Reconstruction program — change log

## 2026-03-29 — Phase 3 slice (routers + chat service + CSS tokens)

### Delivered

| Change | Notes |
|--------|--------|
| `apps/backend/services/chat_service.py` | Chat retrieval, heuristics, `handle_chat`; no FastAPI |
| `apps/backend/api/routes_*.py` | Health, chat, admin, pipeline (query/status/cohorts), workflows |
| `apps/backend/main.py` | `create_app()`, lifespan, CORS; mounts routers (~130 lines) |
| `apps/frontend/css/tokens.css` | `:root` tokens; `style.css` imports via `@import` |
| Tests | `test_chat_gating` imports helpers from `chat_service` |

### Still deferred (later slices)

- `api/deps.py`, domain DTO split, renaming `models` → `domain`
- Phase 4 profiling, Phase 5 README/docstring sweep

---

## 2026-03-29 — Documentation phase (Phases 0–2 + contract)

### Delivered (this session)

| Artifact | Path |
|----------|------|
| Phase 0 recon | `docs/reconstruction/RECON.md` |
| Phase 1 target architecture | `docs/reconstruction/ARCHITECTURE.md` |
| Phase 2 design system | `docs/reconstruction/DESIGN_SYSTEM.md` |
| Contributor mental model | `docs/reconstruction/CONTRIBUTING.md` |
| This file | `docs/reconstruction/CHANGES.md` |
| README pointer | Root `README.md` (new “Reconstruction” section) |

### Explicitly deferred (requires dedicated sprints)

| Phase | Scope | Why deferred |
|-------|--------|--------------|
| **Phase 3 (remainder)** | `deps.py`, pipeline/workflow service layers, optional `domain/` package | First vertical slice done (routers + `chat_service` + token CSS) |
| **Phase 4** | Profile hot paths (LLM, Sheets, search), bundle measurement | No baseline profiling captured in CI yet |
| **Phase 5** | Full README rewrite, per-function docstrings everywhere, ADR files for every decision | Partially satisfied by reconstruction docs; full pass is weeks |

### Preserved (intentionally unchanged in this session)

- All runtime Python and frontend JS/CSS behaviour.
- Test count: **71 passed** (pre-doc baseline).

### Decisions recorded

1. **Reconstruction docs live under `docs/reconstruction/`** — avoids cluttering repo root; still linked from README.
2. **No new runtime dependencies** for documentation.
3. **Target architecture keeps Sheets** as the personal-use database; Postgres deferred until a stated scale trigger.

---

## How to continue Phase 3

1. Extract thin `pipeline_service.py` / `cohort_service.py` if handlers stay bulky in routers.
2. Add `api/deps.py` (`get_settings`, shared dependencies).
3. Run full pytest + manual `/chat` and `/query` smoke after each change.
