"""In-memory URL -> extracted content cache with TTL (default 1 hour)."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3600
MAX_CACHE_SIZE = 500
_cache: dict[str, tuple[Any, float]] = {}
_ttl = DEFAULT_TTL_SECONDS


def _key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def get_cached_markdown(url: str) -> str | None:
    """Backward-compatible markdown getter."""
    cached = get_cached_extraction(url)
    return cached if isinstance(cached, str) else None


def get_cached_extraction(url: str) -> Any | None:
    """Return cached extraction payload for URL if present and not expired."""
    k = _key(url)
    if k not in _cache:
        return None
    value, ts = _cache[k]
    if (time.time() - ts) > _ttl:
        del _cache[k]
        return None
    return value


def set_cached_markdown(url: str, markdown: str) -> None:
    """Store markdown for URL."""
    set_cached_extraction(url, markdown)


def set_cached_extraction(url: str, payload: Any) -> None:
    """Store arbitrary extraction payload for URL."""
    if len(_cache) >= MAX_CACHE_SIZE:
        oldest_key = min(_cache, key=lambda k: _cache[k][1])
        del _cache[oldest_key]
    _cache[_key(url)] = (payload, time.time())


def clear_cache() -> None:
    """Clear the in-memory extractor cache. Used by tests."""
    _cache.clear()
