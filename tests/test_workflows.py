"""Deterministic task/note workflows (Sheets-backed cohorts)."""
from __future__ import annotations

import asyncio

from apps.backend.workflows.handlers import append_item, cohort_for, list_items


def test_cohort_for_stable_per_session() -> None:
    assert cohort_for("user-a", "tasks") == cohort_for("user-a", "tasks")
    assert cohort_for("user-a", "tasks") != cohort_for("user-b", "tasks")
    assert cohort_for("user-a", "tasks") != cohort_for("user-a", "notes")
    assert cohort_for("user-a", "chat").startswith("wf_chat_")
    assert cohort_for("user-a", "chat") != cohort_for("user-a", "tasks")


def test_append_and_list_task() -> None:
    async def _go() -> None:
        sk = "pytest-session-workflow"
        r = await append_item(sk, "tasks", "integration task line")
        assert r["ok"] is True
        items = await list_items(sk, "tasks", limit=20)
        assert any("integration task line" in (i.get("content") or "") for i in items)

    asyncio.run(_go())


def test_append_empty_rejected() -> None:
    async def _go() -> None:
        r = await append_item("x", "notes", "   ")
        assert r["ok"] is False

    asyncio.run(_go())
