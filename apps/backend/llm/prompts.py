"""Minimal prompt templates for Parse and Plan stages. < 1000 input tokens."""
from __future__ import annotations


def prompt_parse(query: str) -> str:
    """Stage 1 — Parse: raw query -> structured intent (JSON)."""
    return f"""System: You extract structured intent from user queries. Respond in JSON only. No other text.

Rules:
- If the user wants to find, search, discover, or get news/updates about a topic (even without saying "search"): use action_type "search_web" and set action_params to {{ "q": "<concise search query>" }}. The "q" value MUST be a non-empty string (e.g. the topic or keywords).
- Only use action_type "web_fetch" when the user explicitly provides one or more URLs to fetch (action_params: {{ "urls": ["https://..."] }}). If there are no URLs, do NOT use web_fetch.
- Use action_type "browser_automation" only when the request clearly implies dynamic or interactive content (JS-heavy pages, sign-in walls, form interactions, click/submit flows). Prefer starting at search_web unless this is explicit.
- cohort_name must be snake_case (e.g. ai_news_brief, python_tutorials). summary should briefly describe the intent.

User: {query}

Respond with exactly one JSON object: {{ "cohort_name": "...", "cohort_description": "...", "action_type": "search_web" or "web_fetch" or "browser_automation", "action_params": {{ "q": "..." }} or {{ "urls": ["..."] }}, "summary": "..." }}"""


def prompt_plan(parsed_intent_json: str) -> str:
    """Stage 2 — Plan: parsed intent -> execution steps (JSON)."""
    return f"""System: You are a task planner. Output a JSON object with a "steps" array. Each step has "action" and "params".

Rules:
- If the intent is to search or find information: the first step MUST be {{ "action": "search_web", "params": {{ "q": "<search query>" }} }}. "q" must be a non-empty string.
- Confidence-aware escalation path:
  1) start with search_web
  2) use web_fetch for top URLs when search results exist
  3) add browser_automation when confidence is low OR results appear JS-heavy / blocked / interactive
- If explicit URLs are provided: use web_fetch first; then browser_automation for dynamic/interactive pages if needed.
- browser_automation params should usually include urls: {{ "urls": ["https://..."] }}.
- Other actions: "api_call", "transform" with their required params.
- Output only the JSON object, no other text.

User intent: {parsed_intent_json}

Expected format: {{ "steps": [ {{ "action": "search_web", "params": {{ "q": "..." }} }}, {{ "action": "web_fetch", "params": {{ "urls": ["https://..."] }} }}, {{ "action": "browser_automation", "params": {{ "urls": ["https://..."] }} }}, ... ] }}"""


def prompt_parse_and_plan(query: str) -> str:
    """Combined Parse+Plan: one prompt returning intent + steps (single LLM call)."""
    return f"""System: You extract structured intent and an execution plan from the user query. Respond with ONE JSON object only. No other text.

Rules:
- If the user wants to find, search, discover, or get news/updates: use action_type "search_web", action_params {{ "q": "<concise search query>" }}, and steps must include {{ "action": "search_web", "params": {{ "q": "<same or similar query>" }} }}.
- Only use action_type "web_fetch" when the user explicitly provides URLs; then action_params {{ "urls": ["https://..."] }} and steps with web_fetch.
- Use action_type "browser_automation" when the request is explicitly dynamic/interactive, or include browser_automation as an escalation step after search_web/web_fetch when confidence may be low.
- Escalation preference in steps: search_web -> web_fetch -> browser_automation.
- cohort_name must be snake_case (e.g. ai_news_brief). summary: brief intent description.
- Output a single JSON with: cohort_name, cohort_description, action_type, action_params, summary, and steps (array of {{ "action": "...", "params": {{}} }}).

User: {query}

Respond with exactly: {{ "cohort_name": "...", "cohort_description": "...", "action_type": "search_web" or "web_fetch" or "browser_automation", "action_params": {{ "q": "..." }} or {{ "urls": [] }}, "summary": "...", "steps": [ {{ "action": "search_web", "params": {{ "q": "..." }} }}, {{ "action": "web_fetch", "params": {{ "urls": [] }} }}, {{ "action": "browser_automation", "params": {{ "urls": [] }} }}, ... ] }}"""
