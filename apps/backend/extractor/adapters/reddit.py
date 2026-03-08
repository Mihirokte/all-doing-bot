"""Reddit adapter using the free .json endpoint."""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from apps.backend.extractor.adapters.base import BaseAdapter, ExtractionResult
from apps.backend.extractor.fetcher import fetch_response


class RedditAdapter(BaseAdapter):
    """Extract Reddit post and listing content from the JSON endpoint."""

    adapter_name = "reddit"

    def can_handle(self, url: str) -> bool:
        return "reddit.com" in url

    def _json_url(self, url: str) -> str:
        parts = urlsplit(url)
        path = parts.path if parts.path.endswith(".json") else f"{parts.path.rstrip('/')}.json"
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    async def extract(self, url: str, max_chars: int = 2000) -> ExtractionResult:
        headers = {"User-Agent": "all-doing-bot/1.0 (reddit adapter)"}
        response = await fetch_response(self._json_url(url), headers=headers)
        if response.status_code in (403, 429, 503):
            return ExtractionResult(
                url=url,
                title="Reddit unavailable",
                content=f"[Blocked: HTTP {response.status_code}]",
                content_type="error",
                adapter_used=self.adapter_name,
                metadata={"status_code": response.status_code},
            )

        try:
            data = response.json()
        except Exception:
            return ExtractionResult(
                url=url,
                title="Reddit error",
                content="[Invalid JSON response from Reddit API]",
                content_type="error",
                adapter_used=self.adapter_name,
            )
        items: list[str] = []
        title = "Reddit"

        def add_item(post_data: dict) -> None:
            nonlocal title
            post_title = post_data.get("title") or post_data.get("link_title") or "Untitled"
            title = title if title != "Reddit" else post_title
            body = post_data.get("selftext") or post_data.get("body") or ""
            score = post_data.get("score", 0)
            comments = post_data.get("num_comments", 0)
            items.append(f"{post_title}\n\n{body}\n\nscore={score} comments={comments}".strip())

        if isinstance(data, list):
            for block in data:
                for child in block.get("data", {}).get("children", []):
                    if isinstance(child, dict):
                        add_item(child.get("data", {}))
        elif isinstance(data, dict):
            for child in data.get("data", {}).get("children", []):
                if isinstance(child, dict):
                    add_item(child.get("data", {}))

        return ExtractionResult(
            url=url,
            title=title,
            content="",
            content_type="feed",
            items=items[:20],
            adapter_used=self.adapter_name,
        )
