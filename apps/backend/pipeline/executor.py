"""Orchestrate Parse -> Plan -> Execute -> Store. Queue-first runtime with legacy fallback."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.actions.contracts import error_code_from_exception, idempotency_key, retry_class_for_error
from apps.backend.actions.policy import evaluate_action_policy
from apps.backend.actions.registry import get_contract, run_action, run_action_strict
from apps.backend.config import settings
from apps.backend.connectors.router import connector_router
from apps.backend.db.catalogue import catalogue
from apps.backend.db.memory import memory_store
from apps.backend.db.models import Entry
from apps.backend.db.sheets import add_entries
from apps.backend.models.schemas import ParsedIntent, PlanOutput, PlanStep, TaskResult
from apps.backend.orchestration.events import StepCompletedPayload, StepDispatchedPayload
from apps.backend.orchestration.queue import get_queue
from apps.backend.orchestration.run_state import set_run_meta, update_run_status
from apps.backend.pipeline.task_store import task_store
from apps.backend.telemetry import log_policy_decision, log_run_event, set_run_context

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


def _planned_steps(parsed: ParsedIntent, plan: PlanOutput | None, query: str) -> list[tuple[int, str, dict[str, Any]]]:
    """Build normalized execution steps (index, action, params)."""
    steps_to_run: list[tuple[int, str, dict[str, Any]]] = []
    if not plan or not plan.steps:
        action, params = parsed.action_type, parsed.action_params
        if action == "web_fetch" and _web_fetch_step_has_no_urls(PlanStep(action=action, params=params)) and _is_search_intent(parsed):
            q = parsed.action_params.get("q") or parsed.summary or query
            if isinstance(q, list):
                q = q[0] if q else query
            action, params = "search_web", {"q": str(q).strip() or query.strip()}
        steps_to_run.append((0, action, params))
    else:
        for idx, step in enumerate(plan.steps[:MAX_STEPS]):
            action, params = _resolve_step(step, parsed, query)
            steps_to_run.append((idx, action, params))
    return steps_to_run


def _entries_from_payloads(payloads: list[StepCompletedPayload]) -> list[Entry]:
    out: list[Entry] = []
    for payload in payloads:
        for row in payload.entries:
            try:
                out.append(Entry.model_validate(row))
            except Exception:
                continue
    return out


async def _run_steps_queue_first(
    task_id: str,
    parsed: ParsedIntent,
    plan: PlanOutput | None,
    query: str,
) -> tuple[list[Entry], list[dict[str, Any]], str]:
    """
    Queue-first execution path:
    - Dispatch steps to queue
    - Poll for step results (worker writes completion payloads)
    Returns (entries, diagnostics, execution_mode).
    """
    queue = get_queue()
    has_external_worker = bool((settings.redis_url or "").strip())
    steps_to_run = _planned_steps(parsed, plan, query)
    step_count = len(steps_to_run)
    await set_run_meta(
        task_id,
        query=query,
        step_count=step_count,
        parsed_json=json.dumps(parsed.model_dump()),
        plan_json=json.dumps(plan.model_dump() if plan else {"steps": []}),
        status="processing",
    )

    for idx, action, params in steps_to_run:
        set_run_context(task_id, idx)
        policy = evaluate_action_policy(action, params)
        log_policy_decision(
            action=action,
            decision=policy.decision,
            reason=policy.reason,
            run_id=task_id,
            step_index=idx,
            source="executor_dispatch",
        )
        if policy.decision in {"deny", "require_approval"}:
            denied_payload = StepCompletedPayload(
                run_id=task_id,
                step_index=idx,
                action=action,
                entry_count=0,
                entries=[],
                error=policy.reason,
                error_code="policy_denied" if policy.decision == "deny" else "approval_required",
            )
            await queue.set_step_result(task_id, idx, denied_payload)
            await queue.add_dead_letter(denied_payload)
            continue
        connector_id, provider_key = connector_router.route_metadata(action, params)
        payload = StepDispatchedPayload(
            run_id=task_id,
            step_index=idx,
            action=action,
            params=params,
            idempotency_key=idempotency_key(task_id, idx, action, params),
            connector_id=connector_id,
            provider_key=provider_key,
        )
        await queue.enqueue_step(payload)
        log_run_event("step_dispatched", run_id=task_id, stage="execute", step_index=idx, action=action)
        # In local dev with no Redis worker, execute via inline worker-compatible path.
        if not has_external_worker:
            # Local inline worker path with retry/dead-letter semantics.
            contract = get_contract(action)
            max_attempts = 3
            last_error: Exception | None = None
            last_code = "internal"
            entries: list[Entry] = []
            for attempt in range(1, max_attempts + 1):
                try:
                    entries = await run_action_strict(
                        action,
                        params,
                        run_id=task_id,
                        step_index=idx,
                        connector_id=connector_id,
                        provider_key=provider_key,
                    )
                    last_error = None
                    break
                except Exception as inline_error:  # noqa: BLE001
                    last_error = inline_error
                    code = error_code_from_exception(inline_error)
                    last_code = code.value
                    retry_class = retry_class_for_error(code, contract)
                    should_retry = retry_class.value != "no_retry" and attempt < max_attempts
                    log_run_event(
                        "step_retry",
                        run_id=task_id,
                        stage="execute",
                        step_index=idx,
                        action=action,
                        outcome="retrying" if should_retry else "stop",
                        error=str(inline_error),
                        error_code=code.value,
                        attempt=attempt,
                    )
                    if not should_retry:
                        break
                    await asyncio.sleep(1.0 * attempt)
            if last_error is None:
                await queue.set_step_result(
                    task_id,
                    idx,
                    StepCompletedPayload(
                        run_id=task_id,
                        step_index=idx,
                        action=action,
                        connector_id=connector_id,
                        provider_key=provider_key,
                        entry_count=len(entries),
                        entries=[e.model_dump() for e in entries],
                    ),
                )
            else:
                dl = StepCompletedPayload(
                    run_id=task_id,
                    step_index=idx,
                    action=action,
                    connector_id=connector_id,
                    provider_key=provider_key,
                    entry_count=0,
                    entries=[],
                    error=str(last_error),
                    error_code=last_code,
                )
                await queue.add_dead_letter(dl)
                await queue.set_step_result(task_id, idx, dl)

    timeout_seconds = max(10.0, float(getattr(settings, "queue_step_poll_timeout_seconds", 300.0) or 300.0))
    poll_interval = max(0.5, float(getattr(settings, "queue_step_poll_interval_seconds", 1.5) or 1.5))
    elapsed = 0.0
    while elapsed < timeout_seconds:
        payloads = await queue.get_all_step_results(task_id, step_count)
        if payloads is not None:
            diagnostics = [
                {
                    "action": p.action,
                    "connector_id": p.connector_id,
                    "provider_key": p.provider_key,
                    "policy_decision": "deny" if p.error_code == "policy_denied" else (
                        "require_approval" if p.error_code == "approval_required" else "allow"
                    ),
                    "entry_count": p.entry_count,
                    "error": p.error,
                    "error_code": p.error_code,
                }
                for p in payloads
            ]
            return _entries_from_payloads(payloads), diagnostics, "queue_worker"
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Timed out waiting for worker step results after {timeout_seconds:.1f}s")


async def _run_steps_legacy_in_process(
    task_id: str,
    parsed: ParsedIntent,
    plan: PlanOutput | None,
    query: str,
) -> tuple[list[Entry], list[dict[str, Any]], str]:
    """Legacy in-process execution path for emergency rollback."""
    all_entries: list[Entry] = []
    steps_diagnostics: list[dict[str, Any]] = []
    for idx, action, params in _planned_steps(parsed, plan, query):
        set_run_context(task_id, idx)
        policy = evaluate_action_policy(action, params)
        log_policy_decision(
            action=action,
            decision=policy.decision,
            reason=policy.reason,
            run_id=task_id,
            step_index=idx,
            source="executor_legacy",
        )
        log_run_event("step_dispatched", run_id=task_id, stage="execute", step_index=idx, action=action)
        connector_id, provider_key = connector_router.route_metadata(action, params)
        step_entries = await run_action(
            action,
            params,
            run_id=task_id,
            step_index=idx,
            connector_id=connector_id,
            provider_key=provider_key,
        )
        all_entries.extend(step_entries)
        steps_diagnostics.append(
            {
                "action": action,
                "connector_id": connector_id,
                "provider_key": provider_key,
                "policy_decision": policy.decision,
                "entry_count": len(step_entries),
            }
        )
        log_run_event(
            "step_completed",
            run_id=task_id,
            stage="execute",
            step_index=idx,
            action=action,
            outcome="ok",
            entry_count=len(step_entries),
        )
    return all_entries, steps_diagnostics, "legacy_in_process"


async def run_full_pipeline(task_id: str, query: str, session_key: str = "default") -> None:
    """
    Parse -> Plan -> Execute -> Store. Updates task_store after each stage.
    On parse/plan failure, marks task failed. On success, creates cohort (if new),
    runs action, writes entries to sheet, returns result.
    """
    set_run_context(task_id, None)
    lane_session_key = (session_key or "default").strip() or "default"
    try:
        task = task_store.get(task_id) or {}
        session_key = str(task.get("session_key") or lane_session_key)
        task_store.set_status(task_id, "processing")

        memory_context = await memory_store.get_context(session_key=session_key, query=query)
        memory_short = [m.content for m in memory_context.short_term][-4:]
        memory_long = [m.content for m in memory_context.long_term][:3]
        memory_lines = []
        if memory_short:
            memory_lines.append("Recent session memory:")
            memory_lines.extend([f"- {item}" for item in memory_short])
        if memory_long:
            memory_lines.append("Relevant long-term memory:")
            memory_lines.extend([f"- {item}" for item in memory_long])
        memory_prompt = "\n".join(memory_lines).strip()
        query_with_memory = query if not memory_prompt else f"{query}\n\n[Memory Context]\n{memory_prompt}"

        from apps.backend.agents.parse_plan import run_parse_plan_langgraph

        try:
            parsed, plan = await run_parse_plan_langgraph(query_with_memory)
        except Exception as parse_plan_exc:
            error_msg = f"Parse+plan stage exception: {parse_plan_exc}"
            logger.error("Parse+plan failed for task %s: %s", task_id, parse_plan_exc)
            log_run_event("run_failed", run_id=task_id, stage="parse", outcome="fail", error=error_msg)
            task_store.set_failed(task_id, error_msg)
            return
        if not parsed:
            error_msg = "Parse+plan stage failed: no valid JSON returned from LLM"
            logger.error("Parse+plan returned None for task %s", task_id)
            log_run_event("run_failed", run_id=task_id, stage="parse", outcome="fail", error=error_msg)
            task_store.set_failed(task_id, error_msg)
            return
        log_run_event("intent_parsed", run_id=task_id, stage="parse", outcome="ok", cohort_name=parsed.cohort_name, action_type=parsed.action_type)
        log_run_event("plan_ready", run_id=task_id, stage="plan", outcome="ok", step_count=len(plan.steps) if plan and plan.steps else 0)

        try:
            all_entries, steps_diagnostics, execution_mode = await _run_steps_queue_first(task_id, parsed, plan, query)
        except Exception as queue_error:
            logger.warning("Queue-first execution failed: %s", queue_error)
            if not settings.orchestrator_legacy_fallback_enabled:
                raise
            log_run_event(
                "queue_fallback",
                run_id=task_id,
                stage="execute",
                outcome="fallback_legacy",
                error=str(queue_error),
            )
            all_entries, steps_diagnostics, execution_mode = await _run_steps_legacy_in_process(task_id, parsed, plan, query)

        entries = all_entries
        now = datetime.now(timezone.utc).isoformat()
        cohort_name = parsed.cohort_name
        sheet_name = cohort_name

        storage_ok = True
        if entries:
            try:
                await add_entries(cohort_name, entries)
            except Exception as storage_err:
                storage_ok = False
                logger.error("Failed to store %d entries for cohort %s: %s", len(entries), cohort_name, storage_err)

        from apps.backend.db.models import Cohort

        async with _cohort_lock:
            existing = await catalogue.get_cohort(cohort_name)
            stored_count = len(entries) if storage_ok else 0
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
                        entry_count=stored_count,
                    )
                )
            else:
                await catalogue.update_cohort(
                    cohort_name, {"last_run": now, "entry_count": existing.entry_count + stored_count}
                )

        dead_letters = [s for s in steps_diagnostics if s.get("error")]
        if not storage_ok:
            await update_run_status(task_id, "completed_with_warnings")
        else:
            await update_run_status(task_id, "completed_with_dead_letters" if dead_letters else "completed")
        log_run_event(
            "run_stored",
            run_id=task_id,
            stage="store",
            outcome="ok",
            cohort_name=cohort_name,
            entries_added=len(entries),
            execution_mode=execution_mode,
            dead_letter_count=len(dead_letters),
        )
        task_store.set_result(
            task_id,
            TaskResult(
                cohort_name=cohort_name,
                entries_added=len(entries),
                message=f"Created/updated cohort '{cohort_name}' with {len(entries)} entries.",
                raw={
                    "steps": steps_diagnostics,
                    "tool_path": [s.get("action") for s in steps_diagnostics if s.get("action")],
                    "connector_path": [
                        f"{s.get('connector_id')}:{s.get('provider_key')}"
                        for s in steps_diagnostics
                        if s.get("connector_id") and s.get("provider_key")
                    ],
                    "execution_mode": execution_mode,
                    "dead_letters": dead_letters,
                    "policy_outcomes": [
                        {
                            "action": s.get("action"),
                            "policy_decision": s.get("policy_decision", "allow"),
                            "error_code": s.get("error_code"),
                        }
                        for s in steps_diagnostics
                    ],
                    "memory_hits": {
                        "short_term": [m.model_dump() for m in memory_context.short_term],
                        "long_term": [m.model_dump() for m in memory_context.long_term],
                    },
                }
                if steps_diagnostics
                else None,
            ),
        )
        await memory_store.append_short_term(session_key=session_key, role="user", content=query)
        if parsed.summary:
            await memory_store.append_short_term(session_key=session_key, role="assistant", content=parsed.summary)
            await memory_store.upsert_long_term(
                session_key=session_key,
                content=parsed.summary,
                tags=[parsed.cohort_name, parsed.action_type],
                score=1.0,
            )
    except Exception as e:
        log_run_event("run_failed", run_id=task_id, stage="pipeline", outcome="fail", error=str(e))
        await update_run_status(task_id, "failed")
        logger.exception("Pipeline failed for task %s", task_id)
        task_store.set_failed(task_id, str(e))
