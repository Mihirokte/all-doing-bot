"""Redis-backed task store for shared /status across API replicas (optional)."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from apps.backend.config import settings
from apps.backend.models.schemas import TaskResult, TaskStatusResponse

logger = logging.getLogger(__name__)

TASK_HASH_KEY = "alldoing:tasks"
TASK_RETENTION_SECONDS = 3600


class RedisTaskStore:
    """Hash alldoing:tasks field=task_id value=json — same contract as TaskStore."""

    def __init__(self, redis_url: str) -> None:
        import redis as redis_mod

        self._url = redis_url
        self._r = redis_mod.from_url(redis_url, decode_responses=True)
        self._r.ping()

    def _client(self) -> Any:
        return self._r

    def task_count(self) -> int:
        return int(self._client().hlen(TASK_HASH_KEY))

    def create(self, query: str, session_key: str = "default") -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        blob = {
            "task_id": task_id,
            "status": "accepted",
            "query": query,
            "session_key": session_key or "default",
            "result": None,
            "created_at": now,
            "updated_at": now,
        }
        self._client().hset(TASK_HASH_KEY, task_id, json.dumps(blob))
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        raw = self._client().hget(TASK_HASH_KEY, task_id)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def get_response(self, task_id: str) -> TaskStatusResponse | None:
        t = self.get(task_id)
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

    def _save(self, task_id: str, t: dict[str, Any]) -> None:
        self._client().hset(TASK_HASH_KEY, task_id, json.dumps(t))

    def set_status(self, task_id: str, status: str, result: TaskResult | dict | None = None) -> None:
        t = self.get(task_id)
        if not t:
            return
        t["status"] = status
        t["updated_at"] = datetime.now(timezone.utc).isoformat()
        if result is not None:
            t["result"] = result.model_dump() if isinstance(result, TaskResult) else result
        self._save(task_id, t)

    def set_result(self, task_id: str, result: TaskResult | dict) -> None:
        self.set_status(task_id, "completed", result=result)

    def set_failed(self, task_id: str, error: str) -> None:
        self.set_status(
            task_id,
            "failed",
            result=TaskResult(error=error, message=error),
        )

    def set_expired(self, task_id: str) -> None:
        self.set_status(
            task_id,
            "expired",
            result=TaskResult(error="Task expired", message="Task expired after retention period"),
        )

    def cleanup_old(self) -> None:
        """Match in-memory TaskStore.cleanup_old semantics."""
        now = time.time()
        to_expire: list[str] = []
        client = self._client()
        for task_id, raw in list(client.hgetall(TASK_HASH_KEY).items()):
            try:
                t = json.loads(raw)
            except json.JSONDecodeError:
                client.hdel(TASK_HASH_KEY, task_id)
                continue
            if t["status"] in ("processing", "accepted"):
                continue
            if t["status"] == "expired":
                try:
                    updated_ts = datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00")).timestamp()
                    if (now - updated_ts) > TASK_RETENTION_SECONDS * 2:
                        to_expire.append(task_id)
                except (ValueError, KeyError):
                    pass
                continue
            if t["status"] not in ("completed", "failed"):
                continue
            try:
                updated_ts = datetime.fromisoformat(t["updated_at"].replace("Z", "+00:00")).timestamp()
                if (now - updated_ts) > TASK_RETENTION_SECONDS:
                    to_expire.append(task_id)
            except (ValueError, KeyError):
                pass
        for tid in to_expire:
            t = self.get(tid)
            if t and t["status"] == "expired":
                client.hdel(TASK_HASH_KEY, tid)
            elif t:
                self.set_expired(tid)
        if to_expire:
            logger.debug("Cleaned up %d old tasks (redis)", len(to_expire))

    async def acreate(self, query: str, session_key: str = "default") -> str:
        return self.create(query, session_key)

    async def aset_status(self, task_id: str, status: str, result: TaskResult | dict | None = None) -> None:
        self.set_status(task_id, status, result)

    async def aget(self, task_id: str) -> dict[str, Any] | None:
        return self.get(task_id)

    async def acleanup_old(self) -> None:
        self.cleanup_old()

    def clear_all(self) -> int:
        n = self.task_count()
        self._client().delete(TASK_HASH_KEY)
        return n

    @property
    def backend_label(self) -> str:
        return "redis"


def try_redis_task_store() -> RedisTaskStore | None:
    try:
        import redis  # noqa: F401 — package required for RedisTaskStore; optional install for tests/CI without deps
    except ImportError:
        logger.debug("redis package not installed; task store stays in-memory")
        return None
    url = (getattr(settings, "redis_url", None) or "").strip()
    if not url:
        return None
    try:
        store = RedisTaskStore(url)
        logger.info("Task store: Redis (%s)", TASK_HASH_KEY)
        return store
    except Exception as e:
        logger.warning("Redis task store unavailable, using in-memory: %s", e)
        return None
