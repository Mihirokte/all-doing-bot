"""Durable run metadata checkpoints for queue-orchestrated runs."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from apps.backend.config import settings

logger = logging.getLogger(__name__)

RUN_META_PREFIX = "alldoing:run_meta:"
RUN_META_TTL_SECONDS = 86400 * 3


def _redis_url() -> str:
    return (getattr(settings, "redis_url", None) or "").strip()


async def set_run_meta(
    run_id: str,
    *,
    query: str = "",
    step_count: int = 0,
    parsed_json: str = "",
    plan_json: str = "",
    status: str = "processing",
) -> None:
    """Persist run checkpoint metadata (no-op when Redis is not configured)."""
    url = _redis_url()
    if not url:
        return
    import redis

    payload = {
        "run_id": run_id,
        "query": query,
        "step_count": step_count,
        "parsed_json": parsed_json,
        "plan_json": plan_json,
        "status": status,
    }
    key = f"{RUN_META_PREFIX}{run_id}"
    client = redis.from_url(url, decode_responses=True)
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: client.setex(key, RUN_META_TTL_SECONDS, json.dumps(payload)),
    )


async def get_run_meta(run_id: str) -> dict[str, Any] | None:
    """Load run metadata checkpoint (returns None when absent)."""
    url = _redis_url()
    if not url:
        return None
    import redis

    key = f"{RUN_META_PREFIX}{run_id}"
    client = redis.from_url(url, decode_responses=True)
    raw = await asyncio.get_event_loop().run_in_executor(None, lambda: client.get(key))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Invalid run_meta for run_id=%s: %s", run_id, exc)
        return None


async def update_run_status(run_id: str, status: str) -> None:
    """Update run status in checkpoint metadata."""
    meta = await get_run_meta(run_id)
    if not meta:
        return
    await set_run_meta(
        run_id,
        query=str(meta.get("query", "")),
        step_count=int(meta.get("step_count", 0) or 0),
        parsed_json=str(meta.get("parsed_json", "")),
        plan_json=str(meta.get("plan_json", "")),
        status=status,
    )


def run_state_backend() -> str:
    """Simple label for current run state backend."""
    return "redis" if _redis_url() else "in_memory"
