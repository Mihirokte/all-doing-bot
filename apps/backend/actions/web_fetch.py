"""Web fetch action: extract URL(s) via Cloudflare crawl (when set) or adapter-based cleaner."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.actions.base import BaseAction
from apps.backend.actions.cloudflare_crawl import _available as cloudflare_available, crawl_urls
from apps.backend.db.models import Entry
from apps.backend.extractor import extract_url

logger = logging.getLogger(__name__)

MAX_CONTENT_LEN = 2000
CF_CONTENT_CAP = 15000


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


class WebFetchAction(BaseAction):
    """Fetch web content, clean to markdown, return one entry per URL."""

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        urls = params.get("urls") or params.get("url")
        if isinstance(urls, str):
            urls = [urls]
        if not urls:
            # Stub: no URLs -> one placeholder entry
            return [
                Entry(
                    content="No URLs in action_params; web_fetch stub.",
                    source="",
                    metadata=_safe_json_dumps(params),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            ]
        entries: list[Entry] = []
        urls = [u for u in urls[:10] if (u or "").strip()]
        now_iso = datetime.now(timezone.utc).isoformat()
        # When Cloudflare is configured, crawl; then for any URL not in results, fall back to extract_url (partial success).
        crawl_by_url: dict[str, dict] = {}
        if cloudflare_available() and urls:
            try:
                crawl_records = await crawl_urls(urls, limit_per_url=1, formats=["markdown"], render=False)
                for rec in crawl_records:
                    url_str = (rec.get("url") or "").strip()
                    if url_str:
                        crawl_by_url[url_str.rstrip("/")] = rec
            except Exception as e:
                logger.warning("Cloudflare fetch failed, using extractor for all: %s", e)

        for url in urls:
            url_norm = url.rstrip("/")
            if url_norm in crawl_by_url:
                rec = crawl_by_url[url_norm]
                meta = rec.get("metadata") or {}
                title = meta.get("title") if isinstance(meta.get("title"), str) else ""
                markdown = (rec.get("markdown") or "")[:CF_CONTENT_CAP]
                entries.append(
                    Entry(
                        content=markdown or "(no content)",
                        source=rec.get("url") or url,
                        metadata=_safe_json_dumps({
                            "title": title,
                            "source": meta.get("source", "cloudflare_crawl"),
                            "status": meta.get("status", "completed"),
                            "url": rec.get("url") or url,
                        }),
                        created_at=now_iso,
                    )
                )
                continue
            try:
                extracted = await extract_url(url, max_chars=MAX_CONTENT_LEN)
                if extracted.items:
                    for item in extracted.items:
                        entries.append(
                            Entry(
                                content=item,
                                source=url,
                                metadata=_safe_json_dumps(
                                    {
                                        "adapter_used": extracted.adapter_used,
                                        "content_type": extracted.content_type,
                                        "title": extracted.title,
                                    }
                                ),
                                created_at=now_iso,
                            )
                        )
                else:
                    entries.append(
                        Entry(
                            content=extracted.content,
                            source=url,
                            metadata=json.dumps(
                                {
                                    "adapter_used": extracted.adapter_used,
                                    "content_type": extracted.content_type,
                                    "title": extracted.title,
                                }
                            ),
                            created_at=now_iso,
                        )
                    )
            except Exception as e:
                logger.warning("Extraction failed for %s: %s", url, e)
                entries.append(
                    Entry(
                        content=f"Error: {e}",
                        source=url,
                        metadata=_safe_json_dumps({"error": str(e)}),
                        created_at=now_iso,
                    )
                )
        return entries
