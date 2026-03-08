"""Web content extraction: fetch URLs, route through adapters, and cache results."""
from apps.backend.extractor.adapters import ExtractionResult, GenericAdapter, RedditAdapter, TwitterAdapter, get_adapter
from apps.backend.extractor.cache import (
    clear_cache,
    get_cached_extraction,
    get_cached_markdown,
    set_cached_extraction,
    set_cached_markdown,
)
from apps.backend.extractor.cleaner import extract_url, html_to_markdown
from apps.backend.extractor.fetcher import fetch_response, fetch_url

__all__ = [
    "ExtractionResult",
    "GenericAdapter",
    "RedditAdapter",
    "TwitterAdapter",
    "clear_cache",
    "extract_url",
    "fetch_response",
    "fetch_url",
    "get_adapter",
    "get_cached_extraction",
    "get_cached_markdown",
    "html_to_markdown",
    "set_cached_extraction",
    "set_cached_markdown",
]
