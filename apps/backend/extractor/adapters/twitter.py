"""Twitter/X adapter with syndication and Nitter fallbacks."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from apps.backend.config import settings
from apps.backend.extractor.adapters.base import BaseAdapter, ExtractionResult
from apps.backend.extractor.adapters.generic import GenericAdapter
from apps.backend.extractor.fetcher import fetch_response

logger = logging.getLogger(__name__)


class TwitterAdapter(BaseAdapter):
    """Try multiple public-access methods for Twitter/X content."""

    adapter_name = "twitter"

    def can_handle(self, url: str) -> bool:
        return "twitter.com" in url or "x.com" in url

    async def _try_syndication(self, url: str, max_chars: int) -> ExtractionResult | None:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        username = parts[0] if parts else ""
        if not username:
            return None
        syndication_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
        response = await fetch_response(syndication_url)
        if response.status_code == 200 and response.text.strip():
            return await GenericAdapter().extract(syndication_url, max_chars=max_chars)
        return None

    async def _try_nitter(self, url: str, max_chars: int) -> ExtractionResult | None:
        parsed = urlparse(url)
        path = parsed.path or ""
        for instance in settings.nitter_instances:
            candidate_url = f"{instance.rstrip('/')}{path}"
            try:
                response = await fetch_response(candidate_url)
                if response.status_code == 200 and response.text.strip():
                    return await GenericAdapter().extract(candidate_url, max_chars=max_chars)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Nitter fallback failed for %s: %s", candidate_url, exc)
        return None

    async def _try_search_fallback(self, url: str, max_chars: int) -> ExtractionResult | None:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        query = parts[-1] if parts else "twitter"
        search_url = f"https://duckduckgo.com/html/?q=site%3Atwitter.com+{query}"
        try:
            result = await GenericAdapter().extract(search_url, max_chars=max_chars)
            return result if result.content_type != "error" else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("Search fallback failed: %s", exc)
            return None

    async def extract(self, url: str, max_chars: int = 2000) -> ExtractionResult:
        for method in (self._try_syndication, self._try_nitter, self._try_search_fallback):
            try:
                result = await method(url, max_chars)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Twitter access method failed for %s: %s", url, exc)
                result = None
            if result is not None:
                result.adapter_used = self.adapter_name
                return result
        return ExtractionResult(
            url=url,
            title="Twitter unavailable",
            content="[Twitter content unavailable — all access methods failed]",
            content_type="error",
            adapter_used=self.adapter_name,
        )
