"""Async HTTP fetch with timeout, browser-like headers, and retries."""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

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
