# Frontend Workflow

Use this guide when changing code under `apps/frontend/`.

## Scope

The frontend is a static app served from `apps/frontend/`:

- `index.html`
- `css/style.css`
- `js/config.js`
- `js/api.js`
- `js/app.js`

## Editing rules

- Keep the frontend static unless the repo plan explicitly changes that choice.
- Preserve compatibility with the backend API contract.
- Keep relative asset paths working from `apps/frontend/index.html`.
- Avoid introducing a framework unless there is an explicit architectural decision to do so.

## Local preview

```bash
cd apps/frontend
python -m http.server 3000
```

## Backend integration assumptions

- Backend URL is configured in `apps/frontend/js/config.js`.
- Query submission and polling should remain aligned with the backend routes.
- Cohort browsing and entry rendering should continue to work against the current JSON shapes.

## High-signal checks after edits

- static assets still load correctly
- API calls still target the correct backend URL
- no stale references to old `frontend/` paths remain in docs or comments
