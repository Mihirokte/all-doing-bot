"""Pipeline stage logic: Parse and Plan (LLM); Execute/Store in executor."""
from __future__ import annotations

import logging

from apps.backend.llm.engine import get_llm
from apps.backend.llm.prompts import prompt_parse, prompt_plan, prompt_parse_and_plan
from apps.backend.models.schemas import ParsedIntent, PlanOutput, PlanStep, ParseAndPlanOutput

logger = logging.getLogger(__name__)


async def run_parse(query: str) -> ParsedIntent | None:
    """Parse stage: user query -> structured intent (cohort + action)."""
    llm = get_llm()
    prompt = prompt_parse(query)
    parsed = await llm.generate_structured(prompt, ParsedIntent, max_retries=1)
    return parsed if isinstance(parsed, ParsedIntent) else None


async def run_plan(parsed: ParsedIntent) -> PlanOutput | None:
    """Plan stage: parsed intent -> execution steps."""
    llm = get_llm()
    prompt = prompt_plan(parsed.model_dump_json())
    planned = await llm.generate_structured(prompt, PlanOutput, max_retries=1)
    return planned if isinstance(planned, PlanOutput) else None


async def run_parse_and_plan(query: str) -> tuple[ParsedIntent | None, PlanOutput | None]:
    """
    Combined parse+plan: one LLM call returns intent and steps.
    Returns (parsed, plan) for use by executor; (None, None) on failure.
    """
    llm = get_llm()
    prompt = prompt_parse_and_plan(query)
    combined = await llm.generate_structured(prompt, ParseAndPlanOutput, max_retries=1)
    if not isinstance(combined, ParseAndPlanOutput):
        return None, None
    parsed = ParsedIntent(
        cohort_name=combined.cohort_name,
        cohort_description=combined.cohort_description,
        action_type=combined.action_type,
        action_params=combined.action_params,
        summary=combined.summary,
    )
    plan = PlanOutput(steps=combined.steps)
    return parsed, plan
