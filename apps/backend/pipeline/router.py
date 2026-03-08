"""Query routing and async pipeline runner."""
from __future__ import annotations

import logging

from apps.backend.pipeline.executor import run_full_pipeline
from apps.backend.pipeline.task_store import task_store

logger = logging.getLogger(__name__)


async def run_pipeline(task_id: str, query: str) -> None:
    """Run the full pipeline: Parse -> Plan -> Execute -> Store."""
    await run_full_pipeline(task_id, query)
