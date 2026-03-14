"""Extractor-only fetch connector implementation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from apps.backend.connectors.base import BaseConnector
from apps.backend.db.models import Entry
from apps.backend.extractor import extract_url

MAX_CONTENT_LEN = 2000


class ExtractorFetchConnector(BaseConnector):
    connector_id = "fetch_extractor"
    capability_id = "web_fetch"
    provider_key = "extractor"

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        urls = params.get("urls") or params.get("url")
        if isinstance(urls, str):
            urls = [urls]
        urls = [str(u).strip() for u in (urls or []) if str(u).strip()]
        if not urls:
            return []
        now = datetime.now(timezone.utc).isoformat()
        entries: list[Entry] = []
        for url in urls[:10]:
            extracted = await extract_url(url, max_chars=MAX_CONTENT_LEN)
            if extracted.items:
                for item in extracted.items:
                    entries.append(
                        Entry(
                            content=item,
                            source=url,
                            metadata=json.dumps(
                                {
                                    "adapter_used": extracted.adapter_used,
                                    "content_type": extracted.content_type,
                                    "title": extracted.title,
                                    "provider": "extractor",
                                }
                            ),
                            created_at=now,
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
                                "provider": "extractor",
                            }
                        ),
                        created_at=now,
                    )
                )
        return entries

