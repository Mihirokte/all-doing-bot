"""Force MCP env before Settings() loads so tests pass even if .env omits MCP (required when provider=mcp)."""

from __future__ import annotations

import os

# Must win over .env / empty env: default provider is mcp and Settings validates non-empty argv.
os.environ["MCP_SEARCH_COMMAND_JSON"] = '["echo","all-doing-bot-test-placeholder"]'
