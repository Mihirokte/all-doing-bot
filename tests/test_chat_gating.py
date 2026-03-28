"""Chat heuristic dedupe and routing helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def test_chat_looks_like_search_reviews() -> None:
    from apps.backend.main import _chat_looks_like_search

    assert _chat_looks_like_search("rotten tomatoes reviews dhurandhar 2")
    assert _chat_looks_like_search("tell me the reviews")
    assert not _chat_looks_like_search("hi")


def test_dedupe_entries_by_source() -> None:
    from apps.backend.main import _dedupe_entries_by_source

    a = MagicMock(source="https://example.com/page", content="one")
    b = MagicMock(source="https://example.com/page#frag", content="two")
    c = MagicMock(source="https://other.test/", content="three")
    out = _dedupe_entries_by_source([a, b, c], max_keep=10)
    assert len(out) == 2


def test_chat_search_disabled_returns_explicit_message() -> None:
    from apps.backend.main import app
    from apps.backend.config import settings

    with patch.object(settings, "chat_web_search_enabled", False):
        client = TestClient(app)
        r = client.get("/chat", params={"q": "reviews of mystery movie 2099"})
    assert r.status_code == 200
    data = r.json()
    assert "CHAT_WEB_SEARCH_ENABLED" in (data.get("response") or "")


def test_chat_gate_clarification_when_ask_user_first() -> None:
    from apps.backend.models.schemas import ChatWebRoute
    from apps.backend.main import app

    mock_route = ChatWebRoute(
        needs_web=False,
        ask_user_first=True,
        ask_user_message="Which movie title should I look up?",
        search_query="",
    )
    with patch("apps.backend.chat_routing.run_chat_web_route", new_callable=AsyncMock, return_value=mock_route):
        client = TestClient(app)
        r = client.get("/chat", params={"q": "it's a 2026 movie"})
    assert r.status_code == 200
    assert "movie title" in (r.json().get("response") or "").lower()
