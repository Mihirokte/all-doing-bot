"""Cloudflare Browser Rendering crawl API: fetch URL(s) as Markdown (bot-friendly).

See: https://developers.cloudflare.com/browser-rendering/rest-api/crawl-endpoint/
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from apps.backend.config import settings

logger = logging.getLogger(__name__)

BASE = "https://api.cloudflare.com/client/v4/accounts"
POLL_INTERVAL = 2.0
POLL_TIMEOUT = 90.0


def _available() -> bool:
    return bool(settings.cloudflare_account_id and settings.cloudflare_api_token)


def _normalize_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Normalize a crawl record to a consistent shape: url, markdown, metadata (title, source, status)."""
    meta = rec.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    url_str = rec.get("url") or ""
    title = meta.get("title") if isinstance(meta.get("title"), str) else ""
    return {
        "url": url_str,
        "markdown": rec.get("markdown") or "",
        "metadata": {
            "title": title,
            "source": "cloudflare_crawl",
            "status": rec.get("status") or "completed",
            "url": url_str,
        },
    }


def _normalize_url_for_dedupe(url: str) -> str:
    """Normalize URL for deduplication (strip fragment, trailing slash)."""
    u = (url or "").strip()
    if u and u.endswith("/"):
        u = u[:-1]
    return u


async def _poll_until_done(job_id: str) -> dict[str, Any] | None:
    """Poll crawl job until status is not 'running'. Returns result or None on timeout/error."""
    url = f"{BASE}/{settings.cloudflare_account_id}/browser-rendering/crawl/{job_id}"
    headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}
    loop = asyncio.get_running_loop()
    started = loop.time()
    while (loop.time() - started) < POLL_TIMEOUT:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, params={"limit": 1}, headers=headers)
        except Exception as e:
            logger.warning("Cloudflare crawl GET error for job %s: %s", job_id, e)
            return None
        if r.status_code != 200:
            logger.warning("Cloudflare crawl status GET failed: %s %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            return None
        status = result.get("status")
        if status != "running":
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r2 = await client.get(url, headers=headers)
                if r2.status_code == 200:
                    data2 = r2.json()
                    return data2.get("result") if isinstance(data2, dict) else result
            except Exception as e:
                logger.warning("Cloudflare crawl full result GET error: %s", e)
            return result
        await asyncio.sleep(POLL_INTERVAL)
    logger.warning("Cloudflare crawl job %s did not complete within %s s", job_id, POLL_TIMEOUT)
    return None


async def crawl_urls(
    urls: list[str],
    *,
    limit_per_url: int = 1,
    formats: list[str] | None = None,
    render: bool = False,
) -> list[dict[str, Any]]:
    """
    Crawl one or more URLs via Cloudflare Browser Rendering.
    Each URL is started as a separate job; we wait for each with a timeout (partial success:
    one failure does not drop others). Returns list of normalized records: url, markdown, metadata.
    """
    if not _available():
        return []
    formats = formats or ["markdown"]
    headers = {
        "Authorization": f"Bearer {settings.cloudflare_api_token}",
        "Content-Type": "application/json",
    }
    post_url = f"{BASE}/{settings.cloudflare_account_id}/browser-rendering/crawl"
    job_ids: list[tuple[str, str]] = []  # (job_id, requested_url)
    for u in urls[:5]:
        u = (u or "").strip()
        if not u:
            continue
        body = {
            "url": u,
            "limit": limit_per_url,
            "formats": formats,
            "render": render,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(post_url, headers=headers, json=body)
            if r.status_code != 200:
                logger.warning("Cloudflare crawl POST failed for %s: %s %s", u, r.status_code, r.text[:200])
                continue
            data = r.json()
            jid = data.get("result") if isinstance(data, dict) else None
            if isinstance(jid, str):
                job_ids.append((jid, u))
        except Exception as e:
            logger.warning("Cloudflare crawl POST error for %s: %s", u, e)

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for jid, requested_url in job_ids:
        try:
            result = await asyncio.wait_for(_poll_until_done(jid), timeout=POLL_TIMEOUT + 5)
        except asyncio.TimeoutError:
            logger.warning("Cloudflare crawl job %s timed out", jid)
            continue
        if not result or not isinstance(result.get("records"), list):
            continue
        for rec in result["records"]:
            if not isinstance(rec, dict) or rec.get("status") != "completed":
                continue
            normalized = _normalize_record(rec)
            url_key = _normalize_url_for_dedupe(normalized["url"])
            if url_key and url_key not in seen_urls:
                seen_urls.add(url_key)
                records.append(normalized)
    return records
