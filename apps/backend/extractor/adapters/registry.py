"""Adapter registry: route URLs to the first matching adapter."""
from __future__ import annotations

import re

from apps.backend.extractor.adapters.base import BaseAdapter
from apps.backend.extractor.adapters.generic import GenericAdapter
from apps.backend.extractor.adapters.reddit import RedditAdapter
from apps.backend.extractor.adapters.twitter import TwitterAdapter

ADAPTER_REGISTRY: list[tuple[str, type[BaseAdapter]]] = [
    (r"(twitter\.com|x\.com)", TwitterAdapter),
    (r"reddit\.com", RedditAdapter),
]


def get_adapter(url: str) -> BaseAdapter:
    """Return the first matching adapter for the URL, else GenericAdapter."""
    for pattern, adapter_cls in ADAPTER_REGISTRY:
        if re.search(pattern, url, flags=re.IGNORECASE):
            adapter = adapter_cls()
            if adapter.can_handle(url):
                return adapter
    return GenericAdapter()
