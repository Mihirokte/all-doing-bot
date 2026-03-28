"""Async HTTP fetch with timeout, browser-like headers, retries, and per-host spacing."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from apps.backend.config import settings

logger = logging.getLogger(__name__)

_domain_lock = asyncio.Lock()
_domain_last_fetch_mono: dict[str, float] = {}

DEFAULT_TIMEOUT = 15.0
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_host_key(url: str) -> str | None:
    try:
        netloc = (urlparse(url).netloc or "").lower()
        if not netloc:
            return None
        return netloc.split("@")[-1]
    except Exception:  # noqa: BLE001
        return None


async def _respect_domain_interval(url: str) -> None:
    min_s = float(getattr(settings, "fetch_min_interval_seconds_per_domain", 1.0) or 0.0)
    if min_s <= 0:
        return
    host = _fetch_host_key(url)
    if not host:
        return
    loop = asyncio.get_running_loop()
    async with _domain_lock:
        now = loop.time()
        last = _domain_last_fetch_mono.get(host, 0.0)
        wait = min_s - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _domain_last_fetch_mono[host] = loop.time()


async def fetch_response(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Fetch a URL and return the response after retries."""
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=merged_headers) as client:
        for attempt in range(3):
            try:
                await _respect_domain_interval(url)
                response = await client.get(url)
                if response.status_code == 429:
                    retry_after_header = response.headers.get("Retry-After")
                    try:
                        retry_after = float(retry_after_header) if retry_after_header else 2.0 * (attempt + 1)
                    except ValueError:
                        retry_after = 2.0 * (attempt + 1)
                    await asyncio.sleep(retry_after)
                    continue
                return response
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fetch attempt %s failed for %s: %s", attempt + 1, url, exc)
                if attempt == 2:
                    raise
                await asyncio.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Fetch failed after retries for {url}")


async def fetch_url(url: str, timeout: float = DEFAULT_TIMEOUT, headers: dict[str, str] | None = None) -> str:
    """Fetch URL and return response text. Raises on HTTP error status."""
    response = await fetch_response(url, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response.text
