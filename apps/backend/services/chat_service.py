"""Chat short-query path: routing, retrieval stack, direct LLM, transcript persist."""
from __future__ import annotations

import logging
from typing import Any

from apps.backend.config import settings
from apps.backend.text_cleanup import sanitize_chat_evidence_markdown

logger = logging.getLogger(__name__)


class ChatLLMUnavailableError(Exception):
    """Raised when the non-web chat path cannot reach the LLM."""


async def ensure_english_response(text: str) -> str:
    """Normalize assistant output to English while preserving facts and links."""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    try:
        from apps.backend.llm.engine import get_llm

        llm = get_llm()
        prompt = (
            "Rewrite the following text in clear English only. Preserve meaning, "
            "facts, numbers, names, URLs, and formatting structure (lists/line breaks). "
            "If already English, keep the same level of detail and mostly unchanged. "
            "Do not shorten or compress details. Output only the rewritten text. "
            "Do not add intro phrases such as 'Here is the rewritten text'.\n\n"
            f"Text:\n{cleaned}"
        )
        rewritten = await llm.generate(prompt, max_tokens=450, json_mode=False)
        rewritten = (rewritten or "").strip()
        if rewritten.lower().startswith("here is"):
            rewritten = rewritten.split("\n", 1)[-1].strip()
        return rewritten or cleaned
    except Exception as e:  # noqa: BLE001
        logger.warning("English normalization failed; using original text: %s", e)
        return cleaned


def chat_looks_like_search(query: str) -> bool:
    """True if the short query implies the user wants live web results (find, search, latest, etc.)."""
    lower = query.strip().lower()
    if len(lower) < 4:
        return False
    triggers = (
        "find",
        "search",
        "look up",
        "lookup",
        "get me",
        "fetch",
        "latest",
        "recent",
        "today",
        "this week",
        "top",
        "best",
        "trending",
        "what are the",
        "when did",
        "who is the",
        "where can i",
        "how do i",
        "news about",
        "updates on",
        "launches",
        "release",
        "projects",
        "github",
        "review",
        "reviews",
        "movie",
        "movies",
        "film",
        "imdb",
        "rotten",
        "critic",
        "critics",
        "rating",
        "ratings",
        "box office",
        "sequel",
        "trailer",
        "cast of",
        "episode",
        "worth watching",
        "tell me the",
        "are you sure",
        "correct",
        "accurate",
        "sources",
        "source for",
    )
    return any(t in lower for t in triggers)


def dedupe_entries_by_source(entries: list[Any], max_keep: int = 12) -> list[Any]:
    """Drop duplicate URLs (common with editorial listicles); keep order."""
    seen: set[str] = set()
    out: list[Any] = []
    for e in entries or []:
        src = (getattr(e, "source", "") or "").strip()
        key = src.split("#")[0].rstrip("/").lower() if src.startswith("http") else f"c:{hash((getattr(e, 'content', '') or '')[:300])}"
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= max_keep:
            break
    return out


def search_wants_detail(query: str) -> bool:
    """True when user asks to find/search/explore and expects depth."""
    lower = query.strip().lower()
    detail_triggers = (
        "find",
        "search",
        "latest",
        "top",
        "best",
        "trending",
        "list",
        "compare",
        "detailed",
        "in detail",
    )
    return any(t in lower for t in detail_triggers)


def search_response_from_entries(query: str, entries: list, detailed: bool = False) -> str:
    """Return direct, concrete search results for chat (no abstraction)."""
    lines = [f"Search results for '{query}':"]
    rank = 1
    cap = 7 if detailed else 5
    for e in entries[:cap]:
        content = (getattr(e, "content", "") or "").strip()
        source = (getattr(e, "source", "") or "").strip()
        if not content:
            continue
        title = content
        snippet = ""
        if content.startswith("**") and "**" in content[2:]:
            end = content.find("**", 2)
            title = content[2:end].strip() or title
            rest = content[end + 2 :].strip()
            if rest.startswith("\n\n"):
                rest = rest[2:].strip()
            snippet = rest
        snippet = snippet or content
        snippet = " ".join(snippet.split())
        if len(snippet) > (320 if detailed else 180):
            snippet = snippet[: (320 if detailed else 180)].rstrip() + "..."
        line = f"{rank}) {title}"
        if source:
            line += f"\n   Source: {source}"
        if snippet:
            line += f"\n   Summary: {snippet}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return "I couldn't find concrete web results right now. Please try rephrasing the query."
    if detailed:
        lines.append("")
        lines.append("If you want, I can continue with a deeper comparison of the top options.")
    return "\n".join(lines)


def crawl_response_from_records(query: str, records: list[dict], detailed: bool = False) -> str:
    """Return concrete link-hit results from crawled pages."""
    lines = [f"I analyzed rendered pages for '{query}' and found:"]
    rank = 1
    cap = 5 if detailed else 3
    for rec in records[:cap]:
        if not isinstance(rec, dict):
            continue
        url = str(rec.get("url") or "").strip()
        markdown = str(rec.get("markdown") or "").strip()
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        title = str(meta.get("title") or "").strip() if meta else ""
        if not markdown:
            continue
        summary = " ".join(markdown.split())
        if len(summary) > (500 if detailed else 240):
            summary = summary[: (500 if detailed else 240)].rstrip() + "..."
        label = title or url or f"Result {rank}"
        line = f"{rank}) {label}"
        if url:
            line += f"\n   Source: {url}"
        line += f"\n   Key detail: {summary}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return ""
    return "\n".join(lines)


def fetched_response_from_entries(query: str, entries: list, detailed: bool = False) -> str:
    """Return concrete summaries from fetched page content."""
    lines = [f"I fetched source pages for '{query}' and found:"]
    rank = 1
    cap = 6 if detailed else 4
    for e in entries[:cap]:
        content = (getattr(e, "content", "") or "").strip()
        source = (getattr(e, "source", "") or "").strip()
        if not content or content.lower().startswith("error:"):
            continue
        summary = " ".join(content.split())
        if len(summary) > (520 if detailed else 260):
            summary = summary[: (520 if detailed else 260)].rstrip() + "..."
        label = source or f"Result {rank}"
        line = f"{rank}) {label}\n   Detail: {summary}"
        lines.append(line)
        rank += 1
    if rank == 1:
        return ""
    return "\n".join(lines)


async def chat_retrieval_stack(search_q: str, display_q: str, detailed_search: bool) -> str | None:
    """Run deep search / search_web / crawl / fetch. Returns visible text or None."""
    from apps.backend.actions.cloudflare_crawl import _available as crawl_available, crawl_urls
    from apps.backend.actions.registry import run_action

    if getattr(settings, "chat_web_search_enabled", False) and getattr(settings, "chat_deep_mode_enabled", True):
        from apps.backend.deep_search import run_deep_search

        deep_response = await run_deep_search(search_q)
        if deep_response:
            return deep_response
    entries = await run_action("search_web", {"q": search_q, "top_n": 8})
    entries = dedupe_entries_by_source(entries, 12)
    if not entries:
        return None

    if crawl_available():
        urls = []
        for e in entries[:6]:
            src = (getattr(e, "source", "") or "").strip()
            if src and src.startswith("http"):
                urls.append(src)
        if urls:
            records = await crawl_urls(urls[:3], limit_per_url=1, formats=["markdown"], render=False)
            crawl_text = crawl_response_from_records(display_q, records, detailed=detailed_search)
            if crawl_text:
                return crawl_text
    urls = []
    for e in entries[:6]:
        src = (getattr(e, "source", "") or "").strip()
        if src and src.startswith("http"):
            urls.append(src)
    if urls:
        fetched = await run_action("web_fetch", {"urls": urls[:3]})
        fetched_text = fetched_response_from_entries(display_q, fetched, detailed=detailed_search)
        if fetched_text:
            return fetched_text
    return search_response_from_entries(display_q, entries, detailed=detailed_search)


async def handle_chat(query: str, session_key: str) -> dict[str, str]:
    """
    Session-scoped chat: transcript load, structured gate, web vs direct LLM, persist.
    Caller validates non-empty query and length.
    """
    from apps.backend.chat_routing import run_chat_web_route
    from apps.backend.db.chat_transcript import load_transcript_for_prompt, persist_chat_exchange
    from apps.backend.llm.engine import get_llm
    from apps.backend.models.schemas import ChatWebRoute

    sk = (session_key or "default").strip() or "default"
    detailed_search = search_wants_detail(query)
    prior = await load_transcript_for_prompt(sk)

    route = await run_chat_web_route(query, prior)
    if route is None:
        route = ChatWebRoute()

    async def reply(assistant_text: str) -> dict[str, str]:
        cleaned = sanitize_chat_evidence_markdown((assistant_text or "").strip())
        normalized = await ensure_english_response(cleaned)
        normalized = sanitize_chat_evidence_markdown((normalized or "").strip())
        await persist_chat_exchange(sk, query, normalized)
        return {"response": normalized}

    if route.ask_user_first and (route.ask_user_message or "").strip():
        return await reply((route.ask_user_message or "").strip())

    heuristic_search = chat_looks_like_search(query)
    effective_web = bool(route.needs_web or heuristic_search)
    search_q = (route.search_query or "").strip() or query

    if effective_web:
        if not getattr(settings, "chat_web_search_enabled", False):
            return await reply(
                "I would need live web search to answer that without guessing, "
                "but CHAT_WEB_SEARCH_ENABLED is off on this server. "
                "Turn it on in the backend environment, or use a host where search is enabled."
            )
        try:
            text = await chat_retrieval_stack(search_q, query, detailed_search)
        except Exception as e:  # noqa: BLE001
            logger.warning("Chat web retrieval failed: %s", e)
            text = None
        if text:
            return await reply(text)
        return await reply(
            "Web search did not return usable results. "
            "Try a more specific query with a full name, title, year, or product name."
        )

    llm = get_llm()
    ctx = f"Prior conversation:\n{prior}\n\n" if prior else ""
    prompt = (
        "You are a careful assistant.\n"
        "Answer in English only, in 2-4 short sentences. Do not use markdown or bullet lists.\n"
        "If you are not sure, say you are not sure. Do not invent movie titles, people, dates, "
        "statistics, reviews, box office numbers, or current events.\n"
        "If the question needs fresh news or niche facts you cannot verify from general knowledge, "
        "say you cannot confirm without a web search.\n"
        "Use the prior conversation to interpret follow-ups (e.g. \"it\" / \"that movie\").\n"
        f"{ctx}Current question: {query}"
    )
    try:
        response = await llm.generate(prompt, max_tokens=220, json_mode=False)
        return await reply((response or "").strip())
    except Exception as e:
        logger.warning("Chat LLM failed: %s", e)
        raise ChatLLMUnavailableError from e
