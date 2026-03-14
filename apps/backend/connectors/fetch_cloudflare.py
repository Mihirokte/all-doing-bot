"""Cloudflare-priority fetch connector implementation."""
from __future__ import annotations

from typing import Any

from apps.backend.actions.web_fetch import WebFetchAction
from apps.backend.connectors.base import BaseConnector
from apps.backend.db.models import Entry


class CloudflareFetchConnector(BaseConnector):
    connector_id = "fetch_cloudflare"
    capability_id = "web_fetch"
    provider_key = "cloudflare"

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        merged = dict(params)
        merged["provider_hint"] = "cloudflare"
        return await WebFetchAction().execute(merged)

