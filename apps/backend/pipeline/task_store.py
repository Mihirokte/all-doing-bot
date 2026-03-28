"""In-memory task state. Single user, ephemeral across restarts."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from apps.backend.models.schemas import TaskResult, TaskStatusResponse

logger = logging.getLogger(__name__)

# Completed tasks older than this (seconds) are removed on cleanup
TASK_RETENTION_SECONDS = 3600


class TaskStore:
    """In-memory store: task_id -> task state."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def create(self, query: str, session_key: str = "default") -> str:
        """Create a new task, return task_id."""
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._tasks[task_id] = {
            "task_id": task_id,
            "status": "accepted",
            "query": query,
            "session_key": session_key or "default",
            "result": None,
            "created_at": now,
            "updated_at": now,
        }
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Return raw task dict or None."""
        return self._tasks.get(task_id)

    def get_response(self, task_id: str) -> TaskStatusResponse | None:
        """Return task as TaskStatusResponse or None."""
        t = self._tasks.get(task_id)
        if not t:
            return None
        result = t.get("result")
        if result is not None and isinstance(result, dict):
            result = TaskResult(**result)
        elif result is not None and isinstance(result, TaskResult):
            pass
        else:
            result = None
        try:
            created_at = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")) if t.get("created_at") else None
        except (ValueError, AttributeError):
            created_at = None
        try:
            updated_at = datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00")) if t.get("updated_at") else None
        except (ValueError, AttributeError):
            updated_at = None
        return TaskStatusResponse(
            task_id=t["task_id"],
            status=t["status"],
            query=t.get("query"),
            session_key=t.get("session_key"),
            result=result,
            created_at=created_at,
            updated_at=updated_at,
        )

    def set_status(self, task_id: str, status: str, result: TaskResult | dict | None = None) -> None:
        """Update status and optionally result."""
        if task_id not in self._tasks:
            return
        self._tasks[task_id]["status"] = status
        self._tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        if result is not None:
            self._tasks[task_id]["result"] = result.model_dump() if isinstance(result, TaskResult) else result

    def set_result(self, task_id: str, result: TaskResult | dict) -> None:
        """Set result and mark completed."""
        self.set_status(task_id, "completed", result=result)

    def set_failed(self, task_id: str, error: str) -> None:
        """Mark task as failed with error message."""
        self.set_status(
            task_id,
            "failed",
            result=TaskResult(error=error, message=error),
        )

    def set_expired(self, task_id: str) -> None:
        """Mark task as expired instead of deleting, so the frontend gets a meaningful status."""
        self.set_status(
            task_id,
            "expired",
            result=TaskResult(error="Task expired", message="Task expired after retention period"),
        )

    def cleanup_old(self) -> None:
        """Mark old completed/failed/expired tasks as expired. Never removes processing or accepted tasks."""
        now = time.time()
        to_expire: list[str] = []
        for tid, t in list(self._tasks.items()):  # snapshot to avoid mutation-during-iteration
            if t["status"] in ("processing", "accepted"):
                continue
            if t["status"] == "expired":
                # Already expired; remove if well past retention
                try:
                    updated_ts = datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00")).timestamp()
                    if (now - updated_ts) > TASK_RETENTION_SECONDS * 2:
                        to_expire.append(tid)
                except (ValueError, KeyError):
                    pass
                continue
            if t["status"] not in ("completed", "failed"):
                continue
            try:
                updated_ts = datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00")).timestamp()
                if (now - updated_ts) > TASK_RETENTION_SECONDS:
                    to_expire.append(tid)
            except (ValueError, KeyError):
                pass
        for tid in to_expire:
            t = self._tasks.get(tid)
            if t and t["status"] == "expired":
                # Already expired and past 2x retention, safe to delete
                del self._tasks[tid]
            elif t:
                self.set_expired(tid)
        if to_expire:
            logger.debug("Cleaned up %d old tasks", len(to_expire))

    async def acreate(self, query: str, session_key: str = "default") -> str:
        """Async-safe create: acquires lock before mutating _tasks."""
        async with self._lock:
            return self.create(query, session_key)

    async def aset_status(self, task_id: str, status: str, result: TaskResult | dict | None = None) -> None:
        """Async-safe set_status."""
        async with self._lock:
            self.set_status(task_id, status, result)

    async def aget(self, task_id: str) -> dict[str, Any] | None:
        """Async-safe get."""
        async with self._lock:
            return self.get(task_id)

    async def acleanup_old(self) -> None:
        """Async-safe cleanup_old."""
        async with self._lock:
            self.cleanup_old()

    def clear_all(self) -> int:
        """Clear all in-memory task sessions. Returns number removed."""
        count = len(self._tasks)
        self._tasks.clear()
        return count


task_store = TaskStore()
