"""Tests for chat evidence markdown sanitization."""

from apps.backend.text_cleanup import sanitize_chat_evidence_markdown


def test_strips_wiki_article_link_with_title() -> None:
    raw = '2015 single by [Adele](/wiki/Adele "Adele"), released on 23 October'
    out = sanitize_chat_evidence_markdown(raw)
    assert "[Adele]" not in out and "](/wiki/" not in out
    assert "Adele" in out
    assert "2015 single" in out


def test_strips_image_markdown() -> None:
    raw = "Hello ![](//upload.wikimedia.org/wikipedia/foo.jpg) world"
    out = sanitize_chat_evidence_markdown(raw)
    assert "![" not in out and "upload.wikimedia" not in out
    assert "Hello" in out and "world" in out


def test_strips_linked_wiki_thumb() -> None:
    raw = "See [![thumb](//x.jpg)](/wiki/File:Telephone) please"
    out = sanitize_chat_evidence_markdown(raw)
    assert "![" not in out and "](/wiki/" not in out
    assert "See" in out and "please" in out


def test_flattens_full_wikipedia_url_link() -> None:
    raw = "More at [Hello (Adele song)](https://en.wikipedia.org/wiki/Hello_(Adele_song)) today"
    out = sanitize_chat_evidence_markdown(raw)
    assert "https://en.wikipedia.org" not in out
    assert "[" not in out and "](" not in out
    assert "Hello (Adele song)" in out
    assert "today" in out
