"""One local LLM structured audit per LangGraph stage (parse / plan) → enum verdict."""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from apps.backend.config import settings
from apps.backend.models.schemas import (
    ParsedIntent,
    PlanOutput,
    PipelineStageAnalysis,
    PipelineStageAuditVerdict,
)

logger = logging.getLogger(__name__)

_PIPELINE_STAGE_AUDIT_MARKER = "pipeline_stage_audit_v1"


class StageAuditLLMResponse(BaseModel):
    """JSON-only shape returned by the audit model (no `stage`; caller sets it)."""

    verdict: PipelineStageAuditVerdict
    rationale: str = Field(default="", max_length=500)


def _compact_parsed_snapshot(parsed: ParsedIntent) -> dict[str, Any]:
    return {
        "cohort_name": parsed.cohort_name,
        "cohort_description": (parsed.cohort_description or "")[:240],
        "action_type": parsed.action_type,
        "action_params": parsed.action_params,
        "summary": (parsed.summary or "")[:400],
    }


def _compact_plan_snapshot(plan: PlanOutput) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, step in enumerate(plan.steps[:8]):
        out.append({"index": i, "action": step.action, "params_keys": list((step.params or {}).keys())})
    return out


def prompt_audit_parse(query: str, parsed: ParsedIntent) -> str:
    snap = json.dumps(_compact_parsed_snapshot(parsed), ensure_ascii=False)[:3500]
    verdicts = ", ".join(v.value for v in PipelineStageAuditVerdict)
    return f"""{_PIPELINE_STAGE_AUDIT_MARKER}
You audit whether PARSE output matches the USER QUERY. Reply with JSON ONLY matching:
{{"verdict": "<one of: {verdicts}>", "rationale": "<one short sentence>"}}

Rules:
- sound: intent and cohort clearly fit the query.
- needs_clarification: user likely needs another question before acting.
- ambiguous_intent: multiple conflicting interpretations.
- plan_mismatch: (use only for parse audit when action clearly wrong for query) — rare at parse stage; prefer ambiguous_intent.
- incomplete: parse JSON looks broken or empty fields.

USER QUERY:
{query.strip()[:2000]}

PARSE OUTPUT:
{snap}
"""


def prompt_audit_plan(query: str, parsed: ParsedIntent, plan: PlanOutput) -> str:
    p = json.dumps(_compact_parsed_snapshot(parsed), ensure_ascii=False)[:2000]
    steps = json.dumps(_compact_plan_snapshot(plan), ensure_ascii=False)[:2000]
    verdicts = ", ".join(v.value for v in PipelineStageAuditVerdict)
    return f"""{_PIPELINE_STAGE_AUDIT_MARKER}
You audit whether PLAN steps fit the USER QUERY and PARSED INTENT. Reply with JSON ONLY:
{{"verdict": "<one of: {verdicts}>", "rationale": "<one short sentence>"}}

Rules:
- sound: steps are a reasonable way to fulfill the intent.
- plan_mismatch: steps contradict intent or query (wrong actions/order).
- needs_clarification: plan assumes facts the user did not provide.
- ambiguous_intent: cannot tell if plan is right.
- incomplete: no steps or obviously unusable plan.

USER QUERY:
{query.strip()[:2000]}

PARSED INTENT:
{p}

PLAN STEPS:
{steps}
"""


async def audit_parse_output(query: str, parsed: ParsedIntent) -> PipelineStageAnalysis:
    from apps.backend.llm.engine import get_llm

    llm = get_llm()
    prompt = prompt_audit_parse(query, parsed)
    try:
        out = await llm.generate_structured(prompt, StageAuditLLMResponse, max_retries=1)
    except Exception as e:  # noqa: BLE001
        logger.warning("Parse stage audit LLM error: %s", e)
        return PipelineStageAnalysis(
            stage="parse",
            verdict=PipelineStageAuditVerdict.incomplete,
            rationale="Audit LLM unavailable.",
        )
    if out is None:
        return PipelineStageAnalysis(
            stage="parse",
            verdict=PipelineStageAuditVerdict.incomplete,
            rationale="Audit returned no structured JSON.",
        )
    return PipelineStageAnalysis(stage="parse", verdict=out.verdict, rationale=(out.rationale or "").strip()[:500])


async def audit_plan_output(query: str, parsed: ParsedIntent, plan: PlanOutput) -> PipelineStageAnalysis:
    from apps.backend.llm.engine import get_llm

    llm = get_llm()
    prompt = prompt_audit_plan(query, parsed, plan)
    try:
        out = await llm.generate_structured(prompt, StageAuditLLMResponse, max_retries=1)
    except Exception as e:  # noqa: BLE001
        logger.warning("Plan stage audit LLM error: %s", e)
        return PipelineStageAnalysis(
            stage="plan",
            verdict=PipelineStageAuditVerdict.incomplete,
            rationale="Audit LLM unavailable.",
        )
    if out is None:
        return PipelineStageAnalysis(
            stage="plan",
            verdict=PipelineStageAuditVerdict.incomplete,
            rationale="Audit returned no structured JSON.",
        )
    return PipelineStageAnalysis(stage="plan", verdict=out.verdict, rationale=(out.rationale or "").strip()[:500])


def audit_disabled_placeholder(stage: str) -> PipelineStageAnalysis:
    return PipelineStageAnalysis(
        stage=stage,
        verdict=PipelineStageAuditVerdict.sound,
        rationale="PIPELINE_STAGE_AUDIT_ENABLED is false; audit skipped.",
    )


def audit_parse_failed_placeholder() -> PipelineStageAnalysis:
    return PipelineStageAnalysis(
        stage="parse",
        verdict=PipelineStageAuditVerdict.incomplete,
        rationale="Parse produced no intent.",
    )


def audit_plan_failed_placeholder() -> PipelineStageAnalysis:
    return PipelineStageAnalysis(
        stage="plan",
        verdict=PipelineStageAuditVerdict.incomplete,
        rationale="Plan stage did not produce steps.",
    )


def pipeline_stage_audit_enabled() -> bool:
    return bool(getattr(settings, "pipeline_stage_audit_enabled", True))
