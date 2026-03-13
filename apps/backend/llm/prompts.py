"""Minimal prompt templates for Parse and Plan stages. < 1000 input tokens."""
from __future__ import annotations


def prompt_parse(query: str) -> str:
    """Stage 1 — Parse: raw query -> structured intent (JSON)."""
    return f"""System: You extract structured intent from user queries. Respond in JSON only. No other text.

Rules:
- If the user wants to find, search, discover, or get news/updates about a topic (even without saying "search"): use action_type "search_web" and set action_params to {{ "q": "<concise search query>" }}. The "q" value MUST be a non-empty string (e.g. the topic or keywords).
- Only use action_type "web_fetch" when the user explicitly provides one or more URLs to fetch (action_params: {{ "urls": ["https://..."] }}). If there are no URLs, do NOT use web_fetch.
- cohort_name must be snake_case (e.g. ai_news_brief, python_tutorials). summary should briefly describe the intent.

User: {query}

Respond with exactly one JSON object: {{ "cohort_name": "...", "cohort_description": "...", "action_type": "search_web" or "web_fetch", "action_params": {{ "q": "..." }} or {{ "urls": ["..."] }}, "summary": "..." }}"""


def prompt_plan(parsed_intent_json: str) -> str:
    """Stage 2 — Plan: parsed intent -> execution steps (JSON)."""
    return f"""System: You are a task planner. Output a JSON object with a "steps" array. Each step has "action" and "params".

Rules:
- If the intent is to search or find information: the first step MUST be {{ "action": "search_web", "params": {{ "q": "<search query>" }} }}. "q" must be a non-empty string.
- If the intent is to fetch specific URLs: use {{ "action": "web_fetch", "params": {{ "urls": ["https://..."] }} }}. Do NOT use web_fetch with empty urls.
- Other actions: "api_call", "transform" with their required params.
- Output only the JSON object, no other text.

User intent: {parsed_intent_json}

Expected format: {{ "steps": [ {{ "action": "search_web", "params": {{ "q": "..." }} }}, ... ] }}"""


def prompt_parse_and_plan(query: str) -> str:
    """Combined Parse+Plan: one prompt returning intent + steps (single LLM call)."""
    return f"""System: You extract structured intent and an execution plan from the user query. Respond with ONE JSON object only. No other text.

Rules:
- If the user wants to find, search, discover, or get news/updates: use action_type "search_web", action_params {{ "q": "<concise search query>" }}, and steps must include {{ "action": "search_web", "params": {{ "q": "<same or similar query>" }} }}.
- Only use action_type "web_fetch" when the user explicitly provides URLs; then action_params {{ "urls": ["https://..."] }} and steps with web_fetch.
- cohort_name must be snake_case (e.g. ai_news_brief). summary: brief intent description.
- Output a single JSON with: cohort_name, cohort_description, action_type, action_params, summary, and steps (array of {{ "action": "...", "params": {{}} }}).

User: {query}

Respond with exactly: {{ "cohort_name": "...", "cohort_description": "...", "action_type": "search_web" or "web_fetch", "action_params": {{ "q": "..." }} or {{ "urls": [] }}, "summary": "...", "steps": [ {{ "action": "search_web", "params": {{ "q": "..." }} }}, ... ] }}"""
