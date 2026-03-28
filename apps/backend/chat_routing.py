"""Structured LLM gate: decide if /chat needs web retrieval and refine the search query."""
from __future__ import annotations

import logging

from apps.backend.config import settings
from apps.backend.llm.engine import get_llm
from apps.backend.models.schemas import ChatWebRoute

logger = logging.getLogger(__name__)

# Marker for MockProvider and tests (must appear in the prompt text).
_CHAT_ROUTE_MARKER = "chat_web_route_v1"


def prompt_chat_web_route(user_message: str, conversation_context: str = "") -> str:
    q = (user_message or "").strip()
    prior = (conversation_context or "").strip()
    prior_block = f"\nPrior conversation (chronological, oldest first):\n{prior}\n" if prior else ""
    return f"""{_CHAT_ROUTE_MARKER}
You route the CURRENT user message for a careful assistant. Reply with JSON ONLY matching this shape:
{{"needs_web": boolean, "ask_user_first": boolean, "ask_user_message": string, "search_query": string}}
{prior_block}
Definitions:
- needs_web: true if a good answer normally requires verifiable or up-to-date external facts (movie/show/game reviews or cast, news, sports results, product specs, niche biographies, "is X true", release dates, prices). false for stable general knowledge (e.g. capitals of well-known countries), math, logic, pure coding, creative writing, obvious metaphors/jokes with no factual claim, or vague philosophy. false for standalone greetings or thanks alone (e.g. "hello", "hi", "thanks", "bye") — those do not need the web.
- ask_user_first: true only if the CURRENT message is too vague to search AND the prior conversation does NOT supply a clear topic (e.g. pronouns like "it/this" with no entity in prior turns). If prior turns name a movie/product/person, resolve references and set ask_user_first false.
- ask_user_message: non-empty only when ask_user_first is true (one short clarifying question).
- search_query: when needs_web is true and ask_user_first is false, a concise web-search query (under 120 characters) with real entity names and year if relevant. Merge context from prior turns (e.g. user previously said "Dhurandhar 2" and now says "2026 reviews" -> search_query "Dhurandhar 2 movie reviews 2026"). Do NOT paste vague chat as the query.

Examples (no prior):
- "hello" or "hi" or "thanks" -> {{"needs_web": false, "ask_user_first": false, "ask_user_message": "", "search_query": ""}}
- "capital of France" -> {{"needs_web": false, "ask_user_first": false, "ask_user_message": "", "search_query": ""}}
- "capital of my heart" -> {{"needs_web": false, "ask_user_first": false, "ask_user_message": "", "search_query": ""}}
- "reviews of Dhurandhar 2 movie" -> {{"needs_web": true, "ask_user_first": false, "ask_user_message": "", "search_query": "Dhurandhar 2 movie reviews"}}

Examples (with prior):
- Prior includes User: reviews of Dhurandhar 2. Current: "it's the 2026 film" -> {{"needs_web": true, "ask_user_first": false, "ask_user_message": "", "search_query": "Dhurandhar 2 2026 movie reviews"}}

Current user message:
{q}
"""


async def run_chat_web_route(user_message: str, conversation_context: str = "") -> ChatWebRoute | None:
    if not getattr(settings, "chat_web_gate_enabled", True):
        return None
    llm = get_llm()
    prompt = prompt_chat_web_route(user_message, conversation_context)
    try:
        out = await llm.generate_structured(prompt, ChatWebRoute, max_retries=1)
        if out is None:
            return None
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("Chat web route gate failed: %s", e)
        return None
