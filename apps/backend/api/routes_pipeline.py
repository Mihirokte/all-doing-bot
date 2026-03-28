"""Long pipeline: query accept, status, cohort catalogue and entries."""
from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter, HTTPException

from apps.backend.models.schemas import CohortEntry, CohortInfo, QueryAcceptResponse, TaskStatusResponse
from apps.backend.pipeline.router import enqueue_pipeline
from apps.backend.pipeline.task_store import task_store
from apps.backend.telemetry import log_run_event

router = APIRouter(tags=["pipeline"])

_COHORT_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


@router.get("/query", response_model=QueryAcceptResponse)
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


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_status(task_id: str) -> TaskStatusResponse:
    """Poll task status and result."""
    resp = task_store.get_response(task_id)
    if resp is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return resp


@router.get("/cohorts", response_model=list[CohortInfo])
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


@router.get("/cohort/{name}", response_model=list[CohortEntry])
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
