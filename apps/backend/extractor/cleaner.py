"""Cleaner orchestrator: pick adapter, extract content, and cache results."""
from __future__ import annotations

from apps.backend.extractor.adapters.base import ExtractionResult
from apps.backend.extractor.adapters.generic import html_to_markdown
from apps.backend.extractor.adapters.registry import get_adapter
from apps.backend.extractor.cache import get_cached_extraction, set_cached_extraction

MAX_MARKDOWN_CHARS = 2000


async def extract_url(url: str, max_chars: int = MAX_MARKDOWN_CHARS) -> ExtractionResult:
    """Extract a URL via the appropriate adapter, with cache lookup."""
    cached = get_cached_extraction(url)
    if isinstance(cached, ExtractionResult):
        return cached
    adapter = get_adapter(url)
    result = await adapter.extract(url, max_chars=max_chars)
    set_cached_extraction(url, result)
    return result
