"""Deep Think-Do retrieval: 3-cycle loop for short search queries, evidence-first response."""
from __future__ import annotations

import logging
from typing import Any, List

from apps.backend.config import settings
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)


def _entry_from_crawl_record(rec: dict) -> Entry:
    """Convert a crawl record (url, markdown, metadata) to Entry for ranking."""
    url = str(rec.get("url") or "").strip()
    markdown = str(rec.get("markdown") or "").strip()
    meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
    title = str(meta.get("title") or "").strip() if meta else ""
    content = f"**{title}**\n\n{markdown}" if title else markdown
    return Entry(content=content or "(no content)", source=url, metadata="{}", created_at="")


async def run_deep_search(query: str) -> str:
    """
    Run 3-cycle think/do loop: search -> fetch/crawl -> rank & compose.
    Returns evidence-first response string (bullets + synthesis + confidence).
    """
    from apps.backend.actions.registry import run_action
    from apps.backend.actions.cloudflare_crawl import _available as crawl_available, crawl_urls
    from apps.backend.actions.source_ranker import (
        rank_entries,
        confidence_from_scores,
        evidence_bullets,
    )

    top_n = getattr(settings, "chat_deep_top_links", 4) or 4
    max_cycles = getattr(settings, "chat_deep_max_cycles", 3) or 3

    # Cycle 1: Do — search
    try:
        search_entries = await run_action("search_web", {"q": query, "top_n": top_n})
    except Exception as e:
        logger.warning("Deep search: search_web failed: %s", e)
        search_entries = []

    all_entries: List[Any] = list(search_entries)

    # Cycle 2: Do — fetch/crawl top links
    urls: List[str] = []
    for e in search_entries[:top_n]:
        src = (getattr(e, "source", "") or "").strip()
        if src and src.startswith("http"):
            urls.append(src)
    urls = urls[: max(3, top_n)]

    if urls:
        if crawl_available():
            try:
                records = await crawl_urls(urls[:3], limit_per_url=1, formats=["markdown"], render=False)
                for rec in (records or []):
                    if isinstance(rec, dict) and rec.get("url"):
                        all_entries.append(_entry_from_crawl_record(rec))
            except Exception as e:
                logger.warning("Deep search: crawl failed, using web_fetch: %s", e)
        if len(all_entries) <= len(search_entries):
            try:
                fetched = await run_action("web_fetch", {"urls": urls[:3]})
                for e in fetched or []:
                    if getattr(e, "content", "").strip() and not getattr(e, "content", "").strip().lower().startswith("error:"):
                        all_entries.append(e)
            except Exception as e:
                logger.warning("Deep search: web_fetch failed: %s", e)
    # Optional cycle 3: one more fetch round if we have more URLs and few merged
    if max_cycles >= 3 and urls and len(all_entries) < 4:
        extra_urls = [u for u in urls[3:6] if u]
        if extra_urls:
            try:
                fetched2 = await run_action("web_fetch", {"urls": extra_urls[:2]})
                for e in fetched2 or []:
                    if getattr(e, "content", "").strip():
                        all_entries.append(e)
            except Exception as e:
                logger.debug("Deep search: second fetch failed: %s", e)

    # Think3: rank and compose evidence-first response
    ranked = rank_entries(all_entries, query, top_n=5)
    scores = [s for _, s in ranked]
    confidence = confidence_from_scores(scores, min_evidence=2)
    bullets = evidence_bullets(ranked, max_bullets=5)

    lines: List[str] = []
    if bullets:
        lines.append("**Evidence**")
        for claim, url in bullets:
            lines.append(f"- {claim} — [Source]({url})")
        lines.append("")
    synthesis = _short_synthesis(query, bullets, confidence)
    lines.append(synthesis)
    lines.append("")
    lines.append(f"*Confidence: {confidence}*")
    if confidence == "low" and bullets:
        lines.append("")
        lines.append("Evidence is limited. Try a narrower or more specific query for better results.")
    elif confidence == "low" and not bullets:
        lines.append("")
        lines.append("I couldn't find strong evidence for this. Try rephrasing or a more specific search.")
    return "\n".join(lines).strip()


def _short_synthesis(query: str, bullets: List[tuple], confidence: str) -> str:
    """One short paragraph summarizing the evidence (no LLM call)."""
    if not bullets:
        return f"I didn't find concrete results for \"{query}\"."
    n = len(bullets)
    return f"Based on {n} source(s) above: here are the most relevant findings for \"{query}\"."
