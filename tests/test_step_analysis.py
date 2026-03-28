"""Pipeline stage audit enum and prompts (mockable LLM)."""

from apps.backend.agents.step_analysis import (
    prompt_audit_parse,
    prompt_audit_plan,
    StageAuditLLMResponse,
)
from apps.backend.models.schemas import (
    ParsedIntent,
    PipelineStageAuditVerdict,
    PlanOutput,
    PlanStep,
)


def test_audit_verdict_enum_values() -> None:
    assert PipelineStageAuditVerdict.sound.value == "sound"
    assert PipelineStageAuditVerdict.plan_mismatch.value == "plan_mismatch"


def test_stage_audit_prompts_contain_marker() -> None:
    p = ParsedIntent(
        cohort_name="t",
        cohort_description="d",
        action_type="search_web",
        action_params={"q": "x"},
        summary="s",
    )
    assert "pipeline_stage_audit_v1" in prompt_audit_parse("user q", p)
    plan = PlanOutput(steps=[PlanStep(action="search_web", params={"q": "x"})])
    assert "pipeline_stage_audit_v1" in prompt_audit_plan("user q", p, plan)


def test_stage_audit_llm_response_schema() -> None:
    m = StageAuditLLMResponse(verdict=PipelineStageAuditVerdict.needs_clarification, rationale="ask")
    assert m.verdict == PipelineStageAuditVerdict.needs_clarification
