"""Browser automation action: dynamic page navigation and rendered extraction."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.actions.base import BaseAction
from apps.backend.actions.cloudflare_crawl import _available as cloudflare_available, crawl_urls
from apps.backend.actions.web_fetch import WebFetchAction
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)
CF_CONTENT_CAP = 20000


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


class BrowserAutomationAction(BaseAction):
    """
    First-class rendered web action.
    Uses Cloudflare Browser Rendering crawl with render=True and normalized entry output.
    Falls back to WebFetchAction when browser rendering is unavailable.
    """

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        urls = params.get("urls") or params.get("url")
        if isinstance(urls, str):
            urls = [urls]
        urls = [str(u).strip() for u in (urls or []) if str(u).strip()]
        if not urls:
            # Query-only mode: preserve contract even if planner routed too early.
            q = str(params.get("q") or params.get("query") or "").strip()
            return [
                Entry(
                    content=f"Browser automation requested without URLs. Query={q or '(empty)'}",
                    source="",
                    metadata=_safe_json_dumps({"mode": "browser_automation", "status": "missing_urls"}),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            ]

        now_iso = datetime.now(timezone.utc).isoformat()
        entries: list[Entry] = []

        if cloudflare_available():
            try:
                records = await crawl_urls(urls[:5], limit_per_url=1, formats=["markdown"], render=True)
                for rec in records:
                    url_str = (rec.get("url") or "").strip()
                    markdown = str(rec.get("markdown") or "").strip()[:CF_CONTENT_CAP]
                    meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
                    title = str(meta.get("title") or "").strip()
                    if not markdown:
                        continue
                    entries.append(
                        Entry(
                            content=markdown,
                            source=url_str or "",
                            metadata=_safe_json_dumps(
                                {
                                    "mode": "browser_automation",
                                    "rendered": True,
                                    "title": title,
                                    "source": meta.get("source", "cloudflare_crawl"),
                                    "status": meta.get("status", "completed"),
                                }
                            ),
                            created_at=now_iso,
                        )
                    )
            except Exception as e:
                logger.warning("Browser automation crawl failed, falling back to web_fetch: %s", e)

        if entries:
            return entries

        # Fallback path for environments without Cloudflare browser rendering.
        fallback_entries = await WebFetchAction().execute({"urls": urls[:5]})
        for e in fallback_entries:
            try:
                md = json.loads(e.metadata) if e.metadata else {}
            except Exception:
                md = {}
            md["mode"] = "browser_automation_fallback"
            md["rendered"] = False
            e.metadata = _safe_json_dumps(md)
        return fallback_entries
