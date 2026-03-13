"""FastAPI app: query submission, task polling, cohorts, health. CORS for GitHub Pages."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.config import settings
from apps.backend.models.schemas import (
    CohortInfo,
    CohortEntry,
    QueryAcceptResponse,
    TaskStatusResponse,
)
from apps.backend.pipeline.router import run_pipeline
from apps.backend.pipeline.task_store import task_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: log LLM/persistence mode; shutdown: cancel background tasks."""
    # LLM provider resolution
    logger.info("LLM provider order: %s", settings.llm_provider_order)
    if settings.ollama_base_url and settings.ollama_model:
        logger.info("Ollama configured: %s (model=%s)", settings.ollama_base_url, settings.ollama_model)
    if settings.model_file_path:
        logger.info("Local model configured: %s", settings.model_path)
    else:
        logger.info("Local model not configured (MODEL_PATH unset or file missing)")
    if settings.remote_llm_api_key:
        logger.info("Remote LLM API key configured (REMOTE_LLM_API_KEY set)")
    else:
        logger.info("Remote LLM API not configured (REMOTE_LLM_API_KEY unset); will use local or mock when needed")
    if not settings.model_file_path and not settings.remote_llm_api_key:
        logger.info("No remote or local model configured; using mock LLM. Set REMOTE_LLM_API_KEY or MODEL_PATH for real output")
    # Persistence (Drive + Sheets: by SPREADSHEET_ID or find/create by GOOGLE_SHEETS_SPREADSHEET_NAME)
    from apps.backend.db.google_client import spreadsheet_available
    if not settings.credentials_path:
        logger.warning("GOOGLE_CREDS_PATH not set or file not found; persistence will use in-memory fake")
    elif spreadsheet_available():
        if settings.spreadsheet_id:
            logger.info("Google persistence configured (GOOGLE_CREDS_PATH + SPREADSHEET_ID)")
        else:
            logger.info(
                "Google persistence configured (GOOGLE_CREDS_PATH + GOOGLE_SHEETS_SPREADSHEET_NAME=%s; find or create)",
                settings.google_sheets_spreadsheet_name or "all-doing-bot cohorts",
            )
    else:
        logger.warning(
            "Set GOOGLE_CREDS_PATH and either SPREADSHEET_ID or GOOGLE_SHEETS_SPREADSHEET_NAME for real persistence"
        )
    yield
    # Allow in-flight pipeline tasks to finish briefly
    await asyncio.sleep(0.5)


app = FastAPI(
    title="all-doing-bot",
    description="LLM-powered query -> cohort/action pipeline, results in Google Sheets",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check for monitoring and cron."""
    return {"status": "ok"}


def _chat_looks_like_search(query: str) -> bool:
    """True if the short query implies the user wants live web results (find, search, latest, etc.)."""
    lower = query.strip().lower()
    if len(lower) < 4:
        return False
    triggers = (
        "find", "search", "look up", "lookup", "get me", "fetch",
        "latest", "recent", "today", "this week", "top", "best", "trending",
        "what are the", "when did", "who is the", "where can i", "how do i",
        "news about", "updates on", "launches", "release", "projects", "github",
    )
    return any(t in lower for t in triggers)


def _search_response_from_entries(query: str, entries: list) -> str:
    """Return direct, concrete search results for chat (no abstraction)."""
    lines = [f"Here are the top results for '{query}':"]
    rank = 1
    for e in entries[:5]:
        content = (getattr(e, "content", "") or "").strip()
        source = (getattr(e, "source", "") or "").strip()
        if not content:
            continue
        title = content
        snippet = ""
        if content.startswith("**") and "**" in content[2:]:
            # content format from WebSearchAction: **title**\n\nsnippet
            end = content.find("**", 2)
            title = content[2:end].strip() or title
            rest = content[end + 2 :].strip()
            if rest.startswith("\n\n"):
                rest = rest[2:].strip()
            snippet = rest
        snippet = snippet or content
        snippet = " ".join(snippet.split())
        if len(snippet) > 180:
            snippet = snippet[:180].rstrip() + "..."
        line = f"{rank}. {title}"
        if source:
            line += f" - {source}"
        if snippet:
            line += f"\n   {snippet}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return "I couldn't find concrete web results right now. Please try rephrasing the query."
    return "\n".join(lines)


def _crawl_response_from_records(query: str, records: list[dict]) -> str:
    """Return concrete link-hit results from crawled pages."""
    lines = [f"I crawled top links for '{query}' and found:"]
    rank = 1
    for rec in records[:3]:
        if not isinstance(rec, dict):
            continue
        url = str(rec.get("url") or "").strip()
        markdown = str(rec.get("markdown") or "").strip()
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        title = str(meta.get("title") or "").strip() if meta else ""
        if not markdown:
            continue
        summary = " ".join(markdown.split())
        if len(summary) > 240:
            summary = summary[:240].rstrip() + "..."
        label = title or url or f"Result {rank}"
        line = f"{rank}. {label}"
        if url:
            line += f" - {url}"
        line += f"\n   {summary}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return ""
    return "\n".join(lines)


def _fetched_response_from_entries(query: str, entries: list) -> str:
    """Return concrete summaries from fetched page content."""
    lines = [f"I opened top links for '{query}' and found:"]
    rank = 1
    for e in entries[:4]:
        content = (getattr(e, "content", "") or "").strip()
        source = (getattr(e, "source", "") or "").strip()
        if not content or content.lower().startswith("error:"):
            continue
        summary = " ".join(content.split())
        if len(summary) > 260:
            summary = summary[:260].rstrip() + "..."
        label = source or f"Result {rank}"
        line = f"{rank}. {label}\n   {summary}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return ""
    return "\n".join(lines)


@app.get("/chat")
async def chat(q: str = "") -> dict[str, str]:
    """
    Short-query path: single LLM call, no cohort.
    If the query looks like search intent (find, latest, search...), run web search
    first and feed snippets to the LLM so the answer uses real results.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    from apps.backend.actions.registry import run_action
    from apps.backend.llm.engine import get_llm

    query = q.strip()
    if _chat_looks_like_search(query):
        try:
            entries = await run_action("search_web", {"q": query, "top_n": 5})
            if entries:
                # Proper web protocol: hit returned links via Cloudflare crawl when configured.
                from apps.backend.actions.cloudflare_crawl import _available as crawl_available, crawl_urls

                if crawl_available():
                    urls = []
                    for e in entries[:5]:
                        src = (getattr(e, "source", "") or "").strip()
                        if src and src.startswith("http"):
                            urls.append(src)
                    if urls:
                        records = await crawl_urls(urls[:3], limit_per_url=1, formats=["markdown"], render=False)
                        crawl_text = _crawl_response_from_records(query, records)
                        if crawl_text:
                            return {"response": crawl_text}
                # Fallback path: still hit links via web_fetch/extractor if crawl isn't configured or yields nothing.
                urls = []
                for e in entries[:5]:
                    src = (getattr(e, "source", "") or "").strip()
                    if src and src.startswith("http"):
                        urls.append(src)
                if urls:
                    fetched = await run_action("web_fetch", {"urls": urls[:3]})
                    fetched_text = _fetched_response_from_entries(query, fetched)
                    if fetched_text:
                        return {"response": fetched_text}
                return {"response": _search_response_from_entries(query, entries)}
        except Exception as e:
            logger.warning("Chat web search failed (continuing without): %s", e)

    llm = get_llm()
    prompt = f"Answer concisely in 2-3 sentences. Do not use markdown or bullet points. Question: {query}"
    try:
        response = await llm.generate(prompt, max_tokens=200, json_mode=False)
        return {"response": (response or "").strip()}
    except Exception as e:
        logger.warning("Chat LLM failed: %s", e)
        raise HTTPException(status_code=503, detail="LLM unavailable for chat")


@app.post("/admin/clear-data")
async def clear_data() -> dict:
    """
    Clear past sessions and persisted cohort data.
    - Deletes all cohorts (and backing sheets in Google mode)
    - Clears in-memory task sessions
    """
    from apps.backend.db.catalogue import catalogue

    deleted_cohorts = 0
    cohorts = await catalogue.list_cohorts()
    for c in cohorts:
        try:
            await catalogue.delete_cohort(c.cohort_name)
            deleted_cohorts += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed deleting cohort %s: %s", c.cohort_name, e)

    cleared_tasks = task_store.clear_all()
    return {
        "status": "ok",
        "deleted_cohorts": deleted_cohorts,
        "cleared_tasks": cleared_tasks,
    }


@app.get("/query", response_model=QueryAcceptResponse)
async def submit_query(q: str = "") -> QueryAcceptResponse:
    """
    Accept a natural language query, create a task, and return task_id.
    Pipeline runs in the background.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    task_id = task_store.create(q.strip())
    asyncio.create_task(run_pipeline(task_id, q.strip()))
    task_store.cleanup_old()
    return QueryAcceptResponse(task_id=task_id, status="accepted")


@app.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_status(task_id: str) -> TaskStatusResponse:
    """Poll task status and result."""
    resp = task_store.get_response(task_id)
    if resp is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return resp


@app.get("/cohorts", response_model=list[CohortInfo])
async def list_cohorts() -> list[CohortInfo]:
    """List all cohorts from the master catalogue."""
    from apps.backend.db.catalogue import catalogue
    cohorts = await catalogue.list_cohorts()
    return [
        CohortInfo(
            cohort_name=c.cohort_name,
            cohort_description=c.cohort_description,
            action_type=c.action_type,
            sheet_name=c.sheet_name or c.cohort_name,
            entry_count=c.entry_count,
            created_at=c.created_at,
            last_run=c.last_run,
        )
        for c in cohorts
    ]


@app.get("/cohort/{name}", response_model=list[CohortEntry])
async def get_cohort_entries(name: str) -> list[CohortEntry]:
    """Return entries for a cohort."""
    from apps.backend.db.catalogue import catalogue
    from apps.backend.db.sheets import list_cohort_entries as db_list_entries
    if await catalogue.get_cohort(name) is None:
        raise HTTPException(status_code=404, detail="Cohort not found")
    rows = await db_list_entries(name, limit=100, offset=0)
    out: list[CohortEntry] = []
    for r in rows:
        meta = r.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta) if meta else {}
            except json.JSONDecodeError:
                meta = {}
        out.append(
            CohortEntry(
                entry_id=r["entry_id"],
                content=r["content"],
                source=r.get("source", ""),
                metadata=meta,
                created_at=r.get("created_at", ""),
            )
        )
    return out


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
