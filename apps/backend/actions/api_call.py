"""API call action: HTTP request(s) via httpx, results as entries."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from apps.backend.actions.base import BaseAction
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)

MAX_CONTENT_LEN = 50000


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


class ApiCallAction(BaseAction):
    """Perform HTTP request(s); return one Entry per response."""

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        url = params.get("url")
        urls = params.get("urls")
        if url and urls:
            urls = [url] if isinstance(url, str) else list(url)
        elif urls is not None:
            urls = [urls] if isinstance(urls, str) else list(urls)
        elif url is not None:
            urls = [url] if isinstance(url, str) else list(url)
        else:
            raise ValueError("api_call requires 'url' or 'urls' in action_params")
        method = (params.get("method") or "GET").upper()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            raise ValueError(f"api_call invalid method: {method}")
        headers = params.get("headers")
        if headers is not None and not isinstance(headers, dict):
            raise ValueError("api_call 'headers' must be a dict")
        body = params.get("body")
        entries: list[Entry] = []
        now = datetime.now(timezone.utc).isoformat()
        async with httpx.AsyncClient(timeout=30.0) as client:
            for u in urls[:20]:
                if not isinstance(u, str) or not u.strip():
                    continue
                try:
                    req = client.build_request(method, u, headers=headers, content=body)
                    resp = await client.send(req)
                    text = resp.text
                    if len(text) > MAX_CONTENT_LEN:
                        text = text[:MAX_CONTENT_LEN] + "\n... (truncated)"
                    entries.append(
                        Entry(
                            content=text,
                            source=u,
                            metadata=_safe_json_dumps({
                                "status_code": resp.status_code,
                                "headers": dict(resp.headers),
                            }),
                            created_at=now,
                        )
                    )
                except Exception as e:
                    logger.warning("api_call failed for %s: %s", u, e)
                    entries.append(
                        Entry(
                            content=f"Error: {e}",
                            source=u,
                            metadata=_safe_json_dumps({"error": str(e)}),
                            created_at=now,
                        )
                    )
        return entries
