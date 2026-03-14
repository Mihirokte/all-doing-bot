"""SearXNG search connector implementation."""
from __future__ import annotations

from typing import Any

from apps.backend.actions.web_search import WebSearchAction
from apps.backend.connectors.base import BaseConnector
from apps.backend.db.models import Entry


class SearxngSearchConnector(BaseConnector):
    connector_id = "search_searxng"
    capability_id = "search_web"
    provider_key = "searxng"

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        return await WebSearchAction().execute(params)

