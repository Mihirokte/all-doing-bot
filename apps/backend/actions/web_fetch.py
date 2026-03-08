"""Web fetch action: extract URL(s) through adapter-based cleaner, return entries."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.actions.base import BaseAction
from apps.backend.db.models import Entry
from apps.backend.extractor import extract_url

logger = logging.getLogger(__name__)

MAX_CONTENT_LEN = 2000


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
        for url in urls[:10]:  # cap at 10
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
                                created_at=datetime.now(timezone.utc).isoformat(),
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
                            created_at=datetime.now(timezone.utc).isoformat(),
                        )
                    )
            except Exception as e:
                logger.warning("Extraction failed for %s: %s", url, e)
                entries.append(
                    Entry(
                        content=f"Error: {e}",
                        source=url,
                        metadata=_safe_json_dumps({"error": str(e)}),
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
        return entries
