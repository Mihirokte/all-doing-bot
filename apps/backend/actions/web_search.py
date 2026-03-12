"""Web search action: query SearXNG JSON API, return results as entries."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from apps.backend.actions.base import BaseAction
from apps.backend.config import settings
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 5


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


class WebSearchAction(BaseAction):
    """Search the web via SearXNG; return one entry per result (title, snippet, url)."""

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        query = params.get("q") or params.get("query") or params.get("keyword") or ""
        if isinstance(query, list):
            query = query[0] if query else ""
        query = str(query).strip()
        top_n = int(params.get("top_n", DEFAULT_TOP_N))
        top_n = min(max(1, top_n), 10)

        base = settings.searxng_base_url.rstrip("/")
        url = f"{base}/search"
        payload = {"q": query, "format": "json"}

        entries: list[Entry] = []
        now = datetime.now(timezone.utc).isoformat()

        if not query:
            entries.append(
                Entry(
                    content="No search query in action_params (use 'q' or 'query' or 'keyword').",
                    source="",
                    metadata=_safe_json_dumps(params),
                    created_at=now,
                )
            )
            return entries

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.warning("SearXNG request failed: %s", e)
            entries.append(
                Entry(
                    content=f"Web search unavailable: {e}",
                    source="",
                    metadata=_safe_json_dumps({"error": str(e)}),
                    created_at=now,
                )
            )
            return entries

        results = data.get("results") if isinstance(data, dict) else []
        if not isinstance(results, list):
            results = []

        for i, item in enumerate(results[:top_n]):
            if not isinstance(item, dict):
                continue
            title = item.get("title") or ""
            url_str = item.get("url") or ""
            content_snippet = item.get("content") or ""
            content = f"**{title}**\n\n{content_snippet}".strip() or title or url_str
            entries.append(
                Entry(
                    content=content,
                    source=url_str,
                    metadata=_safe_json_dumps({"title": title, "engine": item.get("engine", "")}),
                    created_at=now,
                )
            )

        if not entries:
            entries.append(
                Entry(
                    content=f"No results for: {query}",
                    source="",
                    metadata=_safe_json_dumps(params),
                    created_at=now,
                )
            )
        return entries
