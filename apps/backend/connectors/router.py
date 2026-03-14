"""Connector router for capability/provider selection."""
from __future__ import annotations

from typing import Any

from apps.backend.actions.browser_automation import BrowserAutomationAction
from apps.backend.actions.cloudflare_crawl import _available as cloudflare_available
from apps.backend.config import settings
from apps.backend.connectors.base import BaseConnector
from apps.backend.connectors.fetch_cloudflare import CloudflareFetchConnector
from apps.backend.connectors.fetch_extractor import ExtractorFetchConnector
from apps.backend.connectors.search_searxng import SearxngSearchConnector
from apps.backend.db.models import Entry


class BrowserAutomationConnector(BaseConnector):
    connector_id = "browser_automation_core"
    capability_id = "browser_automation"
    provider_key = "cloudflare_browser" if cloudflare_available() else "fallback_fetch"

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        return await BrowserAutomationAction().execute(params)


class ConnectorRouter:
    """Select and execute connector providers by capability."""

    def __init__(self) -> None:
        self._connectors: dict[str, list[BaseConnector]] = {
            "search_web": [SearxngSearchConnector()],
            "web_fetch": [CloudflareFetchConnector(), ExtractorFetchConnector()],
            "browser_automation": [BrowserAutomationConnector()],
        }

    def resolve(self, capability_id: str, params: dict[str, Any]) -> BaseConnector | None:
        options = self._connectors.get(capability_id, [])
        if not options:
            return None
        provider_hint = str(params.get("provider_hint") or "").strip().lower()
        if provider_hint:
            for connector in options:
                if connector.provider_key == provider_hint or connector.connector_id == provider_hint:
                    return connector
        default_provider = self._default_provider_for(capability_id)
        if default_provider:
            for connector in options:
                if connector.provider_key == default_provider or connector.connector_id == default_provider:
                    return connector
        if capability_id == "web_fetch" and cloudflare_available():
            for connector in options:
                if connector.provider_key == "cloudflare":
                    return connector
        return options[0]

    async def execute(self, capability_id: str, params: dict[str, Any]) -> tuple[list[Entry], str | None, str | None]:
        connector = self.resolve(capability_id, params)
        if connector is None:
            return [], None, None
        return await connector.execute(params), connector.connector_id, connector.provider_key

    def route_metadata(self, capability_id: str, params: dict[str, Any]) -> tuple[str | None, str | None]:
        connector = self.resolve(capability_id, params)
        if connector is None:
            return None, None
        return connector.connector_id, connector.provider_key

    @staticmethod
    def _default_provider_for(capability_id: str) -> str:
        defaults = {
            "search_web": str(getattr(settings, "connector_search_default_provider", "searxng")),
            "web_fetch": str(getattr(settings, "connector_fetch_default_provider", "cloudflare")),
            "browser_automation": str(getattr(settings, "connector_browser_default_provider", "cloudflare_browser")),
        }
        return defaults.get(capability_id, "").strip().lower()


connector_router = ConnectorRouter()

