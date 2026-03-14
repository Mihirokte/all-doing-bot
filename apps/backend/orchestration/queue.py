"""Queue abstraction for step jobs; Redis-backed implementation when REDIS_URL is set."""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from apps.backend.config import settings
from apps.backend.orchestration.events import StepCompletedPayload, StepDispatchedPayload

logger = logging.getLogger(__name__)

STEP_QUEUE_KEY = "alldoing:step_queue"
STEP_RESULT_PREFIX = "alldoing:step_result:"
RESULT_TTL_SECONDS = 86400 * 2  # 2 days


class QueueBackend(ABC):
    """Abstract queue for step jobs and optional result retrieval."""

    @abstractmethod
    async def enqueue_step(self, payload: StepDispatchedPayload) -> None:
        """Push a step job for a worker."""
        ...

    @abstractmethod
    async def dequeue_step(self, timeout_seconds: float = 0) -> StepDispatchedPayload | None:
        """Pop a step job. Block up to timeout_seconds if > 0."""
        ...

    @abstractmethod
    async def set_step_result(self, run_id: str, step_index: int, payload: StepCompletedPayload) -> None:
        """Store step result so orchestrator can collect."""
        ...

    @abstractmethod
    async def get_step_result(self, run_id: str, step_index: int) -> StepCompletedPayload | None:
        """Return stored step result or None."""
        ...

    async def get_all_step_results(
        self, run_id: str, step_count: int
    ) -> list[StepCompletedPayload] | None:
        """Return list of step results if all present; else None."""
        out: list[StepCompletedPayload] = []
        for i in range(step_count):
            r = await self.get_step_result(run_id, i)
            if r is None:
                return None
            out.append(r)
        return out


class InMemoryQueueBackend(QueueBackend):
    """In-process queue (no Redis): enqueue/dequeue from a list. Step results in dict."""

    def __init__(self) -> None:
        self._steps: list[StepDispatchedPayload] = []
        self._results: dict[tuple[str, int], StepCompletedPayload] = {}

    async def enqueue_step(self, payload: StepDispatchedPayload) -> None:
        self._steps.append(payload)

    async def dequeue_step(self, timeout_seconds: float = 0) -> StepDispatchedPayload | None:
        if not self._steps:
            return None
        return self._steps.pop(0)

    async def set_step_result(self, run_id: str, step_index: int, payload: StepCompletedPayload) -> None:
        self._results[(run_id, step_index)] = payload

    async def get_step_result(self, run_id: str, step_index: int) -> StepCompletedPayload | None:
        return self._results.get((run_id, step_index))


class RedisQueueBackend(QueueBackend):
    """Redis-backed queue: LPUSH/BRPOP for step queue; hash for run step results."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Any = None

    def _client_sync(self):
        import redis
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def enqueue_step(self, payload: StepDispatchedPayload) -> None:
        import asyncio
        client = self._client_sync()
        body = payload.model_dump_json()
        await asyncio.get_event_loop().run_in_executor(None, lambda: client.lpush(STEP_QUEUE_KEY, body))

    async def dequeue_step(self, timeout_seconds: float = 0) -> StepDispatchedPayload | None:
        import asyncio
        client = self._client_sync()
        if timeout_seconds <= 0:
            raw = await asyncio.get_event_loop().run_in_executor(None, lambda: client.rpop(STEP_QUEUE_KEY))
        else:
            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.brpop(STEP_QUEUE_KEY, timeout=int(timeout_seconds))
            )
            if raw is not None and isinstance(raw, (list, tuple)):
                raw = raw[1] if len(raw) > 1 else raw
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return StepDispatchedPayload.model_validate(data)
        except Exception as e:
            logger.warning("Invalid step payload from queue: %s", e)
            return None

    def _result_key(self, run_id: str, step_index: int) -> str:
        return f"{STEP_RESULT_PREFIX}{run_id}:{step_index}"

    async def set_step_result(self, run_id: str, step_index: int, payload: StepCompletedPayload) -> None:
        import asyncio
        client = self._client_sync()
        key = self._result_key(run_id, step_index)
        body = payload.model_dump_json()
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: client.setex(key, RESULT_TTL_SECONDS, body)
        )

    async def get_step_result(self, run_id: str, step_index: int) -> StepCompletedPayload | None:
        import asyncio
        client = self._client_sync()
        key = self._result_key(run_id, step_index)
        raw = await asyncio.get_event_loop().run_in_executor(None, lambda: client.get(key))
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return StepCompletedPayload.model_validate(data)
        except Exception as e:
            logger.warning("Invalid step result in Redis: %s", e)
            return None


def _queue_available() -> bool:
    url = getattr(settings, "redis_url", None) or ""
    return bool(url and url.strip())


def get_queue() -> QueueBackend:
    """Return queue backend: Redis if REDIS_URL set, else in-memory."""
    url = getattr(settings, "redis_url", None) or ""
    if url and url.strip():
        return RedisQueueBackend(url.strip())
    return InMemoryQueueBackend()


def queue_available() -> bool:
    """True if Redis queue is configured (workers can be used)."""
    return _queue_available()
