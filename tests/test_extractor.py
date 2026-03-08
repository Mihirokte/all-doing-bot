"""Extractor adapter and cleaner tests with mocked HTTP only."""
from __future__ import annotations

import respx
from httpx import Response

from apps.backend.extractor import clear_cache, extract_url
from apps.backend.extractor.adapters.generic import GenericAdapter
from apps.backend.extractor.adapters.registry import get_adapter
from apps.backend.extractor.adapters.reddit import RedditAdapter
from apps.backend.extractor.adapters.twitter import TwitterAdapter


ARTICLE_HTML = """
<html>
  <head><title>Example News</title><script>bad()</script></head>
  <body>
    <nav>Menu</nav>
    <article>
      <h1>Example News</h1>
      <p>This is the first sentence. This is the second sentence.</p>
      <p>This is the third sentence.</p>
    </article>
    <footer>Footer</footer>
  </body>
</html>
"""

LIST_HTML = """
<html>
  <head><title>Feed Page</title></head>
  <body>
    <ul>
      <li>Item 1 about AI agents and workflows.</li>
      <li>Item 2 about AI agents and workflows.</li>
      <li>Item 3 about AI agents and workflows.</li>
      <li>Item 4 about AI agents and workflows.</li>
      <li>Item 5 about AI agents and workflows.</li>
      <li>Item 6 about AI agents and workflows.</li>
    </ul>
  </body>
</html>
"""

LONG_HTML = f"""
<html><head><title>Long</title></head><body><article>
<p>{'Sentence. ' * 600}</p>
</article></body></html>
"""

REDDIT_JSON = [
    {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "Post one",
                        "selftext": "Body one",
                        "score": 10,
                        "num_comments": 2,
                    }
                },
                {
                    "data": {
                        "title": "Post two",
                        "selftext": "Body two",
                        "score": 12,
                        "num_comments": 3,
                    }
                },
            ]
        }
    }
]


def setup_function() -> None:
    clear_cache()


@respx.mock
def test_generic_adapter_article_extracts_clean_content() -> None:
    route = respx.get("https://example.com/article").mock(return_value=Response(200, text=ARTICLE_HTML))
    result = __import__("asyncio").run(GenericAdapter().extract("https://example.com/article"))
    assert route.called
    assert result.title == "Example News"
    assert "Menu" not in result.content
    assert "Footer" not in result.content
    assert result.content_type == "article"


@respx.mock
def test_generic_adapter_fallback_still_extracts_body() -> None:
    html = "<html><head><title>Fallback</title></head><body><div>Short body but enough meaningful fallback text here.</div></body></html>"
    respx.get("https://example.com/fallback").mock(return_value=Response(200, text=html))
    result = __import__("asyncio").run(GenericAdapter().extract("https://example.com/fallback"))
    assert "meaningful fallback text" in result.content


@respx.mock
def test_generic_adapter_smart_truncation() -> None:
    respx.get("https://example.com/long").mock(return_value=Response(200, text=LONG_HTML))
    result = __import__("asyncio").run(GenericAdapter().extract("https://example.com/long", max_chars=2000))
    assert len(result.content) <= 2000
    assert result.content.endswith((".", "!", "?", "\n"))


@respx.mock
def test_generic_adapter_detects_list_pages() -> None:
    respx.get("https://example.com/feed").mock(return_value=Response(200, text=LIST_HTML))
    result = __import__("asyncio").run(GenericAdapter().extract("https://example.com/feed"))
    assert result.content_type == "feed"
    assert len(result.items) >= 5
    assert result.content == ""


@respx.mock
def test_reddit_adapter_extracts_items_from_json() -> None:
    respx.get("https://www.reddit.com/r/test/comments/123.json").mock(return_value=Response(200, json=REDDIT_JSON))
    result = __import__("asyncio").run(
        RedditAdapter().extract("https://www.reddit.com/r/test/comments/123", max_chars=2000)
    )
    assert result.content_type == "feed"
    assert len(result.items) == 2
    assert "Post one" in result.items[0]


@respx.mock
def test_twitter_adapter_graceful_failure() -> None:
    respx.get("https://syndication.twitter.com/srv/timeline-profile/screen-name/someuser").mock(
        return_value=Response(503, text="")
    )
    respx.get("https://nitter.net/someuser/status/1").mock(return_value=Response(503, text=""))
    respx.get("https://nitter.poast.org/someuser/status/1").mock(return_value=Response(503, text=""))
    respx.get("https://nitter.privacydev.net/someuser/status/1").mock(return_value=Response(503, text=""))
    respx.get("https://duckduckgo.com/html/?q=site%3Atwitter.com+1").mock(return_value=Response(503, text=""))
    result = __import__("asyncio").run(TwitterAdapter().extract("https://twitter.com/someuser/status/1"))
    assert result.content_type == "error"
    assert "all access methods failed" in result.content.lower()


@respx.mock
def test_generic_adapter_http_error_handling() -> None:
    respx.get("https://example.com/blocked").mock(return_value=Response(403, text="blocked"))
    result = __import__("asyncio").run(GenericAdapter().extract("https://example.com/blocked"))
    assert result.content_type == "error"
    assert "HTTP 403" in result.content


def test_adapter_registry_routing() -> None:
    assert isinstance(get_adapter("https://twitter.com/user/status/1"), TwitterAdapter)
    assert isinstance(get_adapter("https://www.reddit.com/r/test/comments/123"), RedditAdapter)
    assert isinstance(get_adapter("https://example.com/article"), GenericAdapter)


@respx.mock
def test_extractor_cache_prevents_duplicate_fetches() -> None:
    route = respx.get("https://example.com/cached").mock(return_value=Response(200, text=ARTICLE_HTML))
    first = __import__("asyncio").run(extract_url("https://example.com/cached"))
    second = __import__("asyncio").run(extract_url("https://example.com/cached"))
    assert route.call_count == 1
    assert first.title == second.title
