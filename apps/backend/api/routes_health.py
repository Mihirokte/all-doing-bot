"""Health check for monitoring and cron."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, Any]:
    """Health check for monitoring and cron. `api.workflows` signals task/note workflow routes exist."""
    return {
        "status": "ok",
        "api": {
            "workflows": True,
            "version": "2026.03-chat-transcript",
        },
    }
