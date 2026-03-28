"""Parse → plan LangGraph with one local LLM audit (enum verdict) after each stage."""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from apps.backend.models.schemas import ParsePlanGraphOutcome, ParsedIntent, PlanOutput, PipelineStageAnalysis

logger = logging.getLogger(__name__)


class _ParsePlanState(TypedDict, total=False):
    query: str
    parsed: ParsedIntent | None
    plan: PlanOutput | None
    parse_analysis: PipelineStageAnalysis | None
    plan_analysis: PipelineStageAnalysis | None


async def _node_parse(state: _ParsePlanState) -> dict[str, Any]:
    from apps.backend.pipeline.stages import run_parse

    q = (state.get("query") or "").strip()
    parsed = await run_parse(q) if q else None
    return {"parsed": parsed}


async def _node_analyze_parse(state: _ParsePlanState) -> dict[str, Any]:
    from apps.backend.agents.step_analysis import (
        audit_disabled_placeholder,
        audit_parse_failed_placeholder,
        audit_parse_output,
        pipeline_stage_audit_enabled,
    )

    parsed = state.get("parsed")
    q = state.get("query") or ""
    if parsed is None:
        return {"parse_analysis": audit_parse_failed_placeholder()}
    if not pipeline_stage_audit_enabled():
        return {"parse_analysis": audit_disabled_placeholder("parse")}
    analysis = await audit_parse_output(q, parsed)
    return {"parse_analysis": analysis}


async def _node_plan(state: _ParsePlanState) -> dict[str, Any]:
    from apps.backend.pipeline.stages import run_plan

    parsed = state.get("parsed")
    if parsed is None:
        return {"plan": None}
    plan = await run_plan(parsed)
    return {"plan": plan}


async def _node_analyze_plan(state: _ParsePlanState) -> dict[str, Any]:
    from apps.backend.agents.step_analysis import (
        audit_disabled_placeholder,
        audit_plan_failed_placeholder,
        audit_plan_output,
        pipeline_stage_audit_enabled,
    )

    parsed = state.get("parsed")
    plan = state.get("plan")
    q = state.get("query") or ""
    if parsed is None or plan is None:
        return {"plan_analysis": audit_plan_failed_placeholder()}
    if not pipeline_stage_audit_enabled():
        return {"plan_analysis": audit_disabled_placeholder("plan")}
    analysis = await audit_plan_output(q, parsed, plan)
    return {"plan_analysis": analysis}


def _build_app():
    from langgraph.graph import END, StateGraph

    g = StateGraph(_ParsePlanState)
    g.add_node("parse", _node_parse)
    g.add_node("analyze_parse", _node_analyze_parse)
    g.add_node("plan", _node_plan)
    g.add_node("analyze_plan", _node_analyze_plan)
    g.set_entry_point("parse")
    g.add_edge("parse", "analyze_parse")
    g.add_edge("analyze_parse", "plan")
    g.add_edge("plan", "analyze_plan")
    g.add_edge("analyze_plan", END)
    return g.compile()


_compiled = None


def _compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = _build_app()
    return _compiled


def _outcome_from_state(
    parsed: ParsedIntent | None,
    plan: PlanOutput | None,
    parse_analysis: PipelineStageAnalysis | None,
    plan_analysis: PipelineStageAnalysis | None,
) -> ParsePlanGraphOutcome:
    analyses: list[PipelineStageAnalysis] = []
    if isinstance(parse_analysis, PipelineStageAnalysis):
        analyses.append(parse_analysis)
    if isinstance(plan_analysis, PipelineStageAnalysis):
        analyses.append(plan_analysis)
    return ParsePlanGraphOutcome(parsed=parsed, plan=plan, stage_analyses=analyses)


async def _run_parse_plan_with_audits_sequential(
    query: str,
    existing_parsed: ParsedIntent | None = None,
) -> ParsePlanGraphOutcome:
    """Fallback: parse → audit → plan → audit (same as graph, no LangGraph runtime)."""
    from apps.backend.agents.step_analysis import (
        audit_disabled_placeholder,
        audit_parse_failed_placeholder,
        audit_parse_output,
        audit_plan_failed_placeholder,
        audit_plan_output,
        pipeline_stage_audit_enabled,
    )
    from apps.backend.pipeline.stages import run_parse, run_plan

    parse_analysis: PipelineStageAnalysis | None = None
    plan_analysis: PipelineStageAnalysis | None = None

    parsed = existing_parsed
    if parsed is None:
        parsed = await run_parse(query)
        if parsed is None:
            return _outcome_from_state(None, None, audit_parse_failed_placeholder(), None)
        logger.info("Fallback sequential: parse completed")
    else:
        logger.info("Fallback: reusing existing parse result, only re-running plan stage")

    if pipeline_stage_audit_enabled():
        parse_analysis = await audit_parse_output(query, parsed)
    else:
        parse_analysis = audit_disabled_placeholder("parse")

    plan = await run_plan(parsed)
    if plan is None:
        return _outcome_from_state(
            parsed,
            None,
            parse_analysis,
            audit_plan_failed_placeholder(),
        )

    if pipeline_stage_audit_enabled():
        plan_analysis = await audit_plan_output(query, parsed, plan)
    else:
        plan_analysis = audit_disabled_placeholder("plan")

    return _outcome_from_state(parsed, plan, parse_analysis, plan_analysis)


async def run_parse_plan_langgraph(query: str) -> ParsePlanGraphOutcome:
    """
    Run parse → analyze_parse → plan → analyze_plan.

    Each analyze node issues one structured local LLM question and records a
    ``PipelineStageAuditVerdict`` enum on the outcome.
    """
    try:
        out = await _compiled_graph().ainvoke({"query": query})
    except Exception as e:  # noqa: BLE001
        logger.error("LangGraph invoke failed: %s", e)
        partial_parsed: ParsedIntent | None = None
        try:
            graph = _compiled_graph()
            if hasattr(graph, "get_state"):
                state = graph.get_state({"query": query})
                if state and isinstance(state.get("parsed"), ParsedIntent):
                    partial_parsed = state["parsed"]
                    logger.info("Recovered partial parse result from failed graph execution")
        except Exception:  # noqa: BLE001
            pass
        return await _run_parse_plan_with_audits_sequential(query, existing_parsed=partial_parsed)

    parsed = out.get("parsed")
    plan = out.get("plan")
    parse_analysis = out.get("parse_analysis")
    plan_analysis = out.get("plan_analysis")
    if not isinstance(parsed, ParsedIntent):
        parsed = None
    if plan is not None and not isinstance(plan, PlanOutput):
        plan = None
    if parse_analysis is not None and not isinstance(parse_analysis, PipelineStageAnalysis):
        parse_analysis = None
    if plan_analysis is not None and not isinstance(plan_analysis, PipelineStageAnalysis):
        plan_analysis = None
    return _outcome_from_state(parsed, plan, parse_analysis, plan_analysis)
