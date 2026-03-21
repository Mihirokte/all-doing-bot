"""Tests for pipeline executor: guardrail fallback, multi-step, diagnostics."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from apps.backend.models.schemas import ParsedIntent, PlanStep
from apps.backend.pipeline.executor import (
    _is_search_intent,
    _resolve_step,
    _web_fetch_step_has_no_urls,
    run_full_pipeline,
)
from apps.backend.pipeline.task_store import task_store


def test_is_search_intent_search_web_type() -> None:
    parsed = ParsedIntent(
        cohort_name="x",
        action_type="search_web",
        action_params={},
    )
    assert _is_search_intent(parsed) is True


def test_is_search_intent_has_q_param() -> None:
    parsed = ParsedIntent(
        cohort_name="x",
        action_type="web_fetch",
        action_params={"q": "python news"},
    )
    assert _is_search_intent(parsed) is True


def test_is_search_intent_has_query_param() -> None:
    parsed = ParsedIntent(
        cohort_name="x",
        action_type="web_fetch",
        action_params={"query": "AI updates"},
    )
    assert _is_search_intent(parsed) is True


def test_is_search_intent_empty_urls_no_q() -> None:
    parsed = ParsedIntent(
        cohort_name="x",
        action_type="web_fetch",
        action_params={"urls": []},
    )
    assert _is_search_intent(parsed) is False


def test_web_fetch_step_has_no_urls_empty_list() -> None:
    step = PlanStep(action="web_fetch", params={"urls": []})
    assert _web_fetch_step_has_no_urls(step) is True


def test_web_fetch_step_has_no_urls_missing_urls() -> None:
    step = PlanStep(action="web_fetch", params={})
    assert _web_fetch_step_has_no_urls(step) is True


def test_web_fetch_step_has_urls() -> None:
    step = PlanStep(action="web_fetch", params={"urls": ["https://example.com"]})
    assert _web_fetch_step_has_no_urls(step) is False


def test_resolve_step_reroutes_empty_web_fetch_to_search_web() -> None:
    step = PlanStep(action="web_fetch", params={"urls": []})
    parsed = ParsedIntent(
        cohort_name="brief",
        action_type="search_web",
        action_params={"q": "AI news"},
        summary="Get AI news",
    )
    action, params = _resolve_step(step, parsed, "user query")
    assert action == "search_web"
    assert params.get("q") == "AI news"


def test_resolve_step_reroutes_using_summary_when_no_q() -> None:
    step = PlanStep(action="web_fetch", params={"urls": []})
    parsed = ParsedIntent(
        cohort_name="brief",
        action_type="web_fetch",
        action_params={"keyword": "test"},
        summary="Fetch test results",
    )
    action, params = _resolve_step(step, parsed, "fallback query")
    assert action == "search_web"
    assert params.get("q") == "test"


def test_resolve_step_passes_through_web_fetch_with_urls() -> None:
    step = PlanStep(action="web_fetch", params={"urls": ["https://example.com"]})
    parsed = ParsedIntent(cohort_name="x", action_type="web_fetch", action_params={"urls": ["https://example.com"]})
    action, params = _resolve_step(step, parsed, "query")
    assert action == "web_fetch"
    assert params["urls"] == ["https://example.com"]


def test_run_full_pipeline_multistep_includes_diagnostics() -> None:
    task_id = task_store.create("multi step test")
    parsed = ParsedIntent(
        cohort_name="multi_cohort",
        action_type="search_web",
        action_params={"q": "test"},
    )
    plan_steps = [
        PlanStep(action="transform", params={"input": [{"a": 1}]}),
        PlanStep(action="transform", params={"input": [{"b": 2}]}),
    ]
    from apps.backend.models.schemas import PlanOutput

    plan = PlanOutput(steps=plan_steps)

    async def run() -> None:
        with patch(
            "apps.backend.agents.parse_plan.run_parse_plan_langgraph", new_callable=AsyncMock, return_value=(parsed, plan)
        ), patch("apps.backend.pipeline.executor.run_action", new_callable=AsyncMock) as mock_run:
            from apps.backend.db.models import Entry

            mock_run.return_value = [
                Entry(content="e1", source="transform", metadata="{}", created_at="2020-01-01T00:00:00Z"),
            ]
            await run_full_pipeline(task_id, "multi step test")

    asyncio.run(run())

    resp = task_store.get_response(task_id)
    assert resp is not None
    assert resp.status == "completed"
    assert resp.result is not None
    assert resp.result.raw is not None
    assert "steps" in resp.result.raw
    assert len(resp.result.raw["steps"]) == 2
    assert resp.result.raw["steps"][0]["action"] == "transform"
    assert resp.result.raw["steps"][1]["action"] == "transform"
