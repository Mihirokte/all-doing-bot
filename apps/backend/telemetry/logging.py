"""Structured run/step logging for observability (run_id, stage, action, latency, outcome)."""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.backend.telemetry.context import get_run_id, get_step_index

logger = logging.getLogger(__name__)


def _extra(run_id: str | None = None, step_index: int | None = None, **kwargs: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"run_id": run_id or get_run_id(), "step_index": step_index if step_index is not None else get_step_index()}
    for k, v in kwargs.items():
        if v is not None:
            out[k] = v
    return out


def log_run_event(
    event: str,
    run_id: str | None = None,
    stage: str | None = None,
    outcome: str | None = None,
    error: str | None = None,
    **kwargs: Any,
) -> None:
    """Emit a structured run lifecycle event (run_accepted, intent_parsed, plan_ready, step_dispatched, step_completed, run_stored, run_failed)."""
    payload = _extra(run_id=run_id, stage=stage, outcome=outcome, error=error, **kwargs)
    payload["event"] = event
    logger.info("telemetry: %s", payload, extra={"telemetry": payload})


def log_action_exec(
    action: str,
    latency_ms: float,
    outcome: str,
    run_id: str | None = None,
    step_index: int | None = None,
    entry_count: int | None = None,
    error_code: str | None = None,
    **kwargs: Any,
) -> None:
    """Emit structured action execution (action, latency_ms, outcome, entry_count, error_code)."""
    payload = _extra(
        run_id=run_id,
        step_index=step_index,
        action=action,
        latency_ms=round(latency_ms, 2),
        outcome=outcome,
        entry_count=entry_count,
        error_code=error_code,
        **kwargs,
    )
    payload["event"] = "action_exec"
    logger.info("telemetry: %s", payload, extra={"telemetry": payload})
