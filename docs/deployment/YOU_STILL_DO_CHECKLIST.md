# What you still need to do (vs what’s already done)

**Last server sync (from dev machine):** EC2 pulled `main`, deps installed, `alldoing` restarted — health OK at `https://54-165-94-30.sslip.io/health`.

---

## Already in good shape (minimal action)

| Item | Status |
|------|--------|
| Code on GitHub `main` | Up to date |
| EC2 repo + Python 3.11 venv + LangGraph/MCP packages | Done |
| Systemd `alldoing` | Running |
| Public API (sslip) | Should respond `/health` |
| Frontend `BACKEND_URL` in `index.html` | Points at sslip host |
| GitHub Pages workflow | Runs on push to `main` → publishes `apps/frontend` |

---

## You must do in browser / AWS (I can’t do these)

### 1) GitHub Actions → auto backend deploy (optional but recommended)

**Repo → Settings → Secrets and variables → Actions**

**Secrets (new):**

| Name | Value |
|------|--------|
| `EC2_HOST` | `ec2-54-165-94-30.compute-1.amazonaws.com` *or* `54.165.94.30` |
| `EC2_USER` | `ec2-user` |
| `EC2_SSH_KEY` | Full text of private key: `%USERPROFILE%\.ssh\alldoing_ec2` (no `.pub`) |

**Variables → New repository variable:**

| Name | Value |
|------|--------|
| `EC2_AUTO_DEPLOY` | `true` |

- If you **skip** `EC2_AUTO_DEPLOY`, only run deploy manually: **Actions → Deploy backend (EC2) → Run workflow**.

**AWS security group:** inbound **TCP 22** must be allowed from **GitHub Actions** (simplest: `0.0.0.0/0` — weaker; tighter options in `github-actions-ec2-autodeploy.txt`).

**Verify:** Actions tab → green run → `curl https://54-165-94-30.sslip.io/health`

---

### 2) GitHub Pages

**Repo → Settings → Pages**

- Source: branch **`gh-pages`**, folder **`/`** (root)  
- After each push to `main`, workflow **Deploy GitHub Pages** updates the site.

**Open:** `https://mihirokte.github.io/all-doing-bot/` (adjust if your username/repo differs)

---

### 3) Google Sign-In (if you use it)

**Google Cloud Console → APIs & Services → Credentials → your OAuth Web client**

- **Authorized JavaScript origins** must include your Pages URL, e.g.  
  `https://mihirokte.github.io`  
  (and full app path if Google requires it for your setup)

Details: `docs/deployment/google-oauth-github-pages.md`

---

### 4) EC2 `.env` (secrets stay on the server only)

SSH: `ssh -i %USERPROFILE%\.ssh\alldoing_ec2 ec2-user@ec2-54-165-94-30.compute-1.amazonaws.com`

Edit `~/all-doing-bot/.env` — **never commit `.env`**.

| Variable | Notes |
|----------|--------|
| `REMOTE_LLM_API_KEY` | If you use Groq/remote LLM |
| `GOOGLE_CREDS_PATH` | Path to service account JSON on EC2 |
| `CORS_ALLOW_ORIGINS` | Must include `https://mihirokte.github.io` (and localhost for dev) |
| `CONNECTOR_SEARCH_DEFAULT_PROVIDER` | Currently **`searxng`** on your box (SearXNG). For MCP default, set **`mcp`** and add valid **`MCP_SEARCH_COMMAND_JSON`**. |
| `REDIS_URL` | Optional; set if you run queue + worker |

After edits: `sudo systemctl restart alldoing`

---

## Quick copy: secret/variable values (no private key)

```
EC2_HOST=ec2-54-165-94-30.compute-1.amazonaws.com
EC2_USER=ec2-user
EC2_AUTO_DEPLOY=true
```

`EC2_SSH_KEY` = contents of file `alldoing_ec2` (private key only).

---

## Reference files in repo

- `docs/deployment/github-actions-ec2-autodeploy.txt` — Actions + extracted host/user/paths  
- `docs/deployment/aws-credentials-and-deploy.md` — broader AWS/SSH  
- `docs/deployment/google-oauth-github-pages.md` — OAuth for Pages  
