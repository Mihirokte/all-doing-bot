"""Deterministic task/note workflow routes (Sheets-backed)."""
from __future__ import annotations

from fastapi import APIRouter

from apps.backend.models.schemas import WorkflowItem, WorkflowSaveBody, WorkflowSaveResponse

router = APIRouter(tags=["workflows"])


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
@router.post("/workflows/task", response_model=WorkflowSaveResponse)
@router.post("/api/v1/workflow/task", response_model=WorkflowSaveResponse)
async def workflow_add_task(body: WorkflowSaveBody) -> WorkflowSaveResponse:
    """Deterministic: save one task row (Sheets cohort per session_key). No LLM."""
    return await _workflow_save_task(body)


@router.post("/workflows/note", response_model=WorkflowSaveResponse)
@router.post("/api/v1/workflow/note", response_model=WorkflowSaveResponse)
async def workflow_add_note(body: WorkflowSaveBody) -> WorkflowSaveResponse:
    """Deterministic: save one note row. No LLM."""
    return await _workflow_save_note(body)


@router.get("/workflows/tasks", response_model=list[WorkflowItem])
@router.get("/api/v1/workflow/tasks", response_model=list[WorkflowItem])
async def workflow_list_tasks(session_key: str = "default", limit: int = 50) -> list[WorkflowItem]:
    return await _workflow_list_tasks(session_key, limit)


@router.get("/workflows/notes", response_model=list[WorkflowItem])
@router.get("/api/v1/workflow/notes", response_model=list[WorkflowItem])
async def workflow_list_notes(session_key: str = "default", limit: int = 50) -> list[WorkflowItem]:
    return await _workflow_list_notes(session_key, limit)
