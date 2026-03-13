# Personal-use recipes and quality tuning

Ready-to-use query templates and cohort naming conventions for the all-doing-bot backend. Optimized for **quality** (richer results, fewer low-value entries).

---

## Environment knobs that affect quality

| Env / behavior | Effect |
|----------------|--------|
| **SEARXNG_BASE_URL** | Must point to a working SearXNG instance for `search_web`. |
| **CLOUDFLARE_ACCOUNT_ID** + **CLOUDFLARE_API_TOKEN** | When set, enriches top 2 search results with full-page Markdown via Cloudflare Browser Rendering (bot-friendly). Also used for `web_fetch` before falling back to the extractor. |
| **LLM_PROVIDER_PRIORITY** | Use `ollama,local,remote,mock` for real planning; mock returns canned plans. |
| **OLLAMA_MODEL** / **REMOTE_LLM_MODEL** | Better models tend to produce more accurate `search_web` vs `web_fetch` and non-empty `q`. |

Pipeline behavior:

- **Guardrail:** If the planner outputs `web_fetch` with no URLs but the parsed intent has a search query (`q`/`query`/`keyword` or `action_type: search_web`), the executor reroutes to `search_web` with that query so you don’t get stub entries.
- **Multi-step:** Up to 5 steps run in order; each step’s entry count is recorded in `result.raw.steps`.

---

## Query templates (personal use)

Use these as-is or adapt. Cohort names are normalized to `snake_case` by the LLM.

### Daily intelligence / news

- *"Create a cohort called ai_news and search the web for latest AI and LLM news"*
- *"Create cohort security_brief and search for cybersecurity news this week"*
- *"Search the web for Python 3.12 release notes and add to cohort python_updates"*

### Learning and docs

- *"Create cohort rust_tutorials and search for Rust programming tutorials"*
- *"Search for FastAPI best practices and put results in cohort fastapi_learn"*

### Buying / product research

- *"Create cohort monitor_reviews and search for 27 inch monitor reviews 2024"*  
  Then use `web_fetch` with specific URLs from the cohort if you want full-page content (e.g. via a follow-up or manual URL list).

### Career and jobs

- *"Create cohort remote_dev_jobs and search for remote software engineer jobs"*
- *"Search for data engineer salary trends and add to cohort career_radar"*

### Project scouting

- *"Create cohort oss_alternatives and search for open source alternatives to Notion"*
- *"Search for headless CMS comparison and add to cohort cms_scout"*

---

## Cohort naming conventions

- Use **snake_case** in the query (e.g. `ai_news`, `python_updates`). The parser normalizes to this.
- Prefix by purpose if you like: `news_ai`, `learn_rust`, `jobs_remote`, `research_monitors`.

---

## Quality-focused verification

1. **After submitting a search-style query**
   - Poll `GET /status/{task_id}` until `status` is `completed`.
   - Check `result.raw.steps`: you should see at least one step with `action: "search_web"` and `entry_count > 0`. If you see `web_fetch` with `entry_count: 1` and the only entry says "No URLs in action_params", the guardrail should have prevented that; if it still happens, the parsed intent had no `q` (check LLM/output).

2. **Cloudflare enrichment**
   - If `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` are set, entries from the top 2 result URLs may appear with long Markdown content and `metadata.source: "cloudflare_crawl"`. If Crawl fails for one URL, the other is still returned (partial success).

3. **Full pipeline test**
   - From [testing-backend-operations.md](testing-backend-operations.md), run health → submit a search query → poll status → list cohorts → get cohort entries. Confirm entries have real titles/snippets (and optionally full content from Cloudflare).

4. **Unit tests**
   - Run `python -m pytest tests -q` to lock in guardrail, multi-step, and action behavior.
