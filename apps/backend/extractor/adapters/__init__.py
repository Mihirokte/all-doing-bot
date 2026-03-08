"""Site-specific extraction adapters."""
from apps.backend.extractor.adapters.base import BaseAdapter, ExtractionResult
from apps.backend.extractor.adapters.generic import GenericAdapter, html_to_markdown, smart_truncate
from apps.backend.extractor.adapters.reddit import RedditAdapter
from apps.backend.extractor.adapters.registry import get_adapter
from apps.backend.extractor.adapters.twitter import TwitterAdapter

__all__ = [
    "BaseAdapter",
    "ExtractionResult",
    "GenericAdapter",
    "RedditAdapter",
    "TwitterAdapter",
    "get_adapter",
    "html_to_markdown",
    "smart_truncate",
]
