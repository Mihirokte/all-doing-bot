"""Pipeline stage logic: Parse and Plan (LLM); Execute/Store in executor."""
from __future__ import annotations

import logging

from apps.backend.llm.engine import get_llm
from apps.backend.llm.prompts import prompt_parse, prompt_plan
from apps.backend.models.schemas import ParsedIntent, PlanOutput

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
