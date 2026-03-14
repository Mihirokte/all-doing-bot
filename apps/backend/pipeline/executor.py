"""Orchestrate Parse -> Plan -> Execute -> Store. Updates task store per stage."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from apps.backend.actions.registry import run_action
from apps.backend.db.catalogue import catalogue
from apps.backend.db.sheets import add_entries
from apps.backend.models.schemas import ParsedIntent, PlanOutput, PlanStep, TaskResult
from apps.backend.pipeline.stages import run_parse_and_plan
from apps.backend.pipeline.task_store import task_store
from apps.backend.telemetry import log_run_event, set_run_context

logger = logging.getLogger(__name__)
_cohort_lock = asyncio.Lock()
MAX_STEPS = 5


def _is_search_intent(parsed: ParsedIntent) -> bool:
    """True if the user intent is to search/find information (not fetch specific URLs)."""
    if parsed.action_type == "search_web":
        return True
    q = parsed.action_params.get("q") or parsed.action_params.get("query") or parsed.action_params.get("keyword")
    if q is None:
        return False
    if isinstance(q, list):
        q = q[0] if q else ""
    return bool(str(q).strip())


def _web_fetch_step_has_no_urls(step: PlanStep) -> bool:
    """True if step is web_fetch but has no URLs to fetch."""
    if step.action != "web_fetch":
        return False
    urls = step.params.get("urls") or step.params.get("url")
    if isinstance(urls, str):
        urls = [urls] if urls.strip() else []
    return not (isinstance(urls, list) and any(u and str(u).strip() for u in urls))


def _resolve_step(step: PlanStep, parsed: ParsedIntent, query: str) -> tuple[str, dict]:
    """
    Resolve the step to (action_type, params). If plan says web_fetch with no URLs
    but parsed intent is search, reroute to search_web with q from parsed or query.
    """
    if _web_fetch_step_has_no_urls(step) and _is_search_intent(parsed):
        q = (
            parsed.action_params.get("q")
            or parsed.action_params.get("query")
            or parsed.action_params.get("keyword")
            or parsed.summary
            or query
        )
        if isinstance(q, list):
            q = q[0] if q else query
        q = str(q).strip() or query.strip()
        logger.info("Guardrail: rerouting empty web_fetch to search_web with q=%s", q[:80] if q else "")
        return "search_web", {"q": q}
    return step.action, step.params


async def run_full_pipeline(task_id: str, query: str) -> None:
    """
    Parse -> Plan -> Execute -> Store. Updates task_store after each stage.
    On parse/plan failure, marks task failed. On success, creates cohort (if new),
    runs action, writes entries to sheet, returns result.
    """
    set_run_context(task_id, None)
    try:
        task_store.set_status(task_id, "processing")

        parsed, plan = await run_parse_and_plan(query)
        if not parsed:
            log_run_event("run_failed", run_id=task_id, stage="parse", outcome="fail", error="Parse+plan stage failed: no valid JSON")
            task_store.set_failed(task_id, "Parse+plan stage failed: no valid JSON")
            return
        log_run_event("intent_parsed", run_id=task_id, stage="parse", outcome="ok", cohort_name=parsed.cohort_name, action_type=parsed.action_type)
        log_run_event("plan_ready", run_id=task_id, stage="plan", outcome="ok", step_count=len(plan.steps) if plan and plan.steps else 0)

        all_entries: list = []
        steps_diagnostics: list[dict] = []

        if not plan or not plan.steps:
            # Single logical step from parsed intent
            action, params = parsed.action_type, parsed.action_params
            if action == "web_fetch" and _web_fetch_step_has_no_urls(PlanStep(action=action, params=params)) and _is_search_intent(parsed):
                q = parsed.action_params.get("q") or parsed.summary or query
                if isinstance(q, list):
                    q = q[0] if q else query
                action, params = "search_web", {"q": str(q).strip() or query.strip()}
            set_run_context(task_id, 0)
            log_run_event("step_dispatched", run_id=task_id, stage="execute", step_index=0, action=action)
            try:
                all_entries = await run_action(action, params, run_id=task_id, step_index=0)
                steps_diagnostics.append({"action": action, "entry_count": len(all_entries)})
                log_run_event("step_completed", run_id=task_id, stage="execute", step_index=0, action=action, outcome="ok", entry_count=len(all_entries))
            except Exception as e:
                logger.warning("Single-step action %s failed: %s", action, e)
                steps_diagnostics.append({"action": action, "entry_count": 0, "error": str(e)})
                log_run_event("step_completed", run_id=task_id, stage="execute", step_index=0, action=action, outcome="fail", error=str(e))
        else:
            # Capped multi-step execution with per-step diagnostics
            for idx, step in enumerate(plan.steps[:MAX_STEPS]):
                action, params = _resolve_step(step, parsed, query)
                set_run_context(task_id, idx)
                log_run_event("step_dispatched", run_id=task_id, stage="execute", step_index=idx, action=action)
                try:
                    step_entries = await run_action(action, params, run_id=task_id, step_index=idx)
                    all_entries.extend(step_entries)
                    steps_diagnostics.append({"action": action, "entry_count": len(step_entries)})
                    log_run_event("step_completed", run_id=task_id, stage="execute", step_index=idx, action=action, outcome="ok", entry_count=len(step_entries))
                except Exception as e:
                    logger.warning("Step %s failed: %s", action, e)
                    steps_diagnostics.append({"action": action, "entry_count": 0, "error": str(e)})
                    log_run_event("step_completed", run_id=task_id, stage="execute", step_index=idx, action=action, outcome="fail", error=str(e))

        entries = all_entries
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

        log_run_event("run_stored", run_id=task_id, stage="store", outcome="ok", cohort_name=cohort_name, entries_added=len(entries))
        task_store.set_result(
            task_id,
            TaskResult(
                cohort_name=cohort_name,
                entries_added=len(entries),
                message=f"Created/updated cohort '{cohort_name}' with {len(entries)} entries.",
                raw={"steps": steps_diagnostics} if steps_diagnostics else None,
            ),
        )
    except Exception as e:
        log_run_event("run_failed", run_id=task_id, stage="pipeline", outcome="fail", error=str(e))
        logger.exception("Pipeline failed for task %s", task_id)
        task_store.set_failed(task_id, str(e))
