"""Tests for task lifecycle and API endpoints. Pipeline is stubbed (no LLM/DB)."""
import asyncio
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import app
from apps.backend.pipeline.router import run_pipeline

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


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
    task_id = task_store.create("test status")
    asyncio.run(run_pipeline(task_id, "test status"))
    s = client.get(f"/status/{task_id}")
    assert s.status_code == 200
    d = s.json()
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
