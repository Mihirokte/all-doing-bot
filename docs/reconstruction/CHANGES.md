# Reconstruction program — change log

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
| **Phase 3** | Split `main.py`, move chat into `services/`, router packages; optional CSS file split | Large mechanical refactor; must be slice-based to avoid regressions |
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

1. Open a PR that **only** extracts `services/chat_service.py` + `api/routes_chat.py`.
2. Run full pytest + manual `/chat` smoke.
3. Repeat for pipeline routes.
4. Split CSS tokens per `DESIGN_SYSTEM.md` without visual change (diff screenshots).
