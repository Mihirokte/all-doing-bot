"""Plain-text cleanup for chat responses sourced from web/wiki markdown."""

from __future__ import annotations

import re


def sanitize_chat_evidence_markdown(text: str) -> str:
    """
    Strip image markdown and flatten Wikipedia-style links to visible labels.

    Crawled/fetched wiki pages often include constructs like
    ``[Adele](/wiki/Adele "Adele")`` and ``![thumb](//upload.wikimedia.org/...)``
    which read badly in a chat pane; the real citation URL is attached separately
    in evidence bullets.
    """
    if not text:
        return ""
    t = text
    # Linked image: [![caption](thumb)](page)
    t = re.sub(r"\[\s*!\[[^\]]*\]\([^)]+\)\s*\]\([^)]+\)", " ", t)
    # Plain image: ![alt](url) — includes protocol-relative // URLs
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    # [label](/wiki/Path) or [label](/wiki/Path "Title")
    t = re.sub(
        r"\[([^\]]+)\]\(\s*/wiki/[^)\s]+(?:\s+\"[^\"]*\")?\s*\)",
        r"\1",
        t,
    )
    # [label](https://en.wikipedia.org/...) or subdomains
    t = re.sub(
        r"\[([^\]]+)\]\(\s*https?://(?:[a-z0-9-]+\.)?wikipedia\.org[^)]+\)",
        r"\1",
        t,
    )
    # [label](//en.wikipedia.org/...) protocol-relative
    t = re.sub(
        r"\[([^\]]+)\]\(\s*//(?:[a-z0-9-]+\.)?wikipedia\.org[^)]+\)",
        r"\1",
        t,
    )
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
