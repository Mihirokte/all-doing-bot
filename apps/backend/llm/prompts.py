"""Minimal prompt templates for Parse and Plan stages. < 1000 input tokens."""
from __future__ import annotations


def prompt_parse(query: str) -> str:
    """Stage 1 — Parse: raw query -> structured intent (JSON)."""
    return f"""System: You extract structured intent from user queries. Respond in JSON only.
User: {query}
Expected output: {{ "cohort_name": "snake_case_name", "cohort_description": "...", "action_type": "web_fetch", "action_params": {{}}, "summary": "..." }}"""


def prompt_plan(parsed_intent_json: str) -> str:
    """Stage 2 — Plan: parsed intent -> execution steps (JSON)."""
    return f"""System: You are a task planner. Given this intent, output a list of execution steps in JSON.
User: {parsed_intent_json}
Expected output: {{ "steps": [ {{ "action": "search_web", "params": {{}} }}, ... ] }}"""
