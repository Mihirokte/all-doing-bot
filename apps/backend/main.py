"""FastAPI app: query submission, task polling, cohorts, health. CORS for GitHub Pages."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.config import settings
from apps.backend.models.schemas import (
    CohortEntry,
    CohortInfo,
    QueryAcceptResponse,
    TaskStatusResponse,
    WorkflowItem,
    WorkflowSaveBody,
    WorkflowSaveResponse,
)
from apps.backend.pipeline.router import enqueue_pipeline
from apps.backend.pipeline.task_store import task_store
from apps.backend.telemetry import log_run_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _ensure_english_response(text: str) -> str:
    """Normalize assistant output to English while preserving facts and links."""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    try:
        from apps.backend.llm.engine import get_llm

        llm = get_llm()
        prompt = (
            "Rewrite the following text in clear English only. Preserve meaning, "
            "facts, numbers, names, URLs, and formatting structure (lists/line breaks). "
            "If already English, keep the same level of detail and mostly unchanged. "
            "Do not shorten or compress details. Output only the rewritten text. "
            "Do not add intro phrases such as 'Here is the rewritten text'.\n\n"
            f"Text:\n{cleaned}"
        )
        rewritten = await llm.generate(prompt, max_tokens=450, json_mode=False)
        rewritten = (rewritten or "").strip()
        if rewritten.lower().startswith("here is"):
            rewritten = rewritten.split("\n", 1)[-1].strip()
        return rewritten or cleaned
    except Exception as e:  # noqa: BLE001
        logger.warning("English normalization failed; using original text: %s", e)
        return cleaned


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: log LLM/persistence mode; shutdown: cancel background tasks."""
    import sys

    if sys.version_info < (3, 10):
        logger.critical("Python 3.10+ is required (langgraph, mcp). Current: %s", sys.version)
        raise SystemExit(1)
    try:
        import langgraph  # noqa: F401
        import mcp  # noqa: F401
    except ImportError as e:
        logger.critical("Required packages missing: langgraph, mcp. pip install -r apps/backend/requirements.txt — %s", e)
        raise SystemExit(1) from e
    logger.info("Required stack OK: LangGraph + MCP packages importable")

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
    if not settings.ollama_base_url and not settings.model_file_path and not settings.remote_llm_api_key:
        logger.info("No ollama/remote/local model configured; using mock LLM. Set OLLAMA_BASE_URL or MODEL_PATH for real output")
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

_cors_origins = settings.cors_origins_list
if not _cors_origins:
    _cors_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
    logger.warning("CORS_ALLOW_ORIGINS not set, using localhost defaults")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check for monitoring and cron. `api.workflows` signals task/note workflow routes exist."""
    return {
        "status": "ok",
        "api": {
            "workflows": True,
            "version": "2026.03-chat-gate",
        },
    }


def _chat_looks_like_search(query: str) -> bool:
    """True if the short query implies the user wants live web results (find, search, latest, etc.)."""
    lower = query.strip().lower()
    if len(lower) < 4:
        return False
    triggers = (
        "find",
        "search",
        "look up",
        "lookup",
        "get me",
        "fetch",
        "latest",
        "recent",
        "today",
        "this week",
        "top",
        "best",
        "trending",
        "what are the",
        "when did",
        "who is the",
        "where can i",
        "how do i",
        "news about",
        "updates on",
        "launches",
        "release",
        "projects",
        "github",
        "review",
        "reviews",
        "movie",
        "movies",
        "film",
        "imdb",
        "rotten",
        "critic",
        "critics",
        "rating",
        "ratings",
        "box office",
        "sequel",
        "trailer",
        "cast of",
        "episode",
        "worth watching",
        "tell me the",
        "are you sure",
        "correct",
        "accurate",
        "sources",
        "source for",
    )
    return any(t in lower for t in triggers)


def _dedupe_entries_by_source(entries: list[Any], max_keep: int = 12) -> list[Any]:
    """Drop duplicate URLs (common with editorial listicles); keep order."""
    seen: set[str] = set()
    out: list[Any] = []
    for e in entries or []:
        src = (getattr(e, "source", "") or "").strip()
        key = src.split("#")[0].rstrip("/").lower() if src.startswith("http") else f"c:{hash((getattr(e, 'content', '') or '')[:300])}"
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= max_keep:
            break
    return out


def _search_wants_detail(query: str) -> bool:
    """True when user asks to find/search/explore and expects depth."""
    lower = query.strip().lower()
    detail_triggers = (
        "find",
        "search",
        "latest",
        "top",
        "best",
        "trending",
        "list",
        "compare",
        "detailed",
        "in detail",
    )
    return any(t in lower for t in detail_triggers)


def _search_response_from_entries(query: str, entries: list, detailed: bool = False) -> str:
    """Return direct, concrete search results for chat (no abstraction)."""
    lines = [f"Search results for '{query}':"]
    rank = 1
    cap = 7 if detailed else 5
    for e in entries[:cap]:
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
        if len(snippet) > (320 if detailed else 180):
            snippet = snippet[: (320 if detailed else 180)].rstrip() + "..."
        line = f"{rank}) {title}"
        if source:
            line += f"\n   Source: {source}"
        if snippet:
            line += f"\n   Summary: {snippet}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return "I couldn't find concrete web results right now. Please try rephrasing the query."
    if detailed:
        lines.append("")
        lines.append("If you want, I can continue with a deeper comparison of the top options.")
    return "\n".join(lines)


def _crawl_response_from_records(query: str, records: list[dict], detailed: bool = False) -> str:
    """Return concrete link-hit results from crawled pages."""
    lines = [f"I analyzed rendered pages for '{query}' and found:"]
    rank = 1
    cap = 5 if detailed else 3
    for rec in records[:cap]:
        if not isinstance(rec, dict):
            continue
        url = str(rec.get("url") or "").strip()
        markdown = str(rec.get("markdown") or "").strip()
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        title = str(meta.get("title") or "").strip() if meta else ""
        if not markdown:
            continue
        summary = " ".join(markdown.split())
        if len(summary) > (500 if detailed else 240):
            summary = summary[: (500 if detailed else 240)].rstrip() + "..."
        label = title or url or f"Result {rank}"
        line = f"{rank}) {label}"
        if url:
            line += f"\n   Source: {url}"
        line += f"\n   Key detail: {summary}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return ""
    return "\n".join(lines)


def _fetched_response_from_entries(query: str, entries: list, detailed: bool = False) -> str:
    """Return concrete summaries from fetched page content."""
    lines = [f"I fetched source pages for '{query}' and found:"]
    rank = 1
    cap = 6 if detailed else 4
    for e in entries[:cap]:
        content = (getattr(e, "content", "") or "").strip()
        source = (getattr(e, "source", "") or "").strip()
        if not content or content.lower().startswith("error:"):
            continue
        summary = " ".join(content.split())
        if len(summary) > (520 if detailed else 260):
            summary = summary[: (520 if detailed else 260)].rstrip() + "..."
        label = source or f"Result {rank}"
        line = f"{rank}) {label}\n   Detail: {summary}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return ""
    return "\n".join(lines)


async def _chat_retrieval_stack(search_q: str, display_q: str, detailed_search: bool) -> str | None:
    """Run deep search / search_web / crawl / fetch. Returns visible text or None."""
    from apps.backend.actions.cloudflare_crawl import _available as crawl_available, crawl_urls
    from apps.backend.actions.registry import run_action

    if getattr(settings, "chat_web_search_enabled", False) and getattr(settings, "chat_deep_mode_enabled", True):
        from apps.backend.deep_search import run_deep_search

        deep_response = await run_deep_search(search_q)
        if deep_response:
            return deep_response
    entries = await run_action("search_web", {"q": search_q, "top_n": 8})
    entries = _dedupe_entries_by_source(entries, 12)
    if not entries:
        return None

    if crawl_available():
        urls = []
        for e in entries[:6]:
            src = (getattr(e, "source", "") or "").strip()
            if src and src.startswith("http"):
                urls.append(src)
        if urls:
            records = await crawl_urls(urls[:3], limit_per_url=1, formats=["markdown"], render=False)
            crawl_text = _crawl_response_from_records(display_q, records, detailed=detailed_search)
            if crawl_text:
                return crawl_text
    urls = []
    for e in entries[:6]:
        src = (getattr(e, "source", "") or "").strip()
        if src and src.startswith("http"):
            urls.append(src)
    if urls:
        fetched = await run_action("web_fetch", {"urls": urls[:3]})
        fetched_text = _fetched_response_from_entries(display_q, fetched, detailed=detailed_search)
        if fetched_text:
            return fetched_text
    return _search_response_from_entries(display_q, entries, detailed=detailed_search)


@app.get("/chat")
async def chat(q: str = "") -> dict[str, str]:
    """
    Short-query path: structured gate (web vs direct), refined search queries, anti-hallucination prompt.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if len(q) > 10000:
        raise HTTPException(status_code=400, detail="Query too long (max 10000 characters)")
    from apps.backend.chat_routing import run_chat_web_route
    from apps.backend.llm.engine import get_llm
    from apps.backend.models.schemas import ChatWebRoute

    query = q.strip()
    detailed_search = _search_wants_detail(query)

    route = await run_chat_web_route(query)
    if route is None:
        route = ChatWebRoute()

    if route.ask_user_first and (route.ask_user_message or "").strip():
        return {"response": (route.ask_user_message or "").strip()}

    heuristic_search = _chat_looks_like_search(query)
    effective_web = bool(route.needs_web or heuristic_search)
    search_q = (route.search_query or "").strip() or query

    if effective_web:
        if not getattr(settings, "chat_web_search_enabled", False):
            return {
                "response": (
                    "I would need live web search to answer that without guessing, "
                    "but CHAT_WEB_SEARCH_ENABLED is off on this server. "
                    "Turn it on in the backend environment, or use a host where search is enabled."
                )
            }
        try:
            text = await _chat_retrieval_stack(search_q, query, detailed_search)
        except Exception as e:  # noqa: BLE001
            logger.warning("Chat web retrieval failed: %s", e)
            text = None
        if text:
            return {"response": await _ensure_english_response(text)}
        return {
            "response": (
                "Web search did not return usable results. "
                "Try a more specific query with a full name, title, year, or product name."
            )
        }

    llm = get_llm()
    prompt = (
        "You are a careful assistant.\n"
        "Answer in English only, in 2-4 short sentences. Do not use markdown or bullet lists.\n"
        "If you are not sure, say you are not sure. Do not invent movie titles, people, dates, "
        "statistics, reviews, box office numbers, or current events.\n"
        "If the question needs fresh news or niche facts you cannot verify from general knowledge, "
        "say you cannot confirm without a web search.\n"
        f"Question: {query}"
    )
    try:
        response = await llm.generate(prompt, max_tokens=220, json_mode=False)
        return {"response": await _ensure_english_response((response or "").strip())}
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
async def submit_query(q: str = "", session_key: str = "default") -> QueryAcceptResponse:
    """
    Accept a natural language query, create a task, and return task_id.
    Pipeline runs in the background.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if len(q) > 10000:
        raise HTTPException(status_code=400, detail="Query too long (max 10000 characters)")
    lane_key = (session_key or "default").strip() or "default"
    task_id = task_store.create(q.strip(), session_key=lane_key)
    log_run_event("run_accepted", run_id=task_id, stage="api", session_key=lane_key)
    asyncio.create_task(enqueue_pipeline(task_id, q.strip(), lane_key))
    if len(task_store._tasks) > 100:
        task_store.cleanup_old()
    return QueryAcceptResponse(task_id=task_id, status="accepted", session_key=lane_key)


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


async def _workflow_save_task(body: WorkflowSaveBody) -> WorkflowSaveResponse:
    from apps.backend.workflows.handlers import append_item

    sk = (body.session_key or "default").strip() or "default"
    out = await append_item(sk, "tasks", body.text)
    if not out.get("ok"):
        return WorkflowSaveResponse(ok=False, error=out.get("error"), message=out.get("message", ""))
    return WorkflowSaveResponse(
        ok=True,
        cohort_name=out.get("cohort_name", ""),
        entry_id=out.get("entry_id"),
        message=out.get("message", ""),
    )


async def _workflow_save_note(body: WorkflowSaveBody) -> WorkflowSaveResponse:
    from apps.backend.workflows.handlers import append_item

    sk = (body.session_key or "default").strip() or "default"
    out = await append_item(sk, "notes", body.text)
    if not out.get("ok"):
        return WorkflowSaveResponse(ok=False, error=out.get("error"), message=out.get("message", ""))
    return WorkflowSaveResponse(
        ok=True,
        cohort_name=out.get("cohort_name", ""),
        entry_id=out.get("entry_id"),
        message=out.get("message", ""),
    )


async def _workflow_list_tasks(session_key: str, limit: int) -> list[WorkflowItem]:
    from apps.backend.workflows.handlers import list_items

    sk = (session_key or "default").strip() or "default"
    rows = await list_items(sk, "tasks", limit=min(max(1, limit), 200))
    return [WorkflowItem(entry_id=r["entry_id"], content=r["content"], created_at=r["created_at"]) for r in rows]


async def _workflow_list_notes(session_key: str, limit: int) -> list[WorkflowItem]:
    from apps.backend.workflows.handlers import list_items

    sk = (session_key or "default").strip() or "default"
    rows = await list_items(sk, "notes", limit=min(max(1, limit), 200))
    return [WorkflowItem(entry_id=r["entry_id"], content=r["content"], created_at=r["created_at"]) for r in rows]


# Primary paths + /api/v1 aliases (some proxies only forward /api/*).
@app.post("/workflows/task", response_model=WorkflowSaveResponse)
@app.post("/api/v1/workflow/task", response_model=WorkflowSaveResponse)
async def workflow_add_task(body: WorkflowSaveBody) -> WorkflowSaveResponse:
    """Deterministic: save one task row (Sheets cohort per session_key). No LLM."""
    return await _workflow_save_task(body)


@app.post("/workflows/note", response_model=WorkflowSaveResponse)
@app.post("/api/v1/workflow/note", response_model=WorkflowSaveResponse)
async def workflow_add_note(body: WorkflowSaveBody) -> WorkflowSaveResponse:
    """Deterministic: save one note row. No LLM."""
    return await _workflow_save_note(body)


@app.get("/workflows/tasks", response_model=list[WorkflowItem])
@app.get("/api/v1/workflow/tasks", response_model=list[WorkflowItem])
async def workflow_list_tasks(session_key: str = "default", limit: int = 50) -> list[WorkflowItem]:
    return await _workflow_list_tasks(session_key, limit)


@app.get("/workflows/notes", response_model=list[WorkflowItem])
@app.get("/api/v1/workflow/notes", response_model=list[WorkflowItem])
async def workflow_list_notes(session_key: str = "default", limit: int = 50) -> list[WorkflowItem]:
    return await _workflow_list_notes(session_key, limit)


_COHORT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


@app.get("/cohort/{name}", response_model=list[CohortEntry])
async def get_cohort_entries(name: str) -> list[CohortEntry]:
    """Return entries for a cohort."""
    if not _COHORT_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid cohort name")
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
