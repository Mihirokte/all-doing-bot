"""MCP-backed search connector (stdio server)."""
from __future__ import annotations

from typing import Any

from apps.backend.connectors.base import BaseConnector
from apps.backend.db.models import Entry
from apps.backend.mcp.web_search_mcp import search_via_mcp


class McpSearchConnector(BaseConnector):
    connector_id = "search_mcp"
    capability_id = "search_web"
    provider_key = "mcp"

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        q = params.get("q") or params.get("query") or params.get("keyword") or ""
        if isinstance(q, list):
            q = q[0] if q else ""
        q = str(q).strip()
        top_n = int(params.get("top_n", 5))
        top_n = min(max(1, top_n), 10)
        return await search_via_mcp(q, top_n)
