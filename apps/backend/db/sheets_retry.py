"""Retry with exponential backoff for transient Google Sheets / gspread failures."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from apps.backend.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_HTTP = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def is_retryable_sheets_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    try:
        from gspread.exceptions import APIError

        if isinstance(exc, APIError):
            resp = getattr(exc, "response", None)
            code = getattr(resp, "status_code", None)
            if code is not None:
                try:
                    return int(code) in _RETRYABLE_HTTP
                except (TypeError, ValueError):
                    pass
    except ImportError:
        pass
    lowered = str(exc).lower()
    return any(
        token in lowered
        for token in (
            "429",
            "500",
            "502",
            "503",
            "504",
            "rate limit",
            "quota",
            "timeout",
            "temporarily unavailable",
            "service unavailable",
        )
    )


async def run_sync_with_retry(
    fn: Callable[..., T],
    /,
    *args: Any,
    operation: str = "sheets",
    **kwargs: Any,
) -> T:
    max_attempts = max(1, int(getattr(settings, "google_sheets_retry_attempts", 3) or 3))
    base_delay = float(getattr(settings, "google_sheets_retry_base_delay_seconds", 1.0) or 1.0)
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as e:
            last = e
            if attempt >= max_attempts or not is_retryable_sheets_error(e):
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "%s failed (attempt %s/%s), retrying in %.1fs: %s",
                operation,
                attempt,
                max_attempts,
                delay,
                e,
            )
            await asyncio.sleep(delay)
    assert last is not None
    raise last
