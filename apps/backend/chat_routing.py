"""Structured LLM gate: decide if /chat needs web retrieval and refine the search query."""
from __future__ import annotations

import logging

from apps.backend.config import settings
from apps.backend.llm.engine import get_llm
from apps.backend.models.schemas import ChatWebRoute

logger = logging.getLogger(__name__)

# Marker for MockProvider and tests (must appear in the prompt text).
_CHAT_ROUTE_MARKER = "chat_web_route_v1"


def prompt_chat_web_route(user_message: str) -> str:
    q = (user_message or "").strip()
    return f"""{_CHAT_ROUTE_MARKER}
You route ONE user message for a careful assistant. Reply with JSON ONLY matching this shape:
{{"needs_web": boolean, "ask_user_first": boolean, "ask_user_message": string, "search_query": string}}

Definitions:
- needs_web: true if a good answer normally requires verifiable or up-to-date external facts (movie/show/game reviews or cast, news, sports results, product specs, niche biographies, "is X true", release dates, prices). false for stable general knowledge (e.g. capitals of well-known countries), math, logic, pure coding, creative writing, obvious metaphors/jokes with no factual claim, or vague philosophy.
- ask_user_first: true if the message is too vague to search (mostly pronouns like "it/this/that" with no clear topic, or asking for reviews/details but NO title/name). When true, set needs_web to false and put one short clarifying question in ask_user_message.
- ask_user_message: non-empty only when ask_user_first is true.
- search_query: when needs_web is true and ask_user_first is false, a concise web-search query (under 120 characters) with real entity names and year if relevant. Do NOT use the whole vague chat sentence as the query. If the user message is garbage or not a real question, set needs_web false.

Examples:
- "capital of France" -> {{"needs_web": false, "ask_user_first": false, "ask_user_message": "", "search_query": ""}}
- "capital of my heart" -> {{"needs_web": false, "ask_user_first": false, "ask_user_message": "", "search_query": ""}}
- "reviews of Dhurandhar 2 movie" -> {{"needs_web": true, "ask_user_first": false, "ask_user_message": "", "search_query": "Dhurandhar 2 movie reviews 2026"}}
- "it's a latest 2026 moview" -> {{"needs_web": false, "ask_user_first": true, "ask_user_message": "Which movie should I look up? Please send the exact title.", "search_query": ""}}

User message:
{q}
"""


async def run_chat_web_route(user_message: str) -> ChatWebRoute | None:
    if not getattr(settings, "chat_web_gate_enabled", True):
        return None
    llm = get_llm()
    prompt = prompt_chat_web_route(user_message)
    try:
        out = await llm.generate_structured(prompt, ChatWebRoute, max_retries=1)
        if out is None:
            return None
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("Chat web route gate failed: %s", e)
        return None
