"""Health check for monitoring and cron."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.backend.pipeline.task_store import task_store

router = APIRouter(tags=["health"])


# Bump when HTTP surface or capability contract changes (frontend may read `api.version`).
_API_VERSION = "2026.03-api-routers"


@router.get("/health")
def health() -> dict[str, Any]:
    """Health check for monitoring and cron. `api.*` flags tell the UI which route groups exist."""
    return {
        "status": "ok",
        "api": {
            "version": _API_VERSION,
            "chat": True,
            "pipeline": True,
            "workflows": True,
            "task_store": getattr(task_store, "backend_label", "memory"),
        },
    }
