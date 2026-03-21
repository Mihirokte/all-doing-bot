# all-doing-bot — deployment task list

Use this as a living checklist. Check items off as you complete them.

---

## Infrastructure & CI

- [ ] **GitHub Secrets (Actions)** — `EC2_HOST` = `ec2-54-165-94-30.compute-1.amazonaws.com` or `54.165.94.30`
- [ ] **GitHub Secrets** — `EC2_USER` = `ec2-user`
- [ ] **GitHub Secrets** — `EC2_SSH_KEY` = full private key from `%USERPROFILE%\.ssh\alldoing_ec2`
- [ ] **GitHub Variable** — `EC2_AUTO_DEPLOY` = `true` (optional; skip for manual-only deploys)
- [ ] **AWS security group** — inbound TCP **22** allowed for GitHub Actions SSH (or use manual workflow / SSM / self-hosted runner)
- [ ] **Run workflow once** — Actions → *Deploy backend (EC2)* → Run workflow → green check
- [ ] **Verify API** — open or curl `https://54-165-94-30.sslip.io/health`

---

## Frontend (GitHub Pages)

- [ ] **Pages settings** — Source: branch `gh-pages`, folder `/`
- [ ] **Confirm deploy** — push to `main` triggers *Deploy GitHub Pages*; Actions green
- [ ] **Open site** — `https://mihirokte.github.io/all-doing-bot/` (adjust if repo/user differs)
- [ ] **`BACKEND_URL`** — in `apps/frontend/index.html` matches public API (e.g. sslip URL); redeploy if changed

---

## Auth & Google

- [ ] **OAuth Web client** — Authorized JavaScript origins include `https://mihirokte.github.io` (and path if required)
- [ ] **Test Sign in with Google** on the live Pages URL

---

## Backend (EC2)

- [ ] **`.env` on server** — `CORS_ALLOW_ORIGINS` includes your Pages origin + localhost for dev
- [ ] **`.env`** — `GOOGLE_CREDS_PATH` points to service account JSON on EC2
- [ ] **`.env`** — `REMOTE_LLM_API_KEY` set if using Groq/remote LLM
- [ ] **Search** — `CONNECTOR_SEARCH_DEFAULT_PROVIDER` = `searxng` *or* `mcp` + valid `MCP_SEARCH_COMMAND_JSON`
- [ ] **SearXNG** — running if using `searxng` (e.g. `http://localhost:8888` from app’s perspective)
- [ ] **Redis + worker** (optional) — `REDIS_URL` set; worker process running if you use queue mode
- [ ] **After `.env` edits** — `sudo systemctl restart alldoing`

---

## Repo / docs (optional housekeeping)

- [ ] Read `docs/deployment/YOU_STILL_DO_CHECKLIST.md` for narrative “you vs done”
- [ ] Read `docs/deployment/github-actions-ec2-autodeploy.txt` for Actions cheat sheet

---

## Smoke test (when everything is green)

- [ ] **Health** — `GET /health` returns `ok` and `workflows: true`
- [ ] **UI** — load cohorts / chat / quick workflows without console errors
- [ ] **Task or note workflow** — save and list via API or UI
