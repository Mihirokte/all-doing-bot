"""Orchestrate Parse -> Plan -> Execute -> Store. Updates task store per stage."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from apps.backend.actions.registry import run_action
from apps.backend.db.catalogue import catalogue
from apps.backend.db.sheets import add_entries
from apps.backend.models.schemas import ParsedIntent, PlanOutput, TaskResult
from apps.backend.pipeline.stages import run_parse, run_plan
from apps.backend.pipeline.task_store import task_store

logger = logging.getLogger(__name__)
_cohort_lock = asyncio.Lock()


async def run_full_pipeline(task_id: str, query: str) -> None:
    """
    Parse -> Plan -> Execute -> Store. Updates task_store after each stage.
    On parse/plan failure, marks task failed. On success, creates cohort (if new),
    runs action, writes entries to sheet, returns result.
    """
    try:
        task_store.set_status(task_id, "processing")

        parsed = await run_parse(query)
        if not parsed:
            task_store.set_failed(task_id, "Parse stage failed: no valid JSON")
            return

        plan = await run_plan(parsed)
        if not plan or not plan.steps:
            # Still proceed: use parsed intent as single "step" (action_type + action_params)
            entries = await run_action(parsed.action_type, parsed.action_params)
        else:
            # Execute first step only for MVP (e.g. web_fetch)
            step = plan.steps[0]
            entries = await run_action(step.action, step.params)

        now = datetime.now(timezone.utc).isoformat()
        cohort_name = parsed.cohort_name
        sheet_name = cohort_name

        from apps.backend.db.models import Cohort

        async with _cohort_lock:
            existing = await catalogue.get_cohort(cohort_name)
            if not existing:
                await catalogue.create_cohort(
                    Cohort(
                        cohort_name=cohort_name,
                        cohort_description=parsed.cohort_description,
                        action_type=parsed.action_type,
                        action_params=json.dumps(parsed.action_params),
                        created_at=now,
                        last_run=now,
                        sheet_name=sheet_name,
                        entry_count=len(entries),
                    )
                )
            else:
                await catalogue.update_cohort(
                    cohort_name, {"last_run": now, "entry_count": existing.entry_count + len(entries)}
                )

        if entries:
            await add_entries(cohort_name, entries)

        task_store.set_result(
            task_id,
            TaskResult(
                cohort_name=cohort_name,
                entries_added=len(entries),
                message=f"Created/updated cohort '{cohort_name}' with {len(entries)} entries.",
            ),
        )
    except Exception as e:
        logger.exception("Pipeline failed for task %s", task_id)
        task_store.set_failed(task_id, str(e))
