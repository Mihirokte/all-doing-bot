"""Force MCP env before Settings() loads so tests pass even if .env omits MCP (required when provider=mcp)."""

from __future__ import annotations

import os

# Must win over .env / empty env: default provider is mcp and Settings validates non-empty argv.
os.environ["MCP_SEARCH_COMMAND_JSON"] = '["echo","all-doing-bot-test-placeholder"]'
# Keep extractor HTTP tests fast (production can set FETCH_MIN_INTERVAL_SECONDS_PER_DOMAIN=1).
os.environ.setdefault("FETCH_MIN_INTERVAL_SECONDS_PER_DOMAIN", "0")
