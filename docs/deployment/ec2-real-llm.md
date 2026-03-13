# Real LLM on EC2

The backend uses **remote** (API) or **local** (GGUF) LLM. On a small EC2 instance, the practical option is a **remote API** (e.g. Groq free tier).

## 1. Get an API key (Groq, free tier)

1. Go to [https://console.groq.com](https://console.groq.com) and sign in.
2. Open **API Keys** and create a key.
3. Copy the key (starts with `gsk_...`).

## 2. Set it on the EC2 host

SSH into the instance, then:

```bash
cd /home/ec2-user/all-doing-bot

# Create .env from example if missing
test -f .env || cp .env.example .env

# Edit .env and set (replace YOUR_GROQ_KEY with your key):
#   REMOTE_LLM_API_KEY=gsk_...
nano .env
```

Add or set:

```env
REMOTE_LLM_API_KEY=gsk_your_actual_key_here
```

Save (Ctrl+O, Enter, Ctrl+X), then restart:

```bash
sudo systemctl restart alldoing
sudo systemctl status alldoing
```

## 3. Verify

From your machine:

```bash
curl -s "http://54.165.94.30:8000/query?q=Create%20a%20cohort%20test%20and%20summarize%20AI%20news"
```

You should get a `task_id`. Poll status until `completed`; the result should reflect real LLM output (cohort name, summary) instead of mock.

## Optional: other providers

The backend is OpenAI-compatible. To use another provider, set in `.env`:

- `REMOTE_LLM_BASE_URL` (e.g. `https://api.openai.com/v1`)
- `REMOTE_LLM_MODEL` (e.g. `gpt-4o-mini`)
- `REMOTE_LLM_API_KEY` = that provider’s API key

Then restart `alldoing`.

## Optional: quality and web search

- **Ollama on EC2:** Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` and put `ollama` first in `LLM_PROVIDER_PRIORITY` for local inference. Ensure enough disk and RAM (see deployment docs).
- **SearXNG:** Set `SEARXNG_BASE_URL` to your SearXNG instance so “search the web” queries return real results.
- **Cloudflare Browser Rendering:** Set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (token with “Browser Rendering - Edit”) to enrich top search results with full-page Markdown and to use bot-friendly fetch for `web_fetch`. See [personal-use-recipes.md](../instructions/personal-use-recipes.md) for quality verification steps.
