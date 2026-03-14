"""Query routing and async pipeline runner."""
from __future__ import annotations

import logging

from apps.backend.orchestration.gateway import gateway_scheduler
from apps.backend.pipeline.executor import run_full_pipeline

logger = logging.getLogger(__name__)


async def run_pipeline(task_id: str, query: str, session_key: str = "default") -> None:
    """Run full pipeline directly (used in tests and direct execution paths)."""
    await run_full_pipeline(task_id, query, session_key=session_key)


async def enqueue_pipeline(task_id: str, query: str, session_key: str = "default") -> None:
    """Enqueue pipeline run into the gateway scheduler by session lane."""
    await gateway_scheduler.enqueue(task_id=task_id, query=query, session_key=session_key)
