"""Two-step parse then plan via LangGraph (separate LLM calls; more deterministic than one mega JSON)."""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from apps.backend.models.schemas import ParsedIntent, PlanOutput

logger = logging.getLogger(__name__)


class _ParsePlanState(TypedDict, total=False):
    query: str
    parsed: ParsedIntent | None
    plan: PlanOutput | None


async def _node_parse(state: _ParsePlanState) -> dict[str, Any]:
    from apps.backend.pipeline.stages import run_parse

    q = (state.get("query") or "").strip()
    parsed = await run_parse(q) if q else None
    return {"parsed": parsed}


async def _node_plan(state: _ParsePlanState) -> dict[str, Any]:
    from apps.backend.pipeline.stages import run_plan

    parsed = state.get("parsed")
    if parsed is None:
        return {"plan": None}
    plan = await run_plan(parsed)
    return {"plan": plan}


def _build_app():
    from langgraph.graph import END, StateGraph

    g = StateGraph(_ParsePlanState)
    g.add_node("parse", _node_parse)
    g.add_node("plan", _node_plan)
    g.set_entry_point("parse")
    g.add_edge("parse", "plan")
    g.add_edge("plan", END)
    return g.compile()


_compiled = None


def _compiled_graph():
    global _compiled
    if _compiled is None:
        _compiled = _build_app()
    return _compiled


async def _run_parse_then_plan_sequential(query: str) -> tuple[ParsedIntent | None, PlanOutput | None]:
    """Emergency fallback if LangGraph invoke fails (LLM/network); same two structured steps."""
    from apps.backend.pipeline.stages import run_parse, run_plan

    parsed = await run_parse(query)
    if parsed is None:
        return None, None
    plan = await run_plan(parsed)
    return parsed, plan


async def run_parse_plan_langgraph(query: str) -> tuple[ParsedIntent | None, PlanOutput | None]:
    """Run parse -> plan through LangGraph (required dependency). Falls back to sequential only on graph runtime errors."""
    try:
        out = await _compiled_graph().ainvoke({"query": query})
    except Exception as e:  # noqa: BLE001
        logger.warning("LangGraph invoke failed, falling back to sequential parse+plan: %s", e)
        return await _run_parse_then_plan_sequential(query)

    parsed = out.get("parsed")
    plan = out.get("plan")
    if not isinstance(parsed, ParsedIntent):
        parsed = None
    if plan is not None and not isinstance(plan, PlanOutput):
        plan = None
    return parsed, plan
