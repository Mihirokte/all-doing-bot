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
    # Persistence
    if not settings.spreadsheet_id:
        logger.warning("SPREADSHEET_ID not set; persistence will use in-memory fake if creds also missing")
    if not settings.credentials_path:
        logger.warning("GOOGLE_CREDS_PATH not set or file not found; persistence will use in-memory fake")
    if settings.credentials_path and settings.spreadsheet_id:
        logger.info("Google persistence configured (GOOGLE_CREDS_PATH + SPREADSHEET_ID)")
    else:
        logger.warning("Running with in-memory (fake) persistence; set GOOGLE_CREDS_PATH and SPREADSHEET_ID for real persistence")
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
