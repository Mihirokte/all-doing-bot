"""Tests for task lifecycle and API endpoints. Pipeline is stubbed (no LLM/DB)."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.backend.db.models import Entry
from apps.backend.main import app
from apps.backend.models.schemas import ParsedIntent, PlanOutput, PlanStep
from apps.backend.pipeline.router import run_pipeline

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    api = data.get("api", {})
    assert api.get("workflows") is True
    assert api.get("chat") is True
    assert api.get("pipeline") is True
    assert api.get("task_store") in ("memory", "redis")
    assert isinstance(api.get("version"), str) and len(api.get("version", "")) > 0


def test_query_requires_q() -> None:
    r = client.get("/query")
    assert r.status_code in (400, 422)  # missing or empty q
    r2 = client.get("/query?q=")
    assert r2.status_code == 400


def test_query_accepts_and_returns_task_id() -> None:
    r = client.get("/query", params={"q": "hello"})
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert data["status"] == "accepted"
    assert isinstance(data["task_id"], str)
    assert len(data["task_id"]) > 0


def test_status_returns_processing_then_completed() -> None:
    # Create task via store directly so we don't start the background task (TestClient doesn't run it before we poll)
    from apps.backend.pipeline.task_store import task_store

    parsed = ParsedIntent(
        cohort_name="test_cohort",
        action_type="transform",
        action_params={"input": [{}]},
    )
    plan = PlanOutput(steps=[PlanStep(action="transform", params={"input": [{"x": 1}]})])

    task_id = task_store.create("test status")

    async def _run() -> None:
        with patch(
            "apps.backend.agents.parse_plan.run_parse_plan_langgraph",
            new_callable=AsyncMock,
            return_value=(parsed, plan),
        ), patch(
            "apps.backend.pipeline.executor.run_action_strict", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = [
                Entry(content="ok", source="transform", metadata="{}", created_at="2020-01-01T00:00:00Z"),
            ]
            await run_pipeline(task_id, "test status")

    asyncio.run(_run())
    d = None
    for _ in range(20):
        s = client.get(f"/status/{task_id}")
        assert s.status_code == 200
        d = s.json()
        if d["status"] == "completed":
            break
        import time
        time.sleep(0.05)
    assert d is not None
    assert d["task_id"] == task_id
    assert d["status"] == "completed"
    assert "result" in d
    assert d["result"].get("message") or d["result"].get("raw")
    # Executor records per-step diagnostics in result.raw
    if d["result"].get("raw") and "steps" in d["result"]["raw"]:
        assert isinstance(d["result"]["raw"]["steps"], list)
        assert len(d["result"]["raw"]["steps"]) >= 1


def test_status_404_for_unknown_task() -> None:
    r = client.get("/status/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_cohorts_returns_list() -> None:
    r = client.get("/cohorts")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_cohort_entries_404_until_db_connected() -> None:
    r = client.get("/cohort/any_name")
    assert r.status_code == 404
