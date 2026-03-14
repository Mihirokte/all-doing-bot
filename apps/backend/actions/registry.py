"""Action type registry: map action_type string -> handler and contract."""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.backend.actions.api_call import ApiCallAction
from apps.backend.actions.base import BaseAction
from apps.backend.actions.contracts import DEFAULT_CONTRACTS, ActionContract, error_code_from_exception
from apps.backend.actions.transform import TransformAction
from apps.backend.actions.web_fetch import WebFetchAction
from apps.backend.actions.web_search import WebSearchAction
from apps.backend.db.models import Entry
from apps.backend.telemetry import log_action_exec, set_run_context
from apps.backend.telemetry.context import get_run_id, get_step_index

logger = logging.getLogger(__name__)

REGISTRY: dict[str, type[BaseAction]] = {
    "web_fetch": WebFetchAction,
    "search_web": WebSearchAction,
    "api_call": ApiCallAction,
    "transform": TransformAction,
}


def get_action(action_type: str) -> BaseAction | None:
    """Return action instance for type, or None if unknown."""
    cls = REGISTRY.get(action_type)
    return cls() if cls else None


def get_contract(capability_id: str) -> ActionContract | None:
    """Return contract for capability_id; uses DEFAULT_CONTRACTS or action.get_contract()."""
    cls = REGISTRY.get(capability_id)
    if cls:
        inst = cls()
        if hasattr(inst, "get_contract") and inst.get_contract() is not None:
            return inst.get_contract()
    return DEFAULT_CONTRACTS.get(capability_id)


async def run_action(
    action_type: str,
    params: dict[str, Any],
    run_id: str | None = None,
    step_index: int | None = None,
) -> list[Entry]:
    """Execute action by type. Returns empty list if unknown or on error. Logs action_exec telemetry."""
    if run_id is not None or step_index is not None:
        set_run_context(run_id, step_index)
    action = get_action(action_type)
    if not action:
        logger.warning("Unknown action_type: %s", action_type)
        log_action_exec(
            action_type,
            0.0,
            "fail",
            run_id=run_id or get_run_id(),
            step_index=step_index if step_index is not None else get_step_index(),
            error_code="unknown_action",
        )
        return []
    start = time.perf_counter()
    try:
        entries = await action.execute(params)
        latency_ms = (time.perf_counter() - start) * 1000
        log_action_exec(
            action_type,
            latency_ms,
            "ok",
            run_id=run_id or get_run_id(),
            step_index=step_index if step_index is not None else get_step_index(),
            entry_count=len(entries),
        )
        return entries
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        code = error_code_from_exception(e)
        log_action_exec(
            action_type,
            latency_ms,
            "fail",
            run_id=run_id or get_run_id(),
            step_index=step_index if step_index is not None else get_step_index(),
            entry_count=0,
            error_code=code.value,
        )
        logger.exception("Action %s failed: %s", action_type, e)
        return []
