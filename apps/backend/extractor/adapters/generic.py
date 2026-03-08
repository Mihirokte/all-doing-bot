"""Generic adapter using readability-lxml with BeautifulSoup fallback."""
from __future__ import annotations

import logging
import re
from bs4 import BeautifulSoup

from apps.backend.extractor.adapters.base import BaseAdapter, ExtractionResult
from apps.backend.extractor.fetcher import fetch_response

logger = logging.getLogger(__name__)


def smart_truncate(text: str, max_chars: int) -> str:
    """Trim at a sentence or newline boundary before max_chars."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= max_chars:
        return text
    chunk = text[: max_chars + 1]
    candidates = [chunk.rfind("."), chunk.rfind("!"), chunk.rfind("?"), chunk.rfind("\n")]
    cut = max(candidates)
    if cut > max_chars // 2:
        return chunk[: cut + 1].strip()
    return chunk[:max_chars].strip()


def html_to_markdown(html: str, max_chars: int = 2000) -> str:
    """Convert HTML into markdown-ish plain text with readability fallback."""
    cleaned_html = html
    soup_for_cleanup = BeautifulSoup(cleaned_html, "lxml")
    for tag in soup_for_cleanup(["script", "style", "nav", "footer", "aside", "iframe", "noscript"]):
        tag.decompose()
    cleaned_html = str(soup_for_cleanup)

    title = ""
    content_html = ""
    try:
        from readability import Document

        doc = Document(cleaned_html)
        title = doc.short_title() or ""
        content_html = doc.summary() or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("Readability failed: %s", exc)

    if len(re.sub(r"<[^>]+>", "", content_html).strip()) < 100:
        soup = BeautifulSoup(cleaned_html, "lxml")
        title = title or (soup.title.string.strip() if soup.title and soup.title.string else "")
        for tag in soup(["script", "style", "nav", "footer", "aside", "iframe", "noscript"]):
            tag.decompose()
        body = soup.body or soup
        content_html = str(body)

    try:
        from markdownify import markdownify as md

        text = md(content_html, heading_style="ATX")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Markdownify failed: %s", exc)
        text = re.sub(r"<[^>]+>", " ", content_html)
        text = re.sub(r"\s+", " ", text).strip()
    return smart_truncate(text, max_chars)


def _extract_list_items(soup: BeautifulSoup, max_chars: int) -> list[str]:
    candidates = soup.find_all(["li", "article"])
    items: list[str] = []
    for candidate in candidates[:20]:
        text = candidate.get_text(" ", strip=True)
        if len(text) >= 20:
            items.append(smart_truncate(text, max_chars // 4))
    return items


class GenericAdapter(BaseAdapter):
    """Catch-all adapter for article pages and generic HTML."""

    adapter_name = "generic"

    def can_handle(self, url: str) -> bool:
        return True

    async def extract(self, url: str, max_chars: int = 2000) -> ExtractionResult:
        response = await fetch_response(url)
        if response.status_code in (403, 429, 503):
            return ExtractionResult(
                url=url,
                title="Blocked",
                content=f"[Blocked: HTTP {response.status_code}]",
                content_type="error",
                adapter_used=self.adapter_name,
                metadata={"status_code": response.status_code},
            )

        html = response.text
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        list_items = _extract_list_items(soup, max_chars)
        if len(list_items) >= 5:
            return ExtractionResult(
                url=url,
                title=title,
                content="",
                content_type="feed",
                items=list_items,
                adapter_used=self.adapter_name,
            )

        content = html_to_markdown(html, max_chars=max_chars)
        content_type = "article" if content else "error"
        return ExtractionResult(
            url=url,
            title=title,
            content=content,
            content_type=content_type,
            adapter_used=self.adapter_name,
        )
