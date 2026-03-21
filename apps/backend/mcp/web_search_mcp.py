"""Invoke web search through a user-provided MCP server (stdio). No vendor search REST APIs."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.config import settings
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


def _text_from_mcp_result(result: Any) -> str:
    """Extract plain text from mcp.types.CallToolResult."""
    parts: list[str] = []
    content = getattr(result, "content", None) or []
    for block in content:
        t = getattr(block, "text", None)
        if t:
            parts.append(str(t))
        else:
            parts.append(str(block))
    return "\n".join(parts).strip()


async def search_via_mcp(query: str, top_n: int) -> list[Entry]:
    """Call configured MCP tool; normalize to Entry list."""
    now = datetime.now(timezone.utc).isoformat()
    argv = settings.mcp_search_argv
    if not argv:
        return [
            Entry(
                content="MCP search not configured. Set MCP_SEARCH_COMMAND_JSON to a JSON array of command argv "
                "(e.g. [\"npx\",\"-y\",\"your-mcp-server\"]) and CONNECTOR_SEARCH_DEFAULT_PROVIDER=mcp.",
                source="",
                metadata=_safe_json_dumps({"error": "mcp_not_configured"}),
                created_at=now,
            )
        ]

    tool_name = (settings.mcp_search_tool_name or "search").strip() or "search"
    param = (settings.mcp_search_query_param or "query").strip() or "query"
    args = {param: query, "top_n": top_n}

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        logger.warning("Python mcp package missing: %s", e)
        return [
            Entry(
                content="Install the `mcp` package (see requirements.txt) to use MCP search.",
                source="",
                metadata=_safe_json_dumps({"error": "mcp_import"}),
                created_at=now,
            )
        ]

    cmd = argv[0]
    cmd_args = argv[1:] if len(argv) > 1 else []
    server_params = StdioServerParameters(command=cmd, args=cmd_args, env=None)

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
    except Exception as e:  # noqa: BLE001
        logger.warning("MCP search failed: %s", e)
        return [
            Entry(
                content=f"MCP search failed: {e}",
                source="",
                metadata=_safe_json_dumps({"error": str(e)}),
                created_at=now,
            )
        ]

    text = _text_from_mcp_result(result)
    if not text:
        return [
            Entry(
                content="MCP search returned no text. Check MCP_SEARCH_TOOL_NAME and tool arguments.",
                source="",
                metadata=_safe_json_dumps({"tool": tool_name}),
                created_at=now,
            )
        ]

    # Single blob entry; pipeline / chat can still consume it. Optional: split JSON array of results later.
    return [
        Entry(
            content=text[:8000] if len(text) > 8000 else text,
            source="mcp:" + tool_name,
            metadata=_safe_json_dumps({"tool": tool_name, "truncated": len(text) > 8000}),
            created_at=now,
        )
    ]
