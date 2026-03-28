"""Fetcher retries and per-domain spacing."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from apps.backend.config import settings


@pytest.fixture
def reset_fetch_throttle():
    from apps.backend.extractor import fetcher

    fetcher._domain_last_fetch_mono.clear()
    yield
    fetcher._domain_last_fetch_mono.clear()


@respx.mock
def test_fetcher_spaces_requests_to_same_host(reset_fetch_throttle):
    from apps.backend.extractor import fetcher

    respx.get("https://example.com/one").mock(return_value=Response(200, text="a"))
    respx.get("https://example.com/two").mock(return_value=Response(200, text="b"))

    async def run():
        with patch.object(settings, "fetch_min_interval_seconds_per_domain", 1.0):
            t0 = time.monotonic()
            await fetcher.fetch_response("https://example.com/one")
            await fetcher.fetch_response("https://example.com/two")
            return time.monotonic() - t0

    elapsed = asyncio.run(run())
    assert elapsed >= 0.95
