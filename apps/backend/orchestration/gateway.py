"""Gateway scheduler: session-key lanes with serial-per-session execution."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from apps.backend.pipeline.executor import run_full_pipeline
from apps.backend.telemetry import log_run_event

logger = logging.getLogger(__name__)


@dataclass
class RunJob:
    task_id: str
    query: str
    session_key: str


class SessionLane:
    """Single sequential queue per session key (OpenClaw-style lane semantics)."""

    def __init__(self, session_key: str) -> None:
        self.session_key = session_key
        self.queue: asyncio.Queue[RunJob] = asyncio.Queue()
        self.worker_task: asyncio.Task | None = None
        self.running = False

    async def enqueue(self, job: RunJob) -> None:
        await self.queue.put(job)


class GatewayScheduler:
    """Multi-ingress, single-kernel scheduler with per-session serial lanes."""

    def __init__(self) -> None:
        self._lanes: dict[str, SessionLane] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, task_id: str, query: str, session_key: str) -> None:
        key = (session_key or "default").strip() or "default"
        async with self._lock:
            lane = self._lanes.get(key)
            if lane is None:
                lane = SessionLane(key)
                self._lanes[key] = lane
                lane.worker_task = asyncio.create_task(self._run_lane(lane))
            await lane.enqueue(RunJob(task_id=task_id, query=query, session_key=key))
            log_run_event("lane_enqueued", run_id=task_id, stage="gateway", session_key=key, queue_size=lane.queue.qsize())

    async def _run_lane(self, lane: SessionLane) -> None:
        lane.running = True
        logger.info("Gateway lane started: session_key=%s", lane.session_key)
        while True:
            job = await lane.queue.get()
            try:
                log_run_event("lane_processing", run_id=job.task_id, stage="gateway", session_key=lane.session_key)
                await run_full_pipeline(job.task_id, job.query, session_key=job.session_key)
            except Exception as e:  # noqa: BLE001
                logger.exception("Lane run failed session_key=%s task_id=%s: %s", lane.session_key, job.task_id, e)
            finally:
                lane.queue.task_done()


gateway_scheduler = GatewayScheduler()
