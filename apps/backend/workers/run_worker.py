"""Worker loop for queue-dispatched pipeline steps."""
from __future__ import annotations

import asyncio
import logging

from apps.backend.actions.contracts import error_code_from_exception, retry_class_for_error
from apps.backend.actions.policy import evaluate_action_policy
from apps.backend.actions.registry import get_contract, run_action_strict
from apps.backend.orchestration.events import StepCompletedPayload
from apps.backend.orchestration.queue import get_queue
from apps.backend.telemetry import log_policy_decision, log_run_event, set_run_context

logger = logging.getLogger(__name__)

DEQUEUE_TIMEOUT_SECONDS = 3.0
MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 1.5


async def _execute_with_retry(
    run_id: str,
    step_index: int,
    action: str,
    params: dict,
    connector_id: str | None = None,
    provider_key: str | None = None,
) -> StepCompletedPayload:
    queue = get_queue()
    policy = evaluate_action_policy(action, params)
    log_policy_decision(
        action=action,
        decision=policy.decision,
        reason=policy.reason,
        run_id=run_id,
        step_index=step_index,
        source="worker_pre_exec",
    )
    if policy.decision in {"deny", "require_approval"}:
        denied_payload = StepCompletedPayload(
            run_id=run_id,
            step_index=step_index,
            action=action,
            connector_id=connector_id,
            provider_key=provider_key,
            entry_count=0,
            entries=[],
            error=policy.reason,
            error_code="policy_denied" if policy.decision == "deny" else "approval_required",
        )
        await queue.add_dead_letter(denied_payload)
        return denied_payload
    contract = get_contract(action)
    last_error: Exception | None = None
    last_code = "internal"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            entries = await run_action_strict(
                action,
                params,
                run_id=run_id,
                step_index=step_index,
                connector_id=connector_id,
                provider_key=provider_key,
            )
            return StepCompletedPayload(
                run_id=run_id,
                step_index=step_index,
                action=action,
                connector_id=connector_id,
                provider_key=provider_key,
                entry_count=len(entries),
                entries=[e.model_dump() for e in entries],
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            code = error_code_from_exception(exc)
            last_code = code.value
            retry_class = retry_class_for_error(code, contract)
            should_retry = retry_class.value != "no_retry" and attempt < MAX_ATTEMPTS
            log_run_event(
                "step_retry",
                run_id=run_id,
                stage="execute",
                step_index=step_index,
                action=action,
                outcome="retrying" if should_retry else "stop",
                error=str(exc),
                error_code=code.value,
                attempt=attempt,
            )
            if not should_retry:
                break
            await asyncio.sleep(BASE_BACKOFF_SECONDS * attempt)

    payload = StepCompletedPayload(
        run_id=run_id,
        step_index=step_index,
        action=action,
        connector_id=connector_id,
        provider_key=provider_key,
        entry_count=0,
        entries=[],
        error=str(last_error) if last_error else "unknown worker failure",
        error_code=last_code,
    )
    await queue.add_dead_letter(payload)
    log_run_event(
        "dead_letter_emitted",
        run_id=run_id,
        stage="execute",
        step_index=step_index,
        action=action,
        outcome="dead_letter",
        error=payload.error,
        error_code=payload.error_code,
    )
    return payload


async def run_worker_forever() -> None:
    """Continuously consume queue jobs and publish step results."""
    queue = get_queue()
    logger.info("Worker started. Waiting for queued steps...")
    while True:
        payload = await queue.dequeue_step(timeout_seconds=DEQUEUE_TIMEOUT_SECONDS)
        if payload is None:
            continue
        existing = await queue.get_step_result(payload.run_id, payload.step_index)
        if existing is not None:
            log_run_event(
                "step_duplicate_skipped",
                run_id=payload.run_id,
                stage="execute",
                step_index=payload.step_index,
                action=payload.action,
                outcome="idempotent_skip",
            )
            continue
        set_run_context(payload.run_id, payload.step_index)
        log_run_event(
            "step_worker_received",
            run_id=payload.run_id,
            stage="execute",
            step_index=payload.step_index,
            action=payload.action,
        )
        result = await _execute_with_retry(
            payload.run_id,
            payload.step_index,
            payload.action,
            payload.params,
            connector_id=payload.connector_id,
            provider_key=payload.provider_key,
        )
        await queue.set_step_result(payload.run_id, payload.step_index, result)
        log_run_event(
            "step_completed",
            run_id=payload.run_id,
            stage="execute",
            step_index=payload.step_index,
            action=payload.action,
            outcome="ok" if not result.error else "fail",
            entry_count=result.entry_count,
            error=result.error,
            error_code=result.error_code,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(run_worker_forever())


if __name__ == "__main__":
    main()
