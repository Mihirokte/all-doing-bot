"""Orchestration event payloads for queue and run state."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StepDispatchedPayload(BaseModel):
    """Job payload for worker: execute one pipeline step."""

    run_id: str
    step_index: int
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""


class StepCompletedPayload(BaseModel):
    """Result of a step: entries (serializable) or error."""

    run_id: str
    step_index: int
    action: str
    entry_count: int = 0
    entries: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
