"""Task / note persistence: one cohort per (session_key, kind) via stable hashed name."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.db.catalogue import catalogue
from apps.backend.db.models import Cohort, Entry
from apps.backend.db.sheets import add_entries, list_cohort_entries

logger = logging.getLogger(__name__)

_workflow_lock = asyncio.Lock()


def _digest(session_key: str) -> str:
    raw = (session_key or "default").strip() or "default"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cohort_for(session_key: str, kind: str) -> str:
    """Stable cohort name for Google Sheet tab (ASCII, short)."""
    h = _digest(session_key)
    if kind == "tasks":
        return f"wf_tasks_{h}"
    if kind == "notes":
        return f"wf_notes_{h}"
    if kind == "chat":
        return f"wf_chat_{h}"
    raise ValueError(f"unknown workflow kind: {kind!r}")


async def _ensure_workflow_cohort(session_key: str, kind: str, description: str) -> str:
    if kind not in ("tasks", "notes", "chat"):
        raise ValueError(f"unknown workflow kind: {kind!r}")
    name = cohort_for(session_key, kind)
    async with _workflow_lock:
        existing = await catalogue.get_cohort(name)
        now = datetime.now(timezone.utc).isoformat()
        if existing is None:
            await catalogue.create_cohort(
                Cohort(
                    cohort_name=name,
                    cohort_description=description,
                    action_type="workflow_" + kind,
                    action_params=json.dumps({"session_digest": _digest(session_key)}),
                    created_at=now,
                    last_run=now,
                    sheet_name=name,
                    entry_count=0,
                )
            )
            logger.info("Created workflow cohort %s (%s)", name, kind)
    return name


async def ensure_chat_cohort(session_key: str) -> str:
    """Ensure per-session Ask-mode chat transcript sheet exists; return cohort name."""
    return await _ensure_workflow_cohort(
        session_key,
        "chat",
        "Ask-mode chat transcript (persists follow-ups per session)",
    )


async def append_item(session_key: str, kind: str, text: str) -> dict[str, Any]:
    """Append a task or note row. No LLM."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty_text", "message": "Text is required."}

    desc = "Operator tasks" if kind == "tasks" else "Operator notes"
    cohort_name = await _ensure_workflow_cohort(session_key, kind, desc)
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "workflow": kind,
        "session_digest": _digest(session_key),
    }
    entry = Entry(
        content=text,
        source="workflow",
        metadata=json.dumps(meta),
        created_at=now,
    )
    await add_entries(cohort_name, [entry])
    existing = await catalogue.get_cohort(cohort_name)
    if existing:
        new_count = existing.entry_count + 1
        await catalogue.update_cohort(cohort_name, {"last_run": now, "entry_count": new_count})

    rows = await list_cohort_entries(cohort_name, limit=500, offset=0)
    last_id = rows[-1].get("entry_id") if rows else None
    return {
        "ok": True,
        "cohort_name": cohort_name,
        "entry_id": last_id,
        "message": f"Saved to {kind} ({cohort_name}).",
    }


async def list_items(session_key: str, kind: str, limit: int = 50) -> list[dict[str, Any]]:
    name = cohort_for(session_key, kind)
    if await catalogue.get_cohort(name) is None:
        return []
    rows = await list_cohort_entries(name, limit=limit, offset=0)
    # Newest last in sheet — return reversed for UI (newest first)
    out = []
    for r in reversed(rows):
        out.append(
            {
                "entry_id": r.get("entry_id"),
                "content": r.get("content", ""),
                "created_at": r.get("created_at", ""),
            }
        )
    return out
